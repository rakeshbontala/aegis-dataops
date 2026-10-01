from pathlib import Path
import json

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = PROJECT_ROOT / "config"

# Must match the Silver output schema produced by
# pipelines/silver_transformation.py (Customer 360 pipeline).
schema_contract = {
    "pipeline": "customer_gold_pipeline",
    "source": "silver.customers",
    "expected_columns": [
        "customer_id",
        "customer_name",
        "email",
        "phone",
        "gender",
        "date_of_birth",
        "country",
        "state_province",
        "city",
        "postal_code",
        "registration_date",
        "registration_channel",
        "customer_segment",
        "loyalty_tier",
        "status",
        "marketing_opt_in",
        "preferred_payment_method",
        "preferred_channel",
        "total_orders",
        "total_revenue_local",
        "total_revenue_usd",
        "avg_order_value_local",
        "avg_order_value_usd",
        "first_purchase_date",
        "last_purchase_date",
        "lifetime_value_local",
        "lifetime_value_usd",
        "churn_risk_score",
        "churn_risk_label",
        "returns_count",
        "support_tickets_count",
        "currency",
        "acquisition_channel",
        "data_source_system",
        "last_updated_at",
        "customer_tenure_days",
        "days_since_last_purchase",
        "is_high_value_customer",
        "is_valid_email",
        "data_quality_flags"
    ],
    "allow_new_columns": False
}

output_file = CONFIG_DIR / "customer_schema_contract.json"
output_file.write_text(json.dumps(schema_contract, indent=2), encoding="utf-8")

print(f"Created: {output_file}")
print(json.dumps(schema_contract, indent=2))
print("SCHEMA CONTRACT CREATED")
