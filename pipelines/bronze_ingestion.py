from pathlib import Path

from pyspark.sql import SparkSession


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_FILE = PROJECT_ROOT / "data" / "raw" / "customers.csv"
BRONZE_DIR = PROJECT_ROOT / "data" / "bronze" / "customers"


def main() -> None:
    spark = (
        SparkSession.builder
        .appName("Aegis-Bronze-Ingestion")
        .master("local[2]")
        .getOrCreate()
    )

    spark.sparkContext.setLogLevel("WARN")

    print(f"Reading source: {RAW_FILE}")

    df = spark.read.option("header", True).option("inferSchema", True).csv(str(RAW_FILE))

    print("Source schema:")
    df.printSchema()

    print(f"Source records: {df.count()}")

    df.write.mode("overwrite").parquet(str(BRONZE_DIR))

    print(f"Bronze output: {BRONZE_DIR}")
    print("BRONZE INGESTION PASSED")

    spark.stop()


if __name__ == "__main__":
    main()
