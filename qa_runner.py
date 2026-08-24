"""
Production QA Audit Script for Shopify Taxonomy Classifier.
Run from project root: python qa_runner.py
"""
import sys
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django
django.setup()

import csv
import io
import math

import pandas as pd

PASS = "PASS"
FAIL = "FAIL"

failures = []


def check(condition, label, detail=""):
    if condition:
        print(f"  [PASS] {label}")
    else:
        print(f"  [FAIL] {label} {detail}")
        failures.append(label)


# ── TEST 1: _clean_str edge cases ─────────────────────────────────────────────
print("\n=== TEST 1: _clean_str edge cases ===")
from dashboard.views import _clean_str

check(_clean_str(None) == "", "None -> empty string")
check(_clean_str(float("nan")) == "", "float NaN -> empty string")
check(_clean_str(pd.NA) == "", "pd.NA -> empty string")
check(_clean_str(pd.NaT) == "", "pd.NaT -> empty string")
check(_clean_str("  hello  ") == "hello", "strips whitespace")
check(_clean_str(42) == "42", "int -> string")
check(_clean_str("") == "", "empty string stays empty")

# ── TEST 2: CSV Parsing accuracy ──────────────────────────────────────────────
print("\n=== TEST 2: CSV Parsing ===")
csv_lines = [
    "title,description,product number,category,materials,image 1",
    "Wooden Chair,Ergonomic oak chair,SKU-001,Furniture,Oak Wood,https://x.com/img.jpg",
    ",Missing Title Row,SKU-002,Office,,",   # should be skipped
    ",,,,,,",                                  # all empty — should be skipped
    "Steel Cabinet,Metal storage unit,SKU-003,,Steel,",
]
csv_text = "\n".join(csv_lines)
reader = csv.reader(io.StringIO(csv_text))
header = next(reader)
hmap = {str(h).strip().lower(): i for i, h in enumerate(header)}

def get_col(row, *names):
    for nm in names:
        idx = hmap.get(nm.lower())
        if idx is not None and idx < len(row):
            v = row[idx].strip()
            if v:
                return v
    return ""

rows = []
for row in reader:
    if not any(c.strip() for c in row):
        continue
    title = get_col(row, "title", "product name", "name")
    if title:
        rows.append(title)

check(len(rows) == 2, f"CSV parsed 2 valid rows (got {len(rows)})")
check("Wooden Chair" in rows, "First valid row captured")
check("Steel Cabinet" in rows, "Second valid row captured")

# ── TEST 3: End-to-end batch ──────────────────────────────────────────────────
print("\n=== TEST 3: End-to-End Batch Classification ===")
from products.models import Product
from classification.models import Batch, ClassificationResult
from classification.tasks.process_batch import execute_batch_processing

p1 = Product.objects.create(
    title="QA Ergonomic Mesh Office Chair Final",
    description="Black mesh office chair with lumbar support, adjustable height.",
    status="PENDING"
)
p2 = Product.objects.create(
    title="QA Stainless Water Bottle Final",
    description="500ml insulated stainless steel flask, keeps cold 24h.",
    status="PENDING"
)
batch = Batch.objects.create(
    name="QA Final Audit Batch",
    total_products=2,
    pending_products=2,
    status="PROCESSING"
)
res = execute_batch_processing(batch.id, [p1.id, p2.id])
batch.refresh_from_db()
p1.refresh_from_db()
p2.refresh_from_db()

check(batch.status == "COMPLETED", f"Batch status=COMPLETED (got '{batch.status}')")
check(batch.pending_products == 0, f"No pending items remaining (got {batch.pending_products})")
check(batch.completed_products == 2, f"2 products completed (got {batch.completed_products})")
check(p1.status in ("COMPLETED", "REVIEW"), f"P1 status={p1.status}")
check(p2.status in ("COMPLETED", "REVIEW"), f"P2 status={p2.status}")

# ── TEST 4: ClassificationResult persisted ────────────────────────────────────
print("\n=== TEST 4: ClassificationResult Persistence ===")
r1 = ClassificationResult.objects.filter(product=p1).first()
r2 = ClassificationResult.objects.filter(product=p2).first()

check(r1 is not None, "ClassificationResult created for P1")
check(r2 is not None, "ClassificationResult created for P2")
if r1:
    check(r1.confidence_score > 0, f"P1 confidence score > 0 (got {r1.confidence_score})")
    check(r1.predicted_category is not None, f"P1 category assigned: {r1.predicted_category}")
if r2:
    check(r2.confidence_score > 0, f"P2 confidence score > 0 (got {r2.confidence_score})")

# ── TEST 5: Batch Resume preserves counters ───────────────────────────────────
print("\n=== TEST 5: Batch Resume (is_resume=True) ===")
p3 = Product.objects.create(
    title="QA Resume Pending Product",
    description="This product was left pending after a partial run.",
    status="FAILED"
)
batch2 = Batch.objects.create(
    name="QA Resume Batch",
    total_products=3,
    pending_products=1,
    completed_products=2,
    failed_products=0,
    status="FAILED",
)
res2 = execute_batch_processing(batch2.id, [p3.id], is_resume=True)
batch2.refresh_from_db()
p3.refresh_from_db()

check(batch2.status == "COMPLETED", f"Resumed batch ends COMPLETED (got {batch2.status})")
check(batch2.completed_products >= 3, f"Total completed>=3 (got {batch2.completed_products})")
check(p3.status in ("COMPLETED", "REVIEW"), f"P3 processed by resume (got {p3.status})")

# ── TEST 6: Dashboard stats ───────────────────────────────────────────────────
print("\n=== TEST 6: Dashboard Stats ===")
from dashboard.services.stats import get_dashboard_stats
s = get_dashboard_stats()

check(s["total_products"] > 0, f"total_products > 0 (got {s['total_products']})")
check(s["completed_products"] > 0, f"completed_products > 0 (got {s['completed_products']})")
check(s["total_classifications"] > 0, f"total_classifications > 0 (got {s['total_classifications']})")
check(isinstance(s["completion_rate_percentage"], float), "completion_rate_percentage is float")

# ── TEST 7: API StatsAPIView (single aggregate) ───────────────────────────────
print("\n=== TEST 7: API StatsAPIView aggregate ===")
from api.views import StatsAPIView
from rest_framework.test import APIRequestFactory
factory = APIRequestFactory()
request = factory.get("/api/stats/")
view = StatsAPIView.as_view()
response = view(request)
check(response.status_code == 200, f"StatsAPIView returns 200 (got {response.status_code})")
check("total_products" in response.data, "total_products in response")
check("avg_confidence" in response.data, "avg_confidence in response")

# ── SUMMARY ───────────────────────────────────────────────────────────────────
print()
print("=" * 50)
if failures:
    print(f"  {len(failures)} TESTS FAILED:")
    for f in failures:
        print(f"    - {f}")
    sys.exit(1)
else:
    print(f"  ALL TESTS PASSED ({7} test groups)")
print("=" * 50)
