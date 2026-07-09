# Release Readiness API

Combines **defect trends** (QA signal) and **dataset quality checks** (data
signal) into a single release-readiness score — answering "are we ready to
ship?" with one API call instead of five spreadsheets.

Built with FastAPI + SQLModel + pandas. Runs entirely locally on SQLite, no
external services required.

## Why this project

Most portfolio projects stop at "I built a CRUD API." This one models a
real decision a release manager makes every sprint: is the code stable
*and* is the data behind it trustworthy? It's rule-based and fully
explainable — every point deducted from a score has a named reason,
which matters both for real-world use and for talking through the design
in an interview.

## Quickstart

```bash
# 1. Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Generate demo data (fake defects + a fake dataset with intentional issues)
python seed.py

# 4. Run the API
uvicorn app.main:app --reload

# 5. Open the interactive docs
open http://127.0.0.1:8000/docs
```

### Try it via the interactive docs

1. `POST /projects` — create a project, e.g. `{"name": "Checkout Release 2.3"}`, note the `id`
2. `POST /projects/{id}/defects/upload` — upload `seed_data/defects.csv`
3. `POST /projects/{id}/dataset/upload` — upload `seed_data/dataset.csv`
4. `GET /projects/{id}/readiness` — see the combined score and summary

### Try it via curl

```bash
curl -X POST http://127.0.0.1:8000/projects \
  -H "Content-Type: application/json" \
  -d '{"name": "Checkout Release 2.3"}'

curl -X POST http://127.0.0.1:8000/projects/1/defects/upload \
  -F "file=@seed_data/defects.csv"

curl -X POST http://127.0.0.1:8000/projects/1/dataset/upload \
  -F "file=@seed_data/dataset.csv"

curl http://127.0.0.1:8000/projects/1/readiness
```

Example response:
```json
{
  "project_id": 1,
  "qa_score": 78.0,
  "data_score": 70.0,
  "combined_score": 74.0,
  "summary_text": "AT RISK — combined score 74.0/100 (QA 78.0/100, Data 70.0/100). Key factors: 1 open high-severity defect(s) (-7 pts); 30.0% reopen rate (-15.0 pts); customer_id: 7.3% of values are null (-5 pts); region: 28.0% of values are null (-15 pts)."
}
```

## Running the tests

```bash
pytest tests/ -v
```

19 tests covering:
- Scoring logic edge cases (zero defects, score clamping at 0/100, weighting)
- Data quality detection (nulls, duplicates, outliers, empty dataframes)
- Full API flows (upload → summary → readiness) using an isolated in-memory DB

## Project structure

```
app/
  main.py       # FastAPI routes
  models.py     # SQLModel database tables
  schemas.py    # Request/response models that aren't DB tables
  quality.py    # pandas-based data quality checks
  scoring.py    # QA + data scoring logic (pure functions, no I/O)
  database.py   # engine/session setup
tests/
  test_scoring.py  # unit tests for scoring math
  test_quality.py  # unit tests for quality checks
  test_api.py      # end-to-end API tests
seed.py         # generates demo CSVs
```

## How scoring works

**QA score** starts at 100 and deducts points for:
- Open critical defects (-15 each)
- Open high-severity defects (-7 each)
- Reopen rate (-up to 50 pts, scaled by rate)

**Data score** starts at 100 and deducts points for:
- Null rate per column ≥5% (warning, -5) or ≥20% (critical, -15)
- Duplicate rows (-5 to -15 depending on rate)
- Statistical outliers, >3 standard deviations from the mean (-5)

**Combined score** is a weighted average (default 50/50, adjustable via
the `qa_weight` query parameter on `/readiness`).

All thresholds live as named constants in `quality.py` and `scoring.py` —
tune them to match your own judgment calls.

## Extending this project

Ideas if you want to keep building:
- Swap SQLite for Postgres and deploy to Render/Fly.io for a live demo link
- Add a `/projects/{id}/readiness/history` chart (already returns the data — just needs a frontend)
- Add authentication (API key or JWT) to show production-readiness
- Add a GitHub Actions workflow that posts real CI test results to `/defects/upload` automatically
