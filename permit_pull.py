#!/usr/bin/env python3
"""
Austin Permit Puller

Pulls commercial building permits from the City of Austin's Open Data feed,
scores them for heavy-equipment-purchase intent, writes CSV + JSON.

Usage:
    python permit_pull.py                       # last 7 days, $1M+ floor
    python permit_pull.py --days 60             # last 60 days
    python permit_pull.py --min-value 500000    # lower the value floor

No API key required (Austin SODA endpoint is public).
Python 3.10+. Stdlib only — no third-party dependencies.
"""

import argparse
import csv
import json
import os
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import quote
from urllib.request import urlopen

API = "https://data.austintexas.gov/resource/3syk-w9eu.json"

# Equipment lexicon — keywords in permit description -> equipment family
EQUIPMENT_LEXICON = {
    "Excavators": ["excavat", "earthwork", "site work", "foundation", "utility trench"],
    "Dozers": ["grad", "site prep", "earthwork", "demoli", "demolition"],
    "Loaders": ["site work", "load", "earthwork", "demoli"],
    "Boom Lifts": ["story", "stories", "high", "tall", "steel", "tilt"],
    "Tower Cranes": ["tower", "high-rise", "5 story", "6 story", "7 story", "8 story", "9 story", "10 story", "garage"],
    "Cranes": ["steel", "tilt wall", "warehouse", "shell", "pre-engineered"],
    "Scissor Lifts": ["interior", "finish", "ceiling", "drywall", "MEP"],
    "Concrete Equipment": ["concrete", "tilt wall", "foundation", "garage", "paving"],
    "Skid Steers": ["site work", "landscape", "drive", "parking", "small commercial"],
    "Material Handling": ["warehouse", "industrial", "logistics", "distribution"],
}

# Work classes that indicate real heavy equipment need
HIGH_INTENT_CLASSES = {"New", "Shell", "Addition and Remodel"}


def build_query(days_back: int, min_value: int) -> str:
    """Construct the SODA $where clause."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days_back)).strftime("%Y-%m-%dT00:00:00.000")
    where = (
        f"issue_date > '{cutoff}' "
        f"AND permit_class_mapped = 'Commercial' "
        f"AND total_job_valuation > {min_value}"
    )
    return f"{API}?$where={quote(where)}&$order=total_job_valuation%20DESC&$limit=200"


def fetch_permits(url: str) -> list[dict]:
    with urlopen(url, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def tag_equipment(description: str, work_class: str) -> list[str]:
    """Return list of equipment families likely needed for this project."""
    desc = (description or "").lower()
    matches = []
    for fam, keywords in EQUIPMENT_LEXICON.items():
        if any(k in desc for k in keywords):
            matches.append(fam)
    # Always-add for new commercial work
    if work_class == "New" and not matches:
        matches.extend(["Excavators", "Dozers", "Loaders"])
    return matches


def compute_score(permit: dict) -> tuple[int, list[str]]:
    """Return (0-100 equipment-purchase intent score, list of contributing signals)."""
    s = 50
    signals: list[str] = []
    val = float(permit.get("total_job_valuation") or 0)
    sqft = float(permit.get("total_new_add_sqft") or 0)
    floors = int(float(permit.get("number_of_floors") or 1))
    work_class = permit.get("work_class", "")

    # Project value
    if val >= 20_000_000:
        s += 20; signals.append("$20M+ value")
    elif val >= 10_000_000:
        s += 15; signals.append("$10M+ value")
    elif val >= 5_000_000:
        s += 10; signals.append("$5M+ value")
    elif val >= 1_000_000:
        s += 5; signals.append("$1M+ value")

    # Size
    if sqft >= 50_000:
        s += 10; signals.append("50K+ sqft")
    elif sqft >= 10_000:
        s += 5; signals.append("10K+ sqft")

    # Vertical = crane/lift work
    if floors >= 4:
        s += 10; signals.append(f"{floors} floors")
    elif floors >= 2:
        s += 5; signals.append(f"{floors} floors")

    # Work class
    if work_class in HIGH_INTENT_CLASSES:
        s += 5; signals.append(work_class)

    return min(100, max(0, s)), signals


def normalize_phone(raw: str) -> str:
    digits = re.sub(r"\D", "", raw or "")
    if len(digits) == 10:
        return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    return raw or ""


def transform(permits: list[dict]) -> list[dict]:
    rows = []
    for p in permits:
        equipment = tag_equipment(p.get("description", ""), p.get("work_class", ""))
        s, signals = compute_score(p)
        rows.append({
            "score": s,
            "signals": ", ".join(signals),
            "permit_number": p.get("permit_number", ""),
            "address": p.get("permit_location", ""),
            "zip": p.get("original_zip", ""),
            "description": (p.get("description", "") or "").strip().replace("\n", " "),
            "valuation": float(p.get("total_job_valuation") or 0),
            "sqft": float(p.get("total_new_add_sqft") or 0),
            "floors": p.get("number_of_floors", ""),
            "work_class": p.get("work_class", ""),
            "permit_class": p.get("permit_class", ""),
            "issue_date": (p.get("issue_date") or "")[:10],
            "contractor_company": p.get("contractor_company_name", ""),
            "contractor_name": p.get("contractor_full_name", ""),
            "contractor_phone": normalize_phone(p.get("contractor_phone", "")),
            "contractor_city": p.get("contractor_city", ""),
            "equipment": ", ".join(equipment),
            "permit_link": (p.get("link") or {}).get("url", ""),
        })
    rows.sort(key=lambda r: (-r["score"], -r["valuation"]))
    return rows


def write_csv(rows: list[dict], path: str) -> None:
    if not rows:
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def write_json(rows: list[dict], path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--min-value", type=int, default=1_000_000)
    ap.add_argument("--out-dir", default="out")
    args = ap.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d")

    print(f"[+] Pulling Austin commercial permits, last {args.days} days, value > ${args.min_value:,}")
    raw = fetch_permits(build_query(args.days, args.min_value))
    print(f"[+] {len(raw)} permits returned")

    rows = transform(raw)
    csv_path = os.path.join(args.out_dir, f"austin_permits_{stamp}.csv")
    json_path = os.path.join(args.out_dir, f"austin_permits_{stamp}.json")
    write_csv(rows, csv_path)
    write_json(rows, json_path)

    top15 = rows[:15]
    top_value = sum(r["valuation"] for r in top15)
    print(f"[+] Wrote {csv_path}  ({len(rows)} rows)")
    print(f"[+] Wrote {json_path}")
    print(f"[+] Top 15 total value: ${top_value:,.0f}")
    print(f"[+] Top 15 contractors: {len(set(r['contractor_company'] for r in top15 if r['contractor_company']))} unique")


if __name__ == "__main__":
    main()
