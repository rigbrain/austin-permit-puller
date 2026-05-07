# Austin Permit Puller

A small Python script that pulls commercial building permits from the City of Austin's Open Data feed, scores them for heavy-equipment-purchase intent, and writes CSV + JSON.

The data is public ([data.austintexas.gov](https://data.austintexas.gov/Building-and-Development/Issued-Construction-Permits/3syk-w9eu)) — this just makes it useful. Run it weekly, get a fresh list of who pulled commercial permits in Austin and what they're likely to need.

No API keys. No dependencies outside the Python stdlib. Python 3.10+.

## What it does

For each permit returned:

- Tags likely equipment families (excavators, dozers, lifts, cranes, etc.) based on permit description and work class
- Scores 0–100 for equipment-purchase intent (project value, square footage, floor count, work class)
- Pulls contractor name, phone, address, and a link to the City of Austin permit record

## Quick start

```bash
git clone https://github.com/<your-org>/austin-permit-puller.git
cd austin-permit-puller
python permit_pull.py
```

Default: last 7 days, $1M+ commercial permits. Output writes to `./out/`.

```bash
python permit_pull.py --days 60 --min-value 500000
```

Flags:

- `--days N` — lookback window in days (default 7)
- `--min-value N` — minimum total job valuation in dollars (default 1,000,000)
- `--out-dir PATH` — output directory (default `./out`)

## Example output

See [`examples/sample_output.csv`](examples/sample_output.csv) for an illustrative row structure. Columns:

`score, signals, permit_number, address, zip, description, valuation, sqft, floors, work_class, permit_class, issue_date, contractor_company, contractor_name, contractor_phone, contractor_city, equipment, permit_link`

Running the script against the live API gives you fresh data.

## Why this exists

I'm building [RigBrain](https://rigbrain.io) — a weekly permit-lead service for heavy-equipment dealers in Austin. Dealers want to know which contractors just pulled commercial permits in their territory, ranked by equipment-purchase intent. The data source is public; the work is the curation, scoring, and weekly delivery.

This puller is the foundation. Open-sourcing it because:

1. Verifying the data is real is good for everybody.
2. Anyone can pull Austin Open Data — what's scarce is doing it consistently and ranking by intent.
3. If you're a dealer or contractor in Austin who wants to run this yourself, go ahead. If you'd rather have a curated weekly report delivered to your inbox, [that's what RigBrain does](https://rigbrain.io).

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

## Equipment lexicon

The keyword-to-equipment mapping lives in `EQUIPMENT_LEXICON` at the top of `permit_pull.py`. Edit in place if you want to tune it for your equipment mix.

## API responsibility

The script makes a single HTTP request per run to the public Austin SODA endpoint, with `$limit=200`. No parallelism, no retry storms, no auth required. If you run it more often than weekly, that's between you and your conscience.

## Automation

[`.github/workflows/weekly-pull.yml`](.github/workflows/weekly-pull.yml) is a sample GitHub Action that runs the puller every Monday at 6 a.m. Central and commits the output back to the repo. Adapt as needed.

## License

MIT. See [LICENSE](LICENSE).

## Contact

Issues and PRs welcome. Built by Nick Kaufman — [nick@rigbrain.io](mailto:nick@rigbrain.io) · [rigbrain.io](https://rigbrain.io)
