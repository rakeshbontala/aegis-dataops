from pathlib import Path
from datetime import datetime, timezone
import uuid

from pyspark.sql import SparkSession
from pyspark.sql.functions import lit


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

    # Bronze = raw data as-is + ingestion lineage metadata. No business
    # cleansing happens here; that is the Silver layer's responsibility.
    ingestion_timestamp = datetime.now(timezone.utc).isoformat()
    batch_id = str(uuid.uuid4())

    bronze_df = (
        df
        .withColumn("ingestion_timestamp", lit(ingestion_timestamp))
        .withColumn("source_file_name", lit(RAW_FILE.name))
        .withColumn("ingestion_batch_id", lit(batch_id))
    )

    bronze_df.write.mode("overwrite").parquet(str(BRONZE_DIR))

    print(f"Bronze output: {BRONZE_DIR}")
    print(f"Ingestion batch_id: {batch_id}")
    print("BRONZE INGESTION PASSED")

    spark.stop()


if __name__ == "__main__":
    main()
