from pathlib import Path
import json

from pyspark.sql import SparkSession


PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Pinned to the contract as it existed for INC-20260930-001, not the live
# (now much larger) config/customer_schema_contract.json - the frozen sandbox
# fixtures below were produced against that original 4-column schema only.
CONTRACT_PATH = (
    PROJECT_ROOT / "data" / "sandbox" / "recovery" / "before" / "schema_contract_snapshot.json"
)

SOURCE_PATH = PROJECT_ROOT / "data" / "sandbox" / "recovery" / "before" / "customers_bronze"

OUTPUT_SILVER = (
    PROJECT_ROOT
    / "data"
    / "sandbox"
    / "recovery"
    / "targeted_rebuild"
    / "customers_silver"
)

OUTPUT_GOLD = (
    PROJECT_ROOT
    / "data"
    / "sandbox"
    / "recovery"
    / "targeted_rebuild"
    / "customer_summary_gold"
)


def main():
    with open(CONTRACT_PATH, "r", encoding="utf-8") as file:
        contract = json.load(file)

    expected_columns = contract["expected_columns"]

    spark = (
        SparkSession.builder
        .appName("AEGIS-Targeted-Recovery")
        .master("local[2]")
        .getOrCreate()
    )

    spark.sparkContext.setLogLevel("ERROR")

    try:
        print("=" * 70)
        print("AEGIS TARGETED RECOVERY")
        print("=" * 70)

        print(f"Source: {SOURCE_PATH}")
        print(f"Expected columns: {expected_columns}")

        source_df = spark.read.parquet(str(SOURCE_PATH))

        print("\nSource schema:")
        source_df.printSchema()

        actual_columns = source_df.columns

        unexpected_columns = [
            column
            for column in actual_columns
            if column not in expected_columns
        ]

        print(f"\nActual columns: {actual_columns}")
        print(f"Unexpected columns: {unexpected_columns}")

        missing_columns = [
            column
            for column in expected_columns
            if column not in actual_columns
        ]

        if missing_columns:
            raise ValueError(
                f"Recovery blocked. Required columns are missing: {missing_columns}"
            )

        # Targeted recovery:
        # Keep only columns approved by the schema contract.
        recovered_silver = source_df.select(*expected_columns)

        recovered_silver = (
            recovered_silver
            .withColumn("customer_name", recovered_silver["customer_name"].cast("string"))
            .withColumn("country", recovered_silver["country"].cast("string"))
            .withColumn("status", recovered_silver["status"].cast("string"))
            .dropDuplicates(["customer_id"])
        )

        recovered_silver.write.mode("overwrite").parquet(str(OUTPUT_SILVER))

        print("\nRecovered Silver schema:")
        recovered_silver.printSchema()

        # Rebuild Gold from the recovered Silver dataset.
        recovered_gold = (
            recovered_silver
            .groupBy("country")
            .count()
            .withColumnRenamed("count", "total_customers")
        )

        from pyspark.sql.functions import sum, when

        active_counts = (
            recovered_silver
            .groupBy("country")
            .agg(
                sum(
                    when(recovered_silver["status"] == "ACTIVE", 1)
                    .otherwise(0)
                ).alias("active_customers"),
                sum(
                    when(recovered_silver["status"] == "INACTIVE", 1)
                    .otherwise(0)
                ).alias("inactive_customers"),
            )
        )

        recovered_gold = (
            recovered_gold
            .join(active_counts, on="country", how="left")
            .orderBy("country")
        )

        recovered_gold.write.mode("overwrite").parquet(str(OUTPUT_GOLD))

        print("\nRecovered Gold data:")
        recovered_gold.show(truncate=False)

        print(f"\nRecovered Silver output: {OUTPUT_SILVER}")
        print(f"Recovered Gold output:   {OUTPUT_GOLD}")

        print("\nTARGETED RECOVERY COMPLETED")
        print("=" * 70)

    finally:
        spark.stop()


if __name__ == "__main__":
    main()
