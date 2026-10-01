"""Generates the raw customer master dataset for the E-commerce/Retail
"Customer 360" pipeline (data/raw/customers.csv).

Produces ~1000 realistic records across a global customer base, with
common source-system data-quality issues deliberately injected so the
downstream Silver layer has real cleansing/validation work to do:

- Duplicate customer_id rows (CRM merge / re-sync), resolved in Silver by
  keeping the latest `last_updated_at`.
- Inconsistent text casing/whitespace in country/status/segment (multiple
  source systems: CRM_LEGACY, CRM_NEW, POS, MOBILE_APP).
- Missing / malformed email addresses.
- Missing loyalty_tier and purchase dates for never-purchased customers.
- Negative revenue values (refund/chargeback data entry errors).
- Out-of-range churn_risk_score values (upstream scoring bugs).
- avg_order_value that doesn't reconcile with total_revenue/total_orders.

Deterministic (fixed random seed) so re-runs are reproducible.
"""

from __future__ import annotations

import random
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "data" / "raw"

RECORD_COUNT = 1000
SEED = 42

FIRST_NAMES = [
    "Arun", "Priya", "John", "Emily", "David", "Sophia", "Wei", "Mei",
    "Carlos", "Maria", "Ahmed", "Fatima", "Lucas", "Isabella", "Hans",
    "Greta", "Oliver", "Charlotte", "Raj", "Anita", "James", "Linda",
    "Mohammed", "Layla", "Pedro", "Camila", "Ivan", "Olga", "Kenji",
    "Yuki", "Liam", "Grace", "Noah", "Ava", "William", "Mia", "Ethan",
    "Zara", "Ravi", "Deepa",
]
LAST_NAMES = [
    "Kumar", "Sharma", "Smith", "Davis", "Wilson", "Johnson", "Chen",
    "Wang", "Garcia", "Rodriguez", "Khan", "Ali", "Silva", "Santos",
    "Mueller", "Schmidt", "Brown", "Taylor", "Patel", "Singh", "Clark",
    "Lewis", "Hassan", "Ibrahim", "Alves", "Costa", "Petrov", "Ivanova",
    "Tanaka", "Suzuki", "Walker", "Young", "Anderson", "Thomas", "Moore",
    "Jackson", "White", "Reddy", "Nair", "Gupta",
]

COUNTRIES_CANONICAL = [
    "India", "USA", "UK", "Germany", "France", "Brazil", "Australia",
    "Canada", "UAE", "Singapore",
]
# Realistic casing/whitespace noise injected by different source systems.
COUNTRY_VARIANTS = {
    "India": ["India", "india", "INDIA", " India", "India "],
    "USA": ["USA", "usa", "U.S.A", "Usa "],
    "UK": ["UK", "uk", " UK", "U.K."],
    "Germany": ["Germany", "germany", "GERMANY "],
    "France": ["France", "france", " France"],
    "Brazil": ["Brazil", "brazil", "BRAZIL"],
    "Australia": ["Australia", "australia ", "AUSTRALIA"],
    "Canada": ["Canada", "canada", " Canada"],
    "UAE": ["UAE", "uae", "U.A.E"],
    "Singapore": ["Singapore", "singapore", "SINGAPORE "],
}
STATES_BY_COUNTRY = {
    "India": ["Maharashtra", "Karnataka", "Delhi", "Tamil Nadu", "Telangana"],
    "USA": ["California", "Texas", "New York", "Florida", "Illinois"],
    "UK": ["England", "Scotland", "Wales", "Northern Ireland"],
    "Germany": ["Bavaria", "Berlin", "Hesse", "Saxony"],
    "France": ["Ile-de-France", "Provence", "Occitanie"],
    "Brazil": ["Sao Paulo", "Rio de Janeiro", "Bahia"],
    "Australia": ["New South Wales", "Victoria", "Queensland"],
    "Canada": ["Ontario", "Quebec", "British Columbia"],
    "UAE": ["Dubai", "Abu Dhabi", "Sharjah"],
    "Singapore": ["Central", "West Region", "East Region"],
}
CITIES_BY_COUNTRY = {
    "India": ["Mumbai", "Bengaluru", "Delhi", "Chennai", "Hyderabad"],
    "USA": ["Los Angeles", "Austin", "New York City", "Miami", "Chicago"],
    "UK": ["London", "Manchester", "Edinburgh", "Cardiff"],
    "Germany": ["Munich", "Berlin", "Frankfurt", "Dresden"],
    "France": ["Paris", "Marseille", "Toulouse"],
    "Brazil": ["Sao Paulo", "Rio de Janeiro", "Salvador"],
    "Australia": ["Sydney", "Melbourne", "Brisbane"],
    "Canada": ["Toronto", "Montreal", "Vancouver"],
    "UAE": ["Dubai", "Abu Dhabi", "Sharjah"],
    "Singapore": ["Singapore"],
}
CURRENCY_BY_COUNTRY = {
    "India": "INR", "USA": "USD", "UK": "GBP", "Germany": "EUR",
    "France": "EUR", "Brazil": "USD", "Australia": "USD", "Canada": "USD",
    "UAE": "USD", "Singapore": "USD",
}
# Must match pipelines/silver_transformation.py FX_TO_USD. Used here only to
# generate local-currency amounts that are comparable in USD-equivalent terms
# across countries (mirrors how a real order-management system would store
# amounts already denominated in the customer's local currency).
FX_TO_USD = {"USD": 1.0, "EUR": 1.08, "GBP": 1.27, "INR": 0.012}

