from pathlib import Path

from pyspark.sql import SparkSession
from pyspark.sql.functions import col, count, sum, when


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SILVER_DIR = PROJECT_ROOT / "data" / "silver" / "customers"
GOLD_DIR = PROJECT_ROOT / "data" / "gold" / "customer_summary"


def main() -> None:
    spark = (
        SparkSession.builder
        .appName("Aegis-Gold-Transformation")
        .master("local[2]")
        .getOrCreate()
    )

    spark.sparkContext.setLogLevel("WARN")

    print(f"Reading Silver: {SILVER_DIR}")

    df = spark.read.parquet(str(SILVER_DIR))

    print(f"Silver records: {df.count()}")

    gold_df = (
        df.groupBy("country")
        .agg(
            count("*").alias("total_customers"),
            sum(when(col("status") == "ACTIVE", 1).otherwise(0)).alias("active_customers"),
            sum(when(col("status") == "INACTIVE", 1).otherwise(0)).alias("inactive_customers"),
        )
        .orderBy("country")
    )

    print("Gold schema:")
    gold_df.printSchema()

    print("Gold data:")
    gold_df.show(truncate=False)

    gold_df.write.mode("overwrite").parquet(str(GOLD_DIR))

    print(f"Gold output: {GOLD_DIR}")
    print("GOLD TRANSFORMATION PASSED")

    spark.stop()


if __name__ == "__main__":
    main()
