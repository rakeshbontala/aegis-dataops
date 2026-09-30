from pathlib import Path

from pyspark.sql import SparkSession
from pyspark.sql.functions import col, trim, upper


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BRONZE_DIR = PROJECT_ROOT / "data" / "bronze" / "customers"
SILVER_DIR = PROJECT_ROOT / "data" / "silver" / "customers"


def main() -> None:
    spark = (
        SparkSession.builder
        .appName("Aegis-Silver-Transformation")
        .master("local[2]")
        .getOrCreate()
    )

    spark.sparkContext.setLogLevel("WARN")

    print(f"Reading Bronze: {BRONZE_DIR}")

    df = spark.read.parquet(str(BRONZE_DIR))

    print(f"Bronze records: {df.count()}")

    silver_df = (
        df
        .withColumn("customer_name", trim(col("customer_name")))
        .withColumn("country", upper(trim(col("country"))))
        .withColumn("status", upper(trim(col("status"))))
        .filter(col("customer_id").isNotNull())
        .dropDuplicates(["customer_id"])
    )

    print("Silver schema:")
    silver_df.printSchema()

    print(f"Silver records: {silver_df.count()}")

    silver_df.write.mode("overwrite").parquet(str(SILVER_DIR))

    print(f"Silver output: {SILVER_DIR}")
    print("SILVER TRANSFORMATION PASSED")

    spark.stop()


if __name__ == "__main__":
    main()
