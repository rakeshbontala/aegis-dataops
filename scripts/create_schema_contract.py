from pathlib import Path
import json

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = PROJECT_ROOT / "config"

schema_contract = {
    "pipeline": "customer_gold_pipeline",
    "source": "silver.customers",
    "expected_columns": [
        "customer_id",
        "customer_name",
        "country",
        "status"
    ],
    "allow_new_columns": False
}

output_file = CONFIG_DIR / "customer_schema_contract.json"
output_file.write_text(json.dumps(schema_contract, indent=2), encoding="utf-8")

print(f"Created: {output_file}")
print(json.dumps(schema_contract, indent=2))
print("SCHEMA CONTRACT CREATED")
