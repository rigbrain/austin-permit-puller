#!/usr/bin/env python3
"""
Permit Puller

Pulls commercial building permits from supported metro open-data feeds,
scores them for heavy-equipment-purchase intent, writes CSV + JSON.

Usage:
    python permit_pull.py                          # Austin, last 7 days, $1M+
    python permit_pull.py --metro orlando          # Orlando instead
    python permit_pull.py --metro all              # Every supported metro
    python permit_pull.py --days 60 --min-value 500000

Supported metros: austin, orlando.

Adding a metro: implement a `fetch_<metro>()` returning raw API rows and a
`normalize_<metro>()` returning the common row shape; add to METROS dict.
No new dependencies — Python 3.10+ stdlib only.
"""

import argparse
import csv
import json
import os
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import quote
from urllib.request import urlopen


# ---------------------------------------------------------------------------
# Shared: equipment tagging + scoring
# ---------------------------------------------------------------------------

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

HIGH_INTENT_CLASSES = {"New", "Shell", "Addition and Remodel", "New Construction"}


def tag_equipment(description: str, work_class: str) -> list[str]:
    desc = (description or "").lower()
    matches = []
    for fam, keywords in EQUIPMENT_LEXICON.items():
        if any(k in desc for k in keywords):
            matches.append(fam)
    if work_class in ("New", "New Construction") and not matches:
        matches.extend(["Excavators", "Dozers", "Loaders"])
    return matches


def compute_score(row: dict) -> tuple[int, list[str]]:
    s = 50
    signals: list[str] = []
    val = float(row.get("valuation") or 0)
    sqft = float(row.get("sqft") or 0)
    floors_raw = row.get("floors") or 0
    try:
        floors = int(float(floors_raw)) if floors_raw not in ("", None) else 0
    except (ValueError, TypeError):
        floors = 0
    work_class = row.get("work_class", "")

    if val >= 20_000_000:
        s += 20; signals.append("$20M+ value")
    elif val >= 10_000_000:
        s += 15; signals.append("$10M+ value")
    elif val >= 5_000_000:
        s += 10; signals.append("$5M+ value")
    elif val >= 1_000_000:
        s += 5; signals.append("$1M+ value")

    if sqft >= 50_000:
        s += 10; signals.append("50K+ sqft")
    elif sqft >= 10_000:
        s += 5; signals.append("10K+ sqft")

    if floors >= 4:
        s += 10; signals.append(f"{floors} floors")
    elif floors >= 2:
        s += 5; signals.append(f"{floors} floors")

    if work_class in HIGH_INTENT_CLASSES:
        s += 5; signals.append(work_class)

    return min(100, max(0, s)), signals


def normalize_phone(raw: str) -> str:
    digits = re.sub(r"\D", "", raw or "")
    if len(digits) == 10:
        return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    return raw or ""


# ---------------------------------------------------------------------------
# Austin — data.austintexas.gov SODA, Issued Construction Permits (3syk-w9eu)
# ---------------------------------------------------------------------------

AUSTIN_API = "https://data.austintexas.gov/resource/3syk-w9eu.json"


