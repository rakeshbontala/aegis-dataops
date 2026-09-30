import json
from pathlib import Path

from pyspark.sql import SparkSession
from pyspark.sql.functions import col, upper


BEFORE_GOLD = Path(
    "data/sandbox/recovery/before/customer_summary_gold"
)

EXECUTED_GOLD = Path(
    "data/sandbox/recovery/executed/REC-002/customer_summary_gold"
)

OUTPUT_FILE = Path(
    "data/sandbox/recovery/verification/post_execution_data_verification.json"
)


spark = (
    SparkSession.builder
    .appName("AEGIS-PostExecutionDataVerification")
    .master("local[2]")
    .getOrCreate()
)

spark.sparkContext.setLogLevel("ERROR")


before_df = spark.read.parquet(str(BEFORE_GOLD))
executed_df = spark.read.parquet(str(EXECUTED_GOLD))


expected_columns = [
    "country",
    "total_customers",
    "active_customers",
    "inactive_customers",
]

before_columns = before_df.columns
executed_columns = executed_df.columns

schema_match = before_columns == executed_columns


before_count = before_df.count()
executed_count = executed_df.count()

row_count_match = before_count == executed_count


before_normalized = (
    before_df
    .select(
        upper(col("country")).alias("country"),
        col("total_customers"),
        col("active_customers"),
        col("inactive_customers"),
    )
)

executed_normalized = (
    executed_df
    .select(
        upper(col("country")).alias("country"),
        col("total_customers"),
        col("active_customers"),
        col("inactive_customers"),
    )
)


before_records = {
    tuple(row)
    for row in before_normalized.collect()
}

executed_records = {
    tuple(row)
    for row in executed_normalized.collect()
}


added_records = executed_records - before_records
removed_records = before_records - executed_records

business_values_match = (
    len(added_records) == 0
    and len(removed_records) == 0
)


record = {
    "verification_scope": "POST_EXECUTION_DATA",
    "verification_status": (
        "PASSED"
        if schema_match
        and row_count_match
        and business_values_match
        else "FAILED"
    ),
    "checks": {
        "schema_match": schema_match,
        "row_count_match": row_count_match,
        "business_values_match": business_values_match,
    },
    "before": {
        "row_count": before_count,
        "columns": before_columns,
    },
    "executed": {
        "row_count": executed_count,
        "columns": executed_columns,
    },
    "differences": {
        "added_records": len(added_records),
        "removed_records": len(removed_records),
    },
}


OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

with OUTPUT_FILE.open("w", encoding="utf-8") as f:
    json.dump(record, f, indent=2)


print("POST-EXECUTION DATA VERIFICATION")
print(json.dumps(record, indent=2))
print(f"Saved to: {OUTPUT_FILE}")


spark.stop()

if record["verification_status"] != "PASSED":
    raise SystemExit(1)
