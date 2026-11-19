# Career Venture Lab — Team Biomedical Engineering (`ROB-3` | AP Calculus | Applied)

Stage 1 Streamlit business simulator for **Robotics kit and repair studio (`ROB-3`)** configured for **AP Calculus (Applied Level)**.

## Included Files
- `app.py` — Working Stage 1 Streamlit dashboard (Inputs, AP Calculus Applied Piecewise Profit & Derivative Plots, Fixture Test Runner, Ledger, and Save/Load JSON Snapshot validation).
- `requirements.txt` — Python dependencies for local runs and Render deployment.
- `sample_data/monthly_fixture.csv` — Official 3-month ROB acceptance test fixture.
- `sample_data/opening_snapshot.json` — Starting JSON snapshot (`v1`) for Team Biomedical Engineering.
- `tests/test_rob3_stage1.py` — Automated `pytest` verification suite for ROB-3 fixtures, stock-limit edge case, zero-sales check, and stale/wrong-team import rejection.
- `ai_assistants/departmental_prompts.md` — Copy-ready instructions for your four departmental AI assistants (Finance, Operations, Market and Marketing, and Independent Reviewer).

## Local Setup & Testing
```bash
pip install -r requirements.txt
pytest
streamlit run app.py
```

## Render Deployment Command
```bash
streamlit run app.py --server.address 0.0.0.0 --server.port $PORT
```