SEGMENT_CASING_NOISE = ["PREMIUM", "premium", "Premium", "STANDARD",
                        "standard", "BASIC", "basic", "VIP", "vip"]
LOYALTY_TIERS = ["PLATINUM", "GOLD", "SILVER", "BRONZE"]
STATUS_CASING_NOISE = ["ACTIVE", "active", "Active", "INACTIVE", "inactive",
                       "SUSPENDED", "suspended", "CHURNED", "churned"]
REGISTRATION_CHANNELS = ["Web", "Mobile App", "Retail Store", "Call Center", "Marketplace"]
PREFERRED_PAYMENT_METHODS = ["Credit Card", "PayPal", "UPI", "Wallet", "COD", "Bank Transfer"]
PREFERRED_CHANNELS = ["Web", "Mobile", "Store"]
ACQUISITION_CHANNELS = ["Organic", "Paid Search", "Social Media", "Referral",
                        "Affiliate", "Email Campaign"]
DATA_SOURCE_SYSTEMS = ["CRM_LEGACY", "CRM_NEW", "POS", "MOBILE_APP"]
GENDERS = ["M", "F", "Other"]


def _random_date(rng: random.Random, start: date, end: date) -> date:
    delta_days = (end - start).days
    return start + timedelta(days=rng.randint(0, max(delta_days, 0)))


def _make_email(rng: random.Random, first: str, last: str, broken: bool) -> str | None:
    domain = rng.choice(["gmail.com", "outlook.com", "yahoo.com", "corp-mail.com"])
    local = f"{first.lower()}.{last.lower()}{rng.randint(1, 999)}"
    if broken:
        # Simulate common malformed-email data entry errors.
        return rng.choice([
            f"{local}{domain}",       # missing '@'
            f"{local}@",              # missing domain
            f"{local}@{domain.split('.')[0]}",  # missing TLD
            "",
        ])
    return f"{local}@{domain}"


