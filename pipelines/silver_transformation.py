import json
from pathlib import Path

from pyspark.sql import SparkSession, Window
from pyspark.sql.functions import (
    array, array_join, col, current_date, datediff, lit, row_number, size,
    to_date, to_timestamp, trim, upper, when, expr,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BRONZE_DIR = PROJECT_ROOT / "data" / "bronze" / "customers"
SILVER_DIR = PROJECT_ROOT / "data" / "silver" / "customers"
DQ_SUMMARY_FILE = PROJECT_ROOT / "data" / "silver" / "_metadata" / "customers_dq_summary.json"

# Static FX reference rates to USD. A production pipeline would read these
# from a daily FX-rates reference table rather than hardcoding them.
FX_TO_USD = {"USD": 1.0, "EUR": 1.08, "GBP": 1.27, "INR": 0.012}

VALID_STATUS_VALUES = ["ACTIVE", "INACTIVE", "SUSPENDED", "CHURNED"]
HIGH_VALUE_THRESHOLD_USD = 2000.0
AOV_MISMATCH_TOLERANCE = 0.10
EMAIL_PATTERN = r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"


def _fx_rate_column():
    rate_expr = lit(1.0)
    for currency, rate in FX_TO_USD.items():
        rate_expr = when(col("currency") == currency, lit(rate)).otherwise(rate_expr)
    return rate_expr


def main() -> None:
    spark = (
        SparkSession.builder
        .appName("Aegis-Silver-Transformation")
        .master("local[2]")
        .getOrCreate()
    )

    spark.sparkContext.setLogLevel("WARN")

    print(f"Reading Bronze: {BRONZE_DIR}")

    bronze_df = spark.read.parquet(str(BRONZE_DIR))
    raw_record_count = bronze_df.count()
    print(f"Bronze records: {raw_record_count}")

    # Bronze-only lineage metadata never flows into Silver's business schema.
    working_df = bronze_df.drop(
        "ingestion_timestamp", "source_file_name", "ingestion_batch_id"
    ).withColumn("last_updated_at", to_timestamp(col("last_updated_at")))

    # --- Deduplication: multiple source systems can re-send a customer
    # record (CRM merge/re-sync). Keep only the most recently updated row.
    dedup_window = Window.partitionBy("customer_id").orderBy(
        col("last_updated_at").desc()
    )
    working_df = (
        working_df
        .filter(col("customer_id").isNotNull())
        .withColumn("_row_rank", row_number().over(dedup_window))
        .filter(col("_row_rank") == 1)
        .drop("_row_rank")
    )
    deduplicated_record_count = working_df.count()

    # --- Standardize free-text fields across inconsistent source systems.
    working_df = (
        working_df
        .withColumn("customer_name", trim(col("customer_name")))
        .withColumn("country", upper(trim(col("country"))))
        .withColumn("customer_segment", upper(trim(col("customer_segment"))))
        .withColumn("loyalty_tier", when(col("loyalty_tier").isNull(), lit("NONE")).otherwise(upper(trim(col("loyalty_tier")))))
        .withColumn("status", upper(trim(col("status"))))
        .withColumn(
            "status",
            when(col("status").isin(VALID_STATUS_VALUES), col("status")).otherwise(lit("UNKNOWN")),
        )
        .withColumn("marketing_opt_in", col("marketing_opt_in").cast("boolean"))
    )

    # --- Cast dates/numerics explicitly (never trust inferSchema long-term).
    working_df = (
        working_df
        .withColumn("date_of_birth", to_date(col("date_of_birth")))
        .withColumn("registration_date", to_date(col("registration_date")))
        .withColumn("first_purchase_date", to_date(col("first_purchase_date")))
        .withColumn("last_purchase_date", to_date(col("last_purchase_date")))
        .withColumn("total_orders", col("total_orders").cast("int"))
        .withColumn("returns_count", col("returns_count").cast("int"))
        .withColumn("support_tickets_count", col("support_tickets_count").cast("int"))
        .withColumn("total_revenue", col("total_revenue").cast("double"))
        .withColumn("avg_order_value", col("avg_order_value").cast("double"))
        .withColumn("lifetime_value", col("lifetime_value").cast("double"))
        .withColumn("churn_risk_score", col("churn_risk_score").cast("int"))
    )

    # --- Business-rule validation and correction (flagged, not silently
    # dropped, so downstream consumers and the DQ scorecard stay accurate).
    working_df = (
        working_df
        .withColumn("is_valid_email", col("email").isNotNull() & col("email").rlike(EMAIL_PATTERN))
        .withColumn("is_revenue_anomaly", col("total_revenue") < 0)
        .withColumn("total_revenue", when(col("total_revenue") < 0, lit(0.0)).otherwise(col("total_revenue")))
        .withColumn("is_churn_anomaly", (col("churn_risk_score") < 0) | (col("churn_risk_score") > 100))
        .withColumn(
            "churn_risk_score",
            when(col("churn_risk_score") < 0, lit(0))
            .when(col("churn_risk_score") > 100, lit(100))
            .otherwise(col("churn_risk_score")),
        )
        .withColumn(
            "_expected_avg_order_value",
            when(col("total_orders") > 0, col("total_revenue") / col("total_orders")).otherwise(lit(0.0)),
        )
        .withColumn(
            "is_aov_mismatch",
            (col("total_orders") > 0)
            & ~(
                (col("avg_order_value") - col("_expected_avg_order_value")).between(
                    -(AOV_MISMATCH_TOLERANCE * col("_expected_avg_order_value")),
                    AOV_MISMATCH_TOLERANCE * col("_expected_avg_order_value"),
                )
            ),
        )
        .withColumn("avg_order_value", col("_expected_avg_order_value"))
        .drop("_expected_avg_order_value")
    )

    # --- Currency normalization to USD for consistent business reporting.
    working_df = (
        working_df
        .withColumn("_fx_rate_to_usd", _fx_rate_column())
        .withColumnRenamed("total_revenue", "total_revenue_local")
        .withColumnRenamed("avg_order_value", "avg_order_value_local")
        .withColumnRenamed("lifetime_value", "lifetime_value_local")
        .withColumn("total_revenue_usd", col("total_revenue_local") * col("_fx_rate_to_usd"))
        .withColumn("avg_order_value_usd", col("avg_order_value_local") * col("_fx_rate_to_usd"))
        .withColumn("lifetime_value_usd", col("lifetime_value_local") * col("_fx_rate_to_usd"))
        .drop("_fx_rate_to_usd")
    )

    # --- Derived business attributes.
    working_df = (
        working_df
        .withColumn("customer_tenure_days", datediff(current_date(), col("registration_date")))
        .withColumn(
            "days_since_last_purchase",
            when(col("last_purchase_date").isNotNull(), datediff(current_date(), col("last_purchase_date"))),
        )
        .withColumn("is_high_value_customer", col("lifetime_value_usd") > HIGH_VALUE_THRESHOLD_USD)
        .withColumn(
            "churn_risk_label",
            when(col("churn_risk_score") >= 67, lit("HIGH"))
            .when(col("churn_risk_score") >= 34, lit("MEDIUM"))
            .otherwise(lit("LOW")),
        )
    )

    # --- Collapse the per-row anomaly flags into a single audit-friendly
    # data_quality_flags column, then drop the intermediate flag columns.
    flags = array(
        when(~col("is_valid_email"), lit("INVALID_EMAIL")),
        when(col("is_revenue_anomaly"), lit("NEGATIVE_REVENUE_CORRECTED")),
        when(col("is_churn_anomaly"), lit("CHURN_SCORE_OUT_OF_RANGE_CLAMPED")),
        when(col("is_aov_mismatch"), lit("AOV_MISMATCH_RECALCULATED")),
    )
    working_df = (
        working_df
        .withColumn("_flags_raw", flags)
        .withColumn("_flags_clean", expr("filter(_flags_raw, x -> x is not null)"))
        .withColumn(
            "data_quality_flags",
            when(size(col("_flags_clean")) == 0, lit("CLEAN")).otherwise(array_join(col("_flags_clean"), "|")),
        )
    )

    invalid_email_count = working_df.filter(~col("is_valid_email")).count()
    revenue_anomaly_count = working_df.filter(col("is_revenue_anomaly")).count()
    churn_anomaly_count = working_df.filter(col("is_churn_anomaly")).count()
    aov_mismatch_count = working_df.filter(col("is_aov_mismatch")).count()
    clean_record_count = working_df.filter(col("data_quality_flags") == "CLEAN").count()

    silver_df = working_df.drop(
        "is_revenue_anomaly", "is_churn_anomaly", "is_aov_mismatch", "_flags_raw", "_flags_clean"
    )

    print("Silver schema:")
    silver_df.printSchema()
    print(f"Silver records (post-dedup): {deduplicated_record_count}")

    silver_df.write.mode("overwrite").parquet(str(SILVER_DIR))

    dq_summary = {
        "raw_record_count": raw_record_count,
        "deduplicated_record_count": deduplicated_record_count,
        "duplicates_removed": raw_record_count - deduplicated_record_count,
        "invalid_email_count": invalid_email_count,
        "revenue_anomaly_count": revenue_anomaly_count,
        "churn_anomaly_count": churn_anomaly_count,
        "aov_mismatch_count": aov_mismatch_count,
        "clean_record_count": clean_record_count,
        "clean_record_pct": round(100.0 * clean_record_count / deduplicated_record_count, 2) if deduplicated_record_count else 0.0,
    }
    DQ_SUMMARY_FILE.parent.mkdir(parents=True, exist_ok=True)
    DQ_SUMMARY_FILE.write_text(json.dumps(dq_summary, indent=2), encoding="utf-8")

    print("Data quality summary:")
    print(json.dumps(dq_summary, indent=2))
    print(f"Silver output: {SILVER_DIR}")
    print(f"DQ summary written to: {DQ_SUMMARY_FILE}")
    print("SILVER TRANSFORMATION PASSED")

    spark.stop()


if __name__ == "__main__":
    main()