def fetch_austin(days_back: int, min_value: int) -> list[dict]:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days_back)).strftime("%Y-%m-%dT00:00:00.000")
    where = (
        f"issue_date > '{cutoff}' "
        f"AND permit_class_mapped = 'Commercial' "
        f"AND total_job_valuation > {min_value}"
    )
    url = f"{AUSTIN_API}?$where={quote(where)}&$order=total_job_valuation%20DESC&$limit=200"
    with urlopen(url, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def normalize_austin(permits: list[dict]) -> list[dict]:
    rows = []
    for p in permits:
        rows.append({
            "metro": "Austin",
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
            "permit_link": (p.get("link") or {}).get("url", ""),
        })
    return rows


# ---------------------------------------------------------------------------
# Orlando — data.cityoforlando.net SODA, Permit Applications (ryhf-m453)
#
# Notable differences from Austin:
# - Stage = APPLICATION (intent signal earlier than Austin's "issued" stage)
# - No contractor_phone field (lookup contractor_name to enrich)
# - No number_of_floors field (scoring won't get the vertical-work bump)
# - estimated_cost replaces total_job_valuation
# - plan_review_type = 'Commercial' replaces permit_class_mapped
# ---------------------------------------------------------------------------

ORLANDO_API = "https://data.cityoforlando.net/resource/ryhf-m453.json"


def fetch_orlando(days_back: int, min_value: int) -> list[dict]:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days_back)).strftime("%Y-%m-%dT00:00:00.000")
    where = (
        f"processed_date > '{cutoff}' "
        f"AND plan_review_type = 'Commercial' "
        f"AND estimated_cost > {min_value}"
    )
    url = f"{ORLANDO_API}?$where={quote(where)}&$order=estimated_cost%20DESC&$limit=200"
    with urlopen(url, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def normalize_orlando(permits: list[dict]) -> list[dict]:
    rows = []
    for p in permits:
        wt = (p.get("worktype") or "").strip()
        work_class = "New Construction" if "new" in wt.lower() else wt or ""
        addr = p.get("contractor_address", "") or ""
        city = ""
        if "," in addr:
            parts = [x.strip() for x in addr.split(",")]
            if len(parts) >= 2:
                city = parts[-2]
        rows.append({
            "metro": "Orlando",
            "permit_number": p.get("permit_number", ""),
            "address": p.get("permit_address", ""),
            "zip": "",
            "description": ((p.get("project_name", "") or "") + " - " + wt).strip(" -"),
            "valuation": float(p.get("estimated_cost") or 0),
            "sqft": float(p.get("square_footage") or 0),
            "floors": "",
            "work_class": work_class,
            "permit_class": p.get("plan_review_type", ""),
            "issue_date": (p.get("processed_date") or "")[:10],
            "contractor_company": p.get("contractor_name", ""),
            "contractor_name": "",
            "contractor_phone": "",
            "contractor_city": city,
            "permit_link": f"https://permits.cityoforlando.net/permit/{p.get('permit_number','')}",
        })
    return rows


# ---------------------------------------------------------------------------
# Dispatch + run
# ---------------------------------------------------------------------------

METROS = {
    "austin":  (fetch_austin,  normalize_austin),
    "orlando": (fetch_orlando, normalize_orlando),
}


def run_metro(metro: str, days: int, min_value: int) -> list[dict]:
    fetch, normalize = METROS[metro]
    raw = fetch(days, min_value)
    rows = normalize(raw)
    for r in rows:
        s, sig = compute_score(r)
        r["score"] = s
        r["signals"] = ", ".join(sig)
        r["equipment"] = ", ".join(tag_equipment(r["description"], r["work_class"]))
    rows.sort(key=lambda r: (-r["score"], -r["valuation"]))
    return rows


COLUMN_ORDER = [
    "score", "signals", "permit_number", "address", "zip", "description",
    "valuation", "sqft", "floors", "work_class", "permit_class", "issue_date",
    "contractor_company", "contractor_name", "contractor_phone",
    "contractor_city", "equipment", "permit_link", "metro",
]


def write_csv(rows: list[dict], path: str) -> None:
    if not rows:
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMN_ORDER)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in COLUMN_ORDER})


def write_json(rows: list[dict], path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--metro", default="austin",
                    help=f"Metro to pull (one of {sorted(METROS.keys())} or 'all'). Default: austin")
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--min-value", type=int, default=1_000_000)
    ap.add_argument("--out-dir", default="out")
    args = ap.parse_args()

    metros = sorted(METROS.keys()) if args.metro == "all" else [args.metro]
    for m in metros:
        if m not in METROS:
            raise SystemExit(f"Unknown metro: {m!r}. Supported: {sorted(METROS.keys())} or 'all'.")

    os.makedirs(args.out_dir, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d")

    for m in metros:
        print(f"[+] {m}: pulling commercial permits, last {args.days} days, value > ${args.min_value:,}")
        rows = run_metro(m, args.days, args.min_value)
        csv_path = os.path.join(args.out_dir, f"{m}_permits_{stamp}.csv")
        json_path = os.path.join(args.out_dir, f"{m}_permits_{stamp}.json")
        write_csv(rows, csv_path)
        write_json(rows, json_path)
        top15 = rows[:15]
        top_value = sum(r["valuation"] for r in top15)
        print(f"[+] {m}: wrote {csv_path}  ({len(rows)} rows)")
        print(f"[+] {m}: top 15 total value: ${top_value:,.0f}")


if __name__ == "__main__":
    main()
