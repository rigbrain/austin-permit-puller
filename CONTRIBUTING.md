# Contributing

PRs and issues welcome. Two kinds of contribution are most useful.

## 1. Add a metro

If your city publishes commercial building permits as a public open-data feed, adding it is a `fetch_<metro>` + `normalize_<metro>` pair in `permit_pull.py` and a new entry in the `METROS` dict. No new dependencies.

The row contract is the dict shape returned by `normalize_austin` / `normalize_orlando` in `permit_pull.py`. All keys must be present. Strings can be empty if the source doesn't publish that field — `contractor_phone` is empty for Orlando, for example. Scoring degrades gracefully when fields are missing.

What to do:

1. Find the city's per-permit commercial building permit feed. Not all cities have one — see the table below for the gotchas across the top 10 US metros we looked at.
2. Implement `fetch_<metro>(days_back, min_value)` returning the raw API rows.
3. Implement `normalize_<metro>(permits)` returning the common row shape.
4. Register both in the `METROS` dict at the bottom of `permit_pull.py`.
5. Run `python permit_pull.py --metro <name> --days 30` and commit one fresh sample to `examples/<metro>_sample_output.csv`.
6. Add a row to the metro coverage table in the README, including which columns are empty.
7. Open a PR.

### What we found across the top 10 US metros

| Metro     | Source check (May 2026)                                                                 |
|-----------|------------------------------------------------------------------------------------------|
| Austin    | ✅ Socrata `3syk-w9eu`, per-permit, fresh                                                |
| Orlando   | ✅ Socrata `ryhf-m453`, application-stage, fresh — implemented                            |
| Houston   | ⚠️ CKAN; only monthly residential aggregates — no per-permit commercial feed found       |
| Dallas    | ⚠️ Socrata `e7gq-4sah` exists but the dataset has been frozen since Aug 30, 2020         |
| Phoenix   | ⚠️ Catalog API returns 403; permits live behind Accela CitizenAccess                     |
| Atlanta   | ⚠️ No Socrata catalog; check ArcGIS feature services                