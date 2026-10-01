import json
from pathlib import Path

from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    avg, col, count, countDistinct, lit, round as spark_round, sum, when,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SILVER_DIR = PROJECT_ROOT / "data" / "silver" / "customers"
DQ_SUMMARY_FILE = PROJECT_ROOT / "data" / "silver" / "_metadata" / "customers_dq_summary.json"
GOLD_ROOT = PROJECT_ROOT / "data" / "gold"

CUSTOMER_SUMMARY_DIR = GOLD_ROOT / "customer_summary"
SEGMENT_PERFORMANCE_DIR = GOLD_ROOT / "segment_performance"
LOYALTY_TIER_DIR = GOLD_ROOT / "loyalty_tier_distribution"
CHURN_RISK_DIR = GOLD_ROOT / "churn_risk_summary"
ACQUISITION_CHANNEL_DIR = GOLD_ROOT / "acquisition_channel_performance"
DQ_SCORECARD_DIR = GOLD_ROOT / "data_quality_scorecard"


def main() -> None:
    spark = (
        SparkSession.builder
        .appName("Aegis-Gold-Transformation")
        .master("local[2]")
        .getOrCreate()
    )

    spark.sparkContext.setLogLevel("WARN")

    print(f"Reading Silver: {SILVER_DIR}")

    df = spark.read.parquet(str(SILVER_DIR)).cache()

    total_silver_records = df.count()
    print(f"Silver records: {total_silver_records}")

    # --- 1. Customer summary by country (executive overview + revenue).
    customer_summary = (
        df.groupBy("country")
        .agg(
            count("*").alias("total_customers"),
            sum(when(col("status") == "ACTIVE", 1).otherwise(0)).alias("active_customers"),
            sum(when(col("status") == "INACTIVE", 1).otherwise(0)).alias("inactive_customers"),
            sum(when(col("status") == "CHURNED", 1).otherwise(0)).alias("churned_customers"),
            spark_round(sum("total_revenue_usd"), 2).alias("total_revenue_usd"),
            spark_round(avg("lifetime_value_usd"), 2).alias("avg_lifetime_value_usd"),
            sum(when(col("is_high_value_customer"), 1).otherwise(0)).alias("high_value_customers"),
        )
        .orderBy("country")
    )

    # --- 2. Segment performance (business/marketing view).
    segment_performance = (
        df.groupBy("customer_segment")
        .agg(
            count("*").alias("customer_count"),
            spark_round(sum("total_revenue_usd"), 2).alias("total_revenue_usd"),
            spark_round(avg("avg_order_value_usd"), 2).alias("avg_order_value_usd"),
            spark_round(avg("lifetime_value_usd"), 2).alias("avg_lifetime_value_usd"),
            spark_round(
                100.0 * sum(when(col("status") == "CHURNED", 1).otherwise(0)) / count("*"), 2
            ).alias("churn_rate_pct"),
        )
        .orderBy(col("total_revenue_usd").desc())
    )

    # --- 3. Loyalty tier distribution (retention program effectiveness).
    total_customers_count = total_silver_records
    loyalty_tier_distribution = (
        df.groupBy("loyalty_tier")
        .agg(
            count("*").alias("customer_count"),
            spark_round(sum("total_revenue_usd"), 2).alias("total_revenue_usd"),
            spark_round(100.0 * count("*") / lit(total_customers_count), 2).alias("pct_of_customer_base"),
        )
        .orderBy(col("total_revenue_usd").desc())
    )

    # --- 4. Churn risk summary (revenue at risk for retention campaigns).
    churn_risk_summary = (
        df.groupBy("churn_risk_label")
        .agg(
            count("*").alias("customer_count"),
            spark_round(sum("total_revenue_usd"), 2).alias("revenue_at_risk_usd"),
            spark_round(avg("days_since_last_purchase"), 1).alias("avg_days_since_last_purchase"),
        )
        .orderBy(col("revenue_at_risk_usd").desc())
    )

    # --- 5. Acquisition channel performance (marketing ROI view).
    acquisition_channel_performance = (
        df.groupBy("acquisition_channel")
        .agg(
            count("*").alias("customer_count"),
            spark_round(sum("total_revenue_usd"), 2).alias("total_revenue_usd"),
            spark_round(avg("avg_order_value_usd"), 2).alias("avg_order_value_usd"),
            countDistinct("country").alias("countries_reached"),
        )
        .orderBy(col("total_revenue_usd").desc())
    )

    print("Customer summary (by country):")
    customer_summary.show(truncate=False)
    print("Segment performance:")
    segment_performance.show(truncate=False)
    print("Loyalty tier distribution:")
    loyalty_tier_distribution.show(truncate=False)
    print("Churn risk summary:")
    churn_risk_summary.show(truncate=False)
    print("Acquisition channel performance:")
    acquisition_channel_performance.show(truncate=False)

    customer_summary.write.mode("overwrite").parquet(str(CUSTOMER_SUMMARY_DIR))
    segment_performance.write.mode("overwrite").parquet(str(SEGMENT_PERFORMANCE_DIR))
    loyalty_tier_distribution.write.mode("overwrite").parquet(str(LOYALTY_TIER_DIR))
    churn_risk_summary.write.mode("overwrite").parquet(str(CHURN_RISK_DIR))
    acquisition_channel_performance.write.mode("overwrite").parquet(str(ACQUISITION_CHANNEL_DIR))

    # --- 6. Data quality scorecard: governance view for the data platform
    # team, built from the Silver layer's own DQ summary metadata. Written
    # as plain JSON (not parquet) since it is a single governance record,
    # not a row-oriented analytical dataset.
    if DQ_SUMMARY_FILE.exists():
        dq_summary = json.loads(DQ_SUMMARY_FILE.read_text(encoding="utf-8"))
        DQ_SCORECARD_DIR.mkdir(parents=True, exist_ok=True)
        (DQ_SCORECARD_DIR / "dq_scorecard.json").write_text(
            json.dumps(dq_summary, indent=2), encoding="utf-8"
        )
        print("Data quality scorecard:")
        print(json.dumps(dq_summary, indent=2))
    else:
        print(f"WARNING: DQ summary not found at {DQ_SUMMARY_FILE}, skipping scorecard.")

    print(f"Gold output root: {GOLD_ROOT}")
    print("GOLD TRANSFORMATION PASSED")

    spark.stop()


if __name__ == "__main__":
    main()
