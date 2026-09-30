from pathlib import Path
import json

from pyspark.sql import SparkSession


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SILVER_DIR = PROJECT_ROOT / "data" / "silver" / "customers"
CONTRACT_FILE = PROJECT_ROOT / "config" / "customer_schema_contract.json"


def main() -> None:
    with open(CONTRACT_FILE, "r", encoding="utf-8") as file:
        contract = json.load(file)

    expected_columns = contract["expected_columns"]
    allow_new_columns = contract["allow_new_columns"]

    spark = (
        SparkSession.builder
        .appName("Aegis-Schema-Drift-Detector")
        .master("local[2]")
        .getOrCreate()
    )

    spark.sparkContext.setLogLevel("WARN")

    df = spark.read.parquet(str(SILVER_DIR))
    actual_columns = df.columns

    unexpected_columns = [
        column
        for column in actual_columns
        if column not in expected_columns
    ]

    missing_columns = [
        column
        for column in expected_columns
        if column not in actual_columns
    ]

    print("Expected columns:")
    print(expected_columns)

    print("Actual columns:")
    print(actual_columns)

    print("Unexpected columns:")
    print(unexpected_columns)

    print("Missing columns:")
    print(missing_columns)

    if unexpected_columns and not allow_new_columns:
        print("SCHEMA DRIFT DETECTED")
    elif missing_columns:
        print("SCHEMA CONTRACT VIOLATION: MISSING COLUMNS")
    else:
        print("SCHEMA CONTRACT PASSED")

    spark.stop()


if __name__ == "__main__":
    main()
