"""
Generates two CSV files you can upload through /docs to demo the API
without needing real production data:

  seed_data/defects.csv   -> upload to /projects/{id}/defects/upload
  seed_data/dataset.csv   -> upload to /projects/{id}/dataset/upload

Run:
    python seed.py
"""
import os
import random
from datetime import date, timedelta

import pandas as pd
from faker import Faker

fake = Faker()
random.seed(42)
Faker.seed(42)

OUT_DIR = "seed_data"
os.makedirs(OUT_DIR, exist_ok=True)


def make_defects(n=60) -> pd.DataFrame:
    severities = ["critical", "high", "medium", "low"]
    statuses = ["open", "in_progress", "resolved", "closed"]
    modules = ["checkout", "auth", "search", "notifications", "billing"]

    rows = []
    for i in range(n):
        created = date.today() - timedelta(days=random.randint(1, 90))
        status = random.choices(statuses, weights=[15, 10, 35, 40])[0]
        resolved = None
        if status in ("resolved", "closed"):
            resolved = created + timedelta(days=random.randint(1, 14))

        rows.append({
            "external_id": f"PROJ-{1000 + i}",
            "title": fake.sentence(nb_words=6),
            "severity": random.choices(severities, weights=[10, 25, 40, 25])[0],
            "status": status,
            "module": random.choice(modules),
            "created_date": created.isoformat(),
            "resolved_date": resolved.isoformat() if resolved else "",
            "reopened_count": random.choices([0, 1, 2], weights=[80, 15, 5])[0],
        })
    return pd.DataFrame(rows)


def make_dataset(n=500) -> pd.DataFrame:
    """A fake 'orders' dataset with intentional quality issues to detect."""
    rows = []
    for i in range(n):
        customer_id = fake.uuid4() if random.random() > 0.08 else None  # ~8% nulls
        amount = round(random.gauss(50, 15), 2)
        if random.random() < 0.01:
            amount = 5000  # outlier
        rows.append({
            "order_id": i + 1,
            "customer_id": customer_id,
            "amount": amount,
            "region": random.choice(["EU", "US", "APAC", None]),
            "order_date": (date.today() - timedelta(days=random.randint(0, 60))).isoformat(),
        })

    df = pd.DataFrame(rows)
    # inject some duplicate rows on purpose
    dupes = df.sample(10, random_state=1)
    df = pd.concat([df, dupes], ignore_index=True)
    return df


if __name__ == "__main__":
    defects_df = make_defects()
    dataset_df = make_dataset()

    defects_path = os.path.join(OUT_DIR, "defects.csv")
    dataset_path = os.path.join(OUT_DIR, "dataset.csv")

    defects_df.to_csv(defects_path, index=False)
    dataset_df.to_csv(dataset_path, index=False)

    print(f"Wrote {len(defects_df)} defects to {defects_path}")
    print(f"Wrote {len(dataset_df)} dataset rows to {dataset_path}")
    print("\nNext steps:")
    print("1. Start the API: uvicorn app.main:app --reload")
    print("2. Open http://127.0.0.1:8000/docs")
    print("3. POST /projects to create a project, note its id")
    print("4. Upload defects.csv and dataset.csv via the upload endpoints")
    print("5. GET /projects/{id}/readiness to see the combined score")
