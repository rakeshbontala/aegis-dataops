from pathlib import Path
import json

from pyspark.sql import SparkSession
from pyspark.sql.functions import col, upper


PROJECT_ROOT = Path(__file__).resolve().parents[2]

BEFORE_GOLD = (
    PROJECT_ROOT
    / "data"
    / "sandbox"
    / "recovery"
    / "before"
    / "customer_summary_gold"
)

AFTER_GOLD = (
    PROJECT_ROOT
    / "data"
    / "sandbox"
    / "recovery"
    / "targeted_rebuild"
    / "customer_summary_gold"
)

VERIFICATION_OUTPUT = (
    PROJECT_ROOT
    / "data"
    / "sandbox"
    / "recovery"
    / "verification"
    / "recovery_verification.json"
)


def normalize_gold(df):
    return (
        df
        .withColumn("country", col("country").cast("string"))
        .withColumn("total_customers", col("total_customers").cast("long"))
        .withColumn("active_customers", col("active_customers").cast("long"))
        .withColumn("inactive_customers", col("inactive_customers").cast("long"))
        .select(
            "country",
            "total_customers",
            "active_customers",
            "inactive_customers",
        )
    )


def main():
    spark = (
        SparkSession.builder
        .appName("AEGIS-Recovery-Verifier")
        .master("local[2]")
        .getOrCreate()
    )

    spark.sparkContext.setLogLevel("ERROR")

    try:
        print("=" * 70)
        print("AEGIS RECOVERY VERIFICATION")
        print("=" * 70)

        before = normalize_gold(
            spark.read.parquet(str(BEFORE_GOLD))
        )

        after = normalize_gold(
            spark.read.parquet(str(AFTER_GOLD))
        )

        before_count = before.count()
        after_count = after.count()

        schema_match = before.columns == after.columns
        row_count_match = before_count == after_count

        before_normalized = (
            before
            .withColumn("country", upper(col("country")))
        )

        after_normalized = (
            after
            .withColumn("country", upper(col("country")))
        )

        before_set = {
            tuple(row)
            for row in before_normalized.collect()
        }

        after_set = {
            tuple(row)
            for row in after_normalized.collect()
        }

        added_records = after_set - before_set
        removed_records = before_set - after_set

        business_values_match = (
            len(added_records) == 0
            and len(removed_records) == 0
        )

        verification_status = (
            "PASSED"
            if schema_match
            and row_count_match
            and business_values_match
            else "FAILED"
        )

        verification_result = {
            "verification_status": verification_status,
            "checks": {
                "schema_match": schema_match,
                "row_count_match": row_count_match,
                "business_values_match": business_values_match,
            },
            "before": {
                "row_count": before_count,
                "columns": before.columns,
            },
            "after": {
                "row_count": after_count,
                "columns": after.columns,
            },
            "differences": {
                "added_records": len(added_records),
                "removed_records": len(removed_records),
            },
        }

        VERIFICATION_OUTPUT.write_text(
            json.dumps(verification_result, indent=2),
            encoding="utf-8",
        )

        print(f"Before Gold rows: {before_count}")
        print(f"After Gold rows:  {after_count}")
        print(f"Schema match:     {schema_match}")
        print(f"Row count match:  {row_count_match}")
        print(f"Business values match: {business_values_match}")
        print(f"Added records:         {len(added_records)}")
        print(f"Removed records:       {len(removed_records)}")
        print(f"\nVERIFICATION STATUS: {verification_status}")
        print(f"Result saved to: {VERIFICATION_OUTPUT}")
        print("=" * 70)

    finally:
        spark.stop()


if __name__ == "__main__":
    main()
