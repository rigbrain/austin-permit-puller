# Permit Puller

[![weekly-pull](https://github.com/rigbrain/austin-permit-puller/actions/workflows/weekly-pull.yml/badge.svg)](https://github.com/rigbrain/austin-permit-puller/actions/workflows/weekly-pull.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

A small Python script that pulls commercial building permits from US city open-data feeds, scores them for heavy-equipment-purchase intent, and writes CSV + JSON.

No API keys. No dependencies outside the Python stdlib. Python 3.10+.

> **Status: archived / maintenance.** The commercial product this came from (RigBrain) was discontinued in June 2026. The puller stands on its own — the code works, the feeds are public, and it's MIT-licensed. Fork it, adapt it, run it. Issues and PRs may not get a fast response.

**See it live:** [rigbrain.io/austin/](https://rigbrain.io/austin/) — a sample of Austin permits, scored and rendered.

**Currently supports: Austin and Orlando.** Adding more metros is documented below — the short version is that "fork it and swap the endpoint" is the easy case (Austin → Orlando) but most other US cities require a separate adapter because they don't publish per-permit commercial data in the same shape. See [Why this is harder than it sounds](#why-this-is-harder-than-it-sounds).

## What it does

For each permit returned:

- Tags likely equipment families (excavators, dozers, lifts, cranes, etc.) based on permit description and work class
- Scores 0–100 for equipment-purchase intent (project value, square footage, floor count, work class)
- Pulls whatever contractor identity the city's feed exposes (name, sometimes phone, sometimes address) and a link to the source record

## Quick start

```bash
git clone https://github.com/rigbrain/austin-permit-puller.git
cd austin-permit-puller
python permit_pull.py                       # Austin, last 7 days, $1M+
python permit_pull.py --metro orlando       # Orlando instead
python permit_pull.py --metro all           # Every supported metro
python permit_pull.py --days 60 --min-value 500000
```

Output writes to `./out/<metro>_permits_<YYYYMMDD>.{csv,json}`.

Flags:

- `--metro NAME` — one of `austin`, `orlando`, or `all` (default: `austin`)
- `--days N` — lookback window in days (default 7)
- `--min-value N` — minimum project value in dollars (default 1,000,000)
- `--out-dir PATH` — output directory (default `./out`)

## Example output

See [`examples/sample_output.csv`](examples/sample_output.csv) (Austin, illustrative) and [`examples/orlando_sample_output.csv`](examples/orlando_sample_output.csv) (Orlando, real rows from the live feed).

Columns:

`score, signals, permit_number, address, zip, description, valuation, sqft, floors, work_class, permit_class, issue_date, contractor_company, contractor_name, contractor_phone, contractor_city, equipment, permit_link, metro`

Some columns are empty for some metros — see the coverage table below.

## Metro coverage

| Metro   | Source                                            | Stage       | Has phone? | Has floors? | Notes |
|---------|---------------------------------------------------|-------------|------------|-------------|-------|
| Austin  | data.austintexas.gov SODA (`3syk-w9eu`)           | Issued      | ✅         | ✅          | Reference implementation. Richest schema. |
| Orlando | data.cityoforlando.net SODA (`ryhf-m453`)         | Application | ❌         | ❌          | Application-stage = earlier intent signal. Contractor company present, but phone/floors not published. |

## Why this is harder than it sounds

The Austin SODA endpoint is the easy case — single HTTP call, no auth, well-documented Socrata Open Data API. Orlando is similar enough that the script handles both with one shared scoring path.

Most other US cities are not. As of this writing:

- **Houston** publishes only monthly aggregate counts (residential), not per-permit commercial records.
- **Dallas** has a Socrata endpoint, but the dataset has been frozen since August 2020.
- **Phoenix, Tampa** block public catalog API access (`HTTP 403`); their permit data lives behind Accela CitizenAccess portals.
- **Atlanta, Charlotte, Nashville, Denver** don't expose Socrata catalog endpoints in the same way; most use ArcGIS feature services, which have a different query model and different field shapes per city.

So while you *can* "fork it and swap the endpoint" between Austin and Orlando, supporting a new metro usually means writing a small adapter for that city's specific data source — and accepting that the adapter may have to fill some columns with empty strings because not every city publishes the same fields.

The `fetch_<metro>` / `normalize_<metro>` split in `permit_pull.py` exists for exactly this. See [CONTRIBUTING.md](CONTRIBUTING.md) for the row contract.

## Scoring rubric

Rules-based v1 — no ML, no closed-loop training data yet. Base score 50, capped 0–100.

| Signal | Score contribution |
|---|---|
| $20M+ project value | +20 |
| $10M+ project value | +15 |
| $5M+ project value | +10 |
| $1M+ project value | +5 |
| 50K+ sqft | +10 |
| 10K+ sqft | +5 |
| 4+ floors | +10 |
| 2–3 floors | +5 |
| Work class: New / Shell / Addition+Remodel | +5 |

Calibrated against Austin permits 2024–2026. Issues and PRs welcome — if your closed-loop data suggests different weights, that's the kind of feedback the rubric is built to take.

Note: metros without a floors field (e.g., Orlando) won't trigger the vertical-work bump. The score still works, it just doesn't get the extra signal.

## Equipment lexicon

The keyword-to-equipment mapping lives in `EQUIPMENT_LEXICON` at the top of `permit_pull.py`. Edit in place if you want to tune it for your equipment mix.

## API responsibility

The script makes a single HTTP request per metro per run, with `$limit=200`. No parallelism, no retry storms, no auth required. If you run it more often than weekly, that's between you and the city's open-data terms of service.

## Automation

[`.github/workflows/weekly-pull.yml`](.github/workflows/weekly-pull.yml) is a sample GitHub Action that runs the puller every Monday at 6 a.m. Central and commits the output back to the repo. Adapt as needed.

## License

MIT. See [LICENSE](LICENSE).

## Why this exists

This was the data engine behind RigBrain — a weekly permit-lead service for heavy-equipment dealers (2026, discontinued). The Austin and Orlando pullers in this repo were the same code paths that produced the data the service sold. The paid work was the curation, the per-dealer filtering, the contractor enrichment for fields the public feeds don't publish, and the weekly delivery. The raw data is public, so the puller is open — and it stays open as a standalone tool.

## Contact

Issues and PRs welcome. Built by Nick Kaufman — [nick@rigbrain.io](mailto:nick@rigbrain.io)
