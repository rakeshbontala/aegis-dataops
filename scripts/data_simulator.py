from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "data" / "raw"


def generate_customers() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"customer_id": 1001, "customer_name": "Arun Kumar", "country": "India", "status": "ACTIVE"},
            {"customer_id": 1002, "customer_name": "Priya Sharma", "country": "India", "status": "ACTIVE"},
            {"customer_id": 1003, "customer_name": "John Smith", "country": "USA", "status": "ACTIVE"},
            {"customer_id": 1004, "customer_name": "Emily Davis", "country": "USA", "status": "INACTIVE"},
            {"customer_id": 1005, "customer_name": "David Wilson", "country": "UK", "status": "ACTIVE"},
        ]
    )


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    customers = generate_customers()
    output_file = RAW_DIR / "customers.csv"

    customers.to_csv(output_file, index=False)

    print(f"Created: {output_file}")
    print(f"Records: {len(customers)}")
    print(f"Columns: {list(customers.columns)}")


if __name__ == "__main__":
    main()