def generate_customers() -> pd.DataFrame:
    rng = random.Random(SEED)
    np.random.seed(SEED)

    today = date(2026, 9, 1)
    rows: list[dict] = []

    base_ids = list(range(100001, 100001 + RECORD_COUNT))

    for customer_id in base_ids:
        country = rng.choice(COUNTRIES_CANONICAL)
        country_raw = rng.choice(COUNTRY_VARIANTS[country])
        state = rng.choice(STATES_BY_COUNTRY[country])
        city = rng.choice(CITIES_BY_COUNTRY[country])
        currency = CURRENCY_BY_COUNTRY[country]

        first = rng.choice(FIRST_NAMES)
        last = rng.choice(LAST_NAMES)
        customer_name = f"{first} {last}"

        dob = _random_date(rng, date(1955, 1, 1), date(2006, 1, 1))
        registration_dt = _random_date(rng, date(2018, 1, 1), date(2026, 6, 1))

        segment = rng.choices(
            SEGMENT_CASING_NOISE,
            weights=[18, 6, 4, 22, 10, 22, 6, 10, 2],
        )[0]

        # ~6% of records have no loyalty tier recorded yet (new sign-ups).
        loyalty_tier = None if rng.random() < 0.06 else rng.choice(LOYALTY_TIERS)

        status_raw = rng.choices(
            STATUS_CASING_NOISE,
            weights=[40, 10, 8, 14, 4, 6, 2, 10, 6],
        )[0]

        total_orders = max(0, int(np.random.poisson(6)))
        has_purchased = total_orders > 0

        if has_purchased:
            first_purchase = _random_date(rng, registration_dt, today)
            last_purchase = _random_date(rng, first_purchase, today)
            avg_order_value_usd_equivalent = rng.uniform(15, 500)
            avg_order_value_local = round(avg_order_value_usd_equivalent / FX_TO_USD[currency], 2)
            total_revenue_local = round(avg_order_value_local * total_orders, 2)

            # ~4% of records: data entry error introduces negative revenue.
            if rng.random() < 0.04:
                total_revenue_local = round(-abs(total_revenue_local) * 0.1, 2)

            # ~5% of records: avg_order_value doesn't reconcile with
            # total_revenue / total_orders (stale snapshot field).
            if rng.random() < 0.05:
                avg_order_value_local = round(avg_order_value_local * rng.uniform(1.5, 2.5), 2)
        else:
            first_purchase = None
            last_purchase = None
            avg_order_value_local = 0.0
            total_revenue_local = 0.0

        lifetime_value_local = round(total_revenue_local * rng.uniform(1.0, 1.3), 2)

        churn_risk_score = int(np.clip(np.random.normal(40, 25), -100, 200))
        # ~3% of records: upstream scoring bug produces out-of-range scores.
        if rng.random() < 0.03:
            churn_risk_score = rng.choice([-15, 125, 150, -40])

        returns_count = int(np.random.poisson(0.6)) if has_purchased else 0
        support_tickets_count = int(np.random.poisson(0.4))

        broken_email = rng.random() < 0.05
        missing_email = rng.random() < 0.08
        email = None if missing_email else _make_email(rng, first, last, broken_email)

        phone = None if rng.random() < 0.10 else f"+{rng.randint(1, 99)}-{rng.randint(1000000000, 9999999999)}"

        marketing_opt_in = rng.random() < 0.55

        last_updated_at = datetime.combine(
            _random_date(rng, registration_dt, today), datetime.min.time()
        ) + timedelta(hours=rng.randint(0, 23), minutes=rng.randint(0, 59))

        rows.append({
            "customer_id": customer_id,
            "customer_name": customer_name,
            "email": email,
            "phone": phone,
            "gender": rng.choice(GENDERS) if rng.random() > 0.03 else None,
            "date_of_birth": dob.isoformat(),
            "country": country_raw,
            "state_province": state,
            "city": city,
            "postal_code": f"{rng.randint(10000, 99999)}",
            "registration_date": registration_dt.isoformat(),
            "registration_channel": rng.choice(REGISTRATION_CHANNELS),
            "customer_segment": segment,
            "loyalty_tier": loyalty_tier,
            "status": status_raw,
            "marketing_opt_in": marketing_opt_in,
            "preferred_payment_method": rng.choice(PREFERRED_PAYMENT_METHODS),
            "preferred_channel": rng.choice(PREFERRED_CHANNELS),
            "total_orders": total_orders,
            "total_revenue": total_revenue_local,
            "avg_order_value": avg_order_value_local,
            "first_purchase_date": first_purchase.isoformat() if first_purchase else None,
            "last_purchase_date": last_purchase.isoformat() if last_purchase else None,
            "lifetime_value": lifetime_value_local,
            "churn_risk_score": churn_risk_score,
            "returns_count": returns_count,
            "support_tickets_count": support_tickets_count,
            "currency": currency,
            "acquisition_channel": rng.choice(ACQUISITION_CHANNELS),
            "data_source_system": rng.choice(DATA_SOURCE_SYSTEMS),
            "last_updated_at": last_updated_at.isoformat(sep=" "),
        })

    df = pd.DataFrame(rows)

    # Inject ~3% duplicate customer_id rows (simulating a CRM re-sync that
    # re-sent slightly stale copies of already-seen customers). The Silver
    # layer must keep only the latest version per customer_id.
    duplicate_sample = df.sample(n=int(RECORD_COUNT * 0.03), random_state=SEED)
    stale_duplicates = duplicate_sample.copy()
    stale_duplicates["last_updated_at"] = stale_duplicates["last_updated_at"].apply(
        lambda ts: (datetime.fromisoformat(ts) - timedelta(days=rng.randint(1, 30))).isoformat(sep=" ")
    )
    stale_duplicates["data_source_system"] = "CRM_LEGACY"

    df = pd.concat([df, stale_duplicates], ignore_index=True)
    df = df.sample(frac=1.0, random_state=SEED).reset_index(drop=True)

    return df


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    customers = generate_customers()
    output_file = RAW_DIR / "customers.csv"

    customers.to_csv(output_file, index=False)

    print(f"Created: {output_file}")
    print(f"Records (incl. injected duplicates): {len(customers)}")
    print(f"Unique customer_id count: {customers['customer_id'].nunique()}")
    print(f"Columns ({len(customers.columns)}): {list(customers.columns)}")


if __name__ == "__main__":
    main()
