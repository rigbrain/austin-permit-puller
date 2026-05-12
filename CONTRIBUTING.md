# Contributing

PRs and issues welcome. Two kinds of contribution are most useful:

## 1. Add a metro

The Austin SODA endpoint is the easy case. Other metros publish permit data in different shapes — some SODA, some ArcGIS, some plain JSON. Adding one means:

1. Find the metro's open-data permit endpoint (most major US cities publish one).
2. Add a new fetch function modeled on `fetch_austin_permits()` in `permit_pull.py` that returns the same row shape: `permit_number, address, zip, description, valuation, sqft, floors, work_class, permit_class, issue_date, contractor_company, contractor_name, contractor_phone, contractor_city, permit_link`.
3. Wire it up behind a `--metro <name>` flag.
4. Add a row to the metro coverage table in the README.
5. Add a sample CSV/JSON to `examples/<metro>_sample.csv`.
6. Open a PR.

Metros currently open for contribution: Houston, Dallas, Phoenix, Atlanta, Charlotte, Nashville, Denver, Tampa, Orlando. The corresponding GitHub issues describe each metro's data source.

## 2. Tune the scoring rubric

The rubric in the README is rules-based v1. If you've run the puller against a real dealer or contractor outreach list and your closed-loop data suggests different weights, that's the kind of signal this repo wants. Open an issue with your data shape and proposed weight changes, or open a PR against the `SCORING_RULES` block in `permit_pull.py`.

## Style

- Python 3.10+, stdlib only (no third-party dependencies). This is a hard rule — adding `requests` or `pandas` would defeat the "single-file, no install dance" property that makes this useful.
- Match the existing code style. No introduction of frameworks, classes, or abstractions unless the second metro demands it.
- One PR = one change. Don't bundle "add Houston" with "refactor scoring" — those are separate PRs.

## Reporting bugs

Open an issue with: a minimal repro command, the actual output, and the expected output. If the bug is "the API returned something weird," include the raw permit JSON snippet.

## Code of conduct

Be useful and direct. Don't waste contributors' time with bikeshedding.
