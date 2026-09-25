import csv

src = "dataset/civicfix_nyc311_sample.csv"
out = "dataset/civicfix_nyc311_mapped.csv"

def civicfix_category(row):
    t = row["Complaint Type"]
    d = (row["Descriptor"] or "").lower()

    if t == "Street Condition" and "pothole" in d:
        return "pothole"

    if t == "Street Light Condition":
        return "streetlight"

    if t in {"Dirty Conditions", "Missed Collection (All Materials)"}:
        return "garbage"

    if t in {"Sewer", "Standing Water"}:
        return "drainage"

    if t in {"Water System", "WATER LEAK", "Water Quality", "Drinking Water"}:
        return "water_supply"

    if t in {
        "Street Condition",
        "Sidewalk Condition",
        "Root/Sewer/Sidewalk Condition",
        "Street Sign - Damaged",
        "Street Sign - Missing",
        "Street Sign - Dangling",
        "DEP Street Condition",
        "DEP Sidewalk Condition"
    }:
        return "road_infrastructure"

    return "road_infrastructure"

with open(src, encoding="utf-8", errors="replace") as fin:
    reader = csv.DictReader(fin)
    fields = reader.fieldnames + ["CivicFix Category"]

    with open(out, "w", newline="", encoding="utf-8") as fout:
        writer = csv.DictWriter(fout, fieldnames=fields)
        writer.writeheader()

        for row in reader:
            row["CivicFix Category"] = civicfix_category(row)
            writer.writerow(row)

print("Created:", out)
