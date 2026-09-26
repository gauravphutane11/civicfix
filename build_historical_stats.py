import csv
import json
from collections import Counter, defaultdict

src = "dataset/civicfix_nyc311_mapped.csv"
out = "backend/data/nyc311_historical_stats.json"

category_counts = Counter()
category_descriptors = defaultdict(Counter)
category_boroughs = defaultdict(Counter)
category_status = defaultdict(Counter)
category_months = defaultdict(Counter)

total = 0

with open(src, encoding="utf-8", errors="replace") as f:
    reader = csv.DictReader(f)

    for row in reader:
        category = row.get("CivicFix Category") or "road_infrastructure"
        descriptor = row.get("Descriptor") or "Unknown"
        borough = row.get("Borough") or "Unknown"
        status = row.get("Status") or "Unknown"
        created = row.get("Created Date") or ""

        month = created[:7] if len(created) >= 7 else "Unknown"

        category_counts[category] += 1
        category_descriptors[category][descriptor] += 1
        category_boroughs[category][borough] += 1
        category_status[category][status] += 1
        category_months[category][month] += 1

        total += 1

stats = {
    "source": "NYC 311 Service Requests",
    "source_file": "civicfix_nyc311_sample.csv",
    "records": total,
    "source_period": "2019",
    "categories": dict(category_counts),
    "top_descriptors": {
        category: dict(counter.most_common(10))
        for category, counter in category_descriptors.items()
    },
    "borough_distribution": {
        category: dict(counter)
        for category, counter in category_boroughs.items()
    },
    "status_distribution": {
        category: dict(counter)
        for category, counter in category_status.items()
    },
    "monthly_distribution": {
        category: dict(sorted(counter.items()))
        for category, counter in category_months.items()
    }
}

with open(out, "w", encoding="utf-8") as f:
    json.dump(stats, f, indent=2)

print("Created:", out)
print("Records summarized:", total)
