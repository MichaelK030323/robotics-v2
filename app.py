import json
import math
import uuid
from decimal import Decimal, ROUND_HALF_UP
from copy import deepcopy
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

st.set_page_config(
    page_title="Career Venture Lab | Team Biomedical Engineering (ROB-3)",
    layout="wide",
)

def money(val) -> Decimal:
    return Decimal(str(val)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

def initial_state() -> dict:
    return {
        "team_id": "team-biomedical-engineering",
        "course": "AP Calculus",
        "pathway_id": "ROB-3",
        "selected_level": "Applied",
        "selected_skill": "Constrained Profit Optimization & Piecewise Derivative",
        "snapshot_id": "snap-rob3-v1",
        "state_version": 1,
        "simulation_date": "2027-01-01",
        "currency": "USD",
        "params": {
            "base_price": 120.00,
            "D0": 40,
            "staff_hours": 90.0,
            "hours_per_unit": 3.0,
            "opening_cash": 5000.00,
            "equipment_assets": 4000.00,
            "opening_stock_units": 100,
            "component_unit_cost": 30.00,
            "restock_units": 0,
            "defect_rate": 0.0,
            "requested_units": 40,
            "ad_cost": 0.00,
            "refund_amount": 0.00,
            "loan_principal": 0.00,
            "interest": 0.00,
            "additional_capex": 0.00,
        },
        "variable_lines": {
            "components_COGS": 30.00,
            "assembly_labor": 20.00,
            "packaging": 10.00,
            "warranty_consumables": 5.00,
        },
        "fixed_lines": {
            "workspace": 250.00,
            "software": 100.00,
            "equipment_maintenance": 150.00,
            "admin": 100.00,
        },
        "ledger": [],
        "executed_run_ids": [],
        "decisions": [],
    }

def compute_rob_month(params: dict, var_lines: dict, fixed_lines: dict, capacity_override=None) -> dict:
    price = money(params["base_price"])
    requested = int(params["requested_units"])
    staff_hours = float(params["staff_hours"])
    hours_per_unit = float(params["hours_per_unit"])
    opening_cash = money(params["opening_cash"])
    opening_stock = int(params["opening_stock_units"])
    comp_cost = money(params["component_unit_cost"])
    restock = int(params["restock_units"])
    defect_rate = float(params["defect_rate"])
    ad_cost = money(params["ad_cost"])
    refund_amount = money(params["refund_amount"])
    loan_principal = money(params["loan_principal"])
    interest = money(params["interest"])
    additional_capex = money(params["additional_capex"])

    staff_cap = math.floor(staff_hours / hours_per_unit) if hours_per_unit > 0 else 0
    if capacity_override is not None:
        effective_cap = int(capacity_override)
        attempted = min(requested, effective_cap)
    else:
        effective_cap = staff_cap
        attempted = min(requested, staff_cap, opening_stock + restock)

    failed = math.floor(attempted * defect_rate)
    sold = attempted - failed
    unserved_demand = max(0, requested - attempted)

    # Variable costs per attempted kit
    var_lines_dec = {k: money(v) for k, v in var_lines.items()}
    var_lines_dec["components_COGS"] = comp_cost
    var_per_unit = sum(var_lines_dec.values(), Decimal("0.00"))
    noncomp_var_per_unit = var_per_unit - comp_cost

    revenue = (price * Decimal(sold)) - refund_amount
    variable_expense = Decimal(attempted) * var_per_unit
    fixed_expense = sum((money(v) for v in fixed_lines.values()), Decimal("0.00"))
    total_expense = variable_expense + fixed_expense + ad_cost
    operating_profit = revenue - total_expense
    net_profit = operating_profit - interest

    # Cash rules: components paid on restock, non-components paid on attempted units
    restock_cash_outflow = Decimal(restock) * comp_cost
    noncomp_cash_outflow = Decimal(attempted) * noncomp_var_per_unit
    ending_cash = (
        opening_cash
        + revenue
        - restock_cash_outflow
        - noncomp_cash_outflow
        - fixed_expense
        - ad_cost
        - interest
        - additional_capex
        + loan_principal
    )

    ending_stock_units = opening_stock + restock - attempted
    ending_inventory_value = Decimal(ending_stock_units) * comp_cost
    build_hours_used = attempted * hours_per_unit
    utilization = (build_hours_used / staff_hours * 100.0) if staff_hours > 0 else 0.0

    return {
        "staff_capacity": staff_cap,
        "effective_capacity": effective_cap,
        "requested": requested,
        "attempted": attempted,
        "failed": failed,
        "sold": sold,
        "unserved_demand": unserved_demand,
        "var_per_unit": var_per_unit,
        "revenue": revenue,
        "variable_expense": variable_expense,
        "fixed_expense": fixed_expense,
        "ad_cost": ad_cost,
        "total_expense": total_expense,
        "operating_profit": operating_profit,
        "net_profit": net_profit,
        "ending_cash": ending_cash,
        "ending_stock_units": ending_stock_units,
        "ending_inventory_value": ending_inventory_value,
        "build_hours_used": build_hours_used,
        "utilization_pct": round(utilization, 1),
    }

def validate_snapshot_import(data: dict, expected_team_id: str, current_version: int) -> tuple[bool, str]:
    required_keys = ["team_id", "course", "pathway_id", "snapshot_id", "state_version", "params"]
    for k in required_keys:
        if k not in data:
            return False, f"Missing required field: {k}"
    if data["team_id"] != expected_team_id:
        return False, f"Team ID mismatch: expected '{expected_team_id}', got '{data['team_id']}'."
    if int(data["state_version"]) < current_version:
        return False, f"Stale snapshot rejected: imported version {data['state_version']} is older than current version {current_version}."
    return True, "Valid snapshot."

if "sim_state" not in st.session_state:
    st.session_state.sim_state = initial_state()

state = st.session_state.sim_state

st.title("Career Venture Lab — Robotics Kit & Repair Studio (ROB-3)")
st.caption(
    f"**Team:** `{state['team_id']}` | **Course:** {state['course']} | "
    f"**Pathway:** {state['pathway_id']} | **Level:** {state['selected_level']} | "
    f"**State Version:** v{state['state_version']} ({state['snapshot_id']})"
)

# Persistent Math Panel Banner
with st.expander("Persistent Math Skills & Challenge Level Panel (AP Calculus — Applied)", expanded=True):
    p0 = state["params"]["base_price"]
    D0 = state["params"]["D0"]
    v = sum(state["variable_lines"].values())
    F = sum(state["fixed_lines"].values())
    cap = math.floor(state["params"]["staff_hours"] / state["params"]["hours_per_unit"])
    a = 2 * D0
    b = D0 / p0 if p0 > 0 else 0
    corner_p = (a - cap) / b if b > 0 else 0
    unconstrained_p = (a + b * v) / (2 * b) if b > 0 else 0

    c1, c2, c3 = st.columns(3)
    c1.markdown(
        f"**Selected Skill & Level**
"
        f"- Course: `AP Calculus` (`Applied`)
"
        f"- Demand: $q(p) = {a} - {b:.4f}p$ on $0 \le p \le {2*p0:.0f}$
"
        f"- Capacity Cap: $s(p) = \min({cap}, \max(0, q(p)))$"
    )
    c2.markdown(
        f"**Piecewise Profit & Derivative**
"
        f"- Capacity branch ($p \le \${corner_p:.2f}$): $P(p) = {cap}(p - {v:.0f}) - {F:.0f}$, $P'(p) = {cap}$
"
        f"- Demand branch ($p > \${corner_p:.2f}$): $P(p) = (p - {v:.0f})({a} - {b:.4f}p) - {F:.0f}$
"
        f"- Capacity Corner: **$p = \${corner_p:.2f}$** ($P'(p)$ undefined at corner)"
    )
    c3.markdown(
        f"**Boundary & Optimality Check**
"
        f"- Unconstrained critical point: $p = \${unconstrained_p:.2f}$ ($q = {a - b*unconstrained_p:.1f}$ kits)
"
        f"- Because $q(\${unconstrained_p:.2f}) > {cap}$ capacity, unconstrained peak is **infeasible**.
"
        f"- Constrained continuous optimum occurs at corner **$p = \${corner_p:.2f}$**."
    )

tabs = st.tabs([
    "1. Overview & Inputs (Stage 1)",
    "2. AP Calculus Visuals (Stage 1)",
    "3. Fixture Test Runner (Stage 1)",
    "4. Ledger & Save/Load JSON (Stage 1)",
    "5. Stages 2–4 Roadmap (Pending)"
])

# TAB 1: Overview & Inputs
with tabs[0]:
    st.subheader("Studio Inputs & Monthly Simulation Step (Normal Mode)")
    st.info("Input changes preview as a scenario until you click **Approve & Record Monthly Run**.")

    col_left, col_right = st.columns(2)
    with col_left:
        st.markdown("#### Pricing, Demand & Operations")
        p_in = st.number_input("Kit Price ($/unit)", min_value=1.0, max_value=500.0, value=float(state["params"]["base_price"]), step=5.0)
        req_in = st.number_input("Requested Kits (units/month)", min_value=0, max_value=500, value=int(state["params"]["requested_units"]), step=1)
        hours_in = st.number_input("Staff Hours Available (hrs/month)", min_value=0.0, max_value=1000.0, value=float(state["params"]["staff_hours"]), step=3.0)
        hpu_in = st.number_input("Build Hours per Kit (hrs/unit)", min_value=0.5, max_value=40.0, value=float(state["params"]["hours_per_unit"]), step=0.5)
        defect_in = st.slider("Defect Rate (0.00 to 1.00)", min_value=0.0, max_value=1.0, value=float(state["params"]["defect_rate"]), step=0.01)

    with col_right:
        st.markdown("#### Inventory, Cash & Marketing")
        stock_in = st.number_input("Opening Component Stock (sets)", min_value=0, max_value=2000, value=int(state["params"]["opening_stock_units"]), step=5)
        restock_in = st.number_input("Restock Units Purchased This Month (sets)", min_value=0, max_value=2000, value=int(state["params"]["restock_units"]), step=5)
        comp_cost_in = st.number_input("Component Cost ($/set)", min_value=0.0, max_value=500.0, value=float(state["params"]["component_unit_cost"]), step=1.0)
        ad_in = st.number_input("Own-Business Campaign Cost ($)", min_value=0.0, max_value=10000.0, value=float(state["params"]["ad_cost"]), step=25.0)
        sim_date_in = st.text_input("Simulation Period End Date (YYYY-MM-DD)", value=state["simulation_date"])

    preview_params = deepcopy(state["params"])
    preview_params.update({
        "base_price": p_in,
        "requested_units": req_in,
        "staff_hours": hours_in,
        "hours_per_unit": hpu_in,
        "defect_rate": defect_in,
        "opening_stock_units": stock_in,
        "restock_units": restock_in,
        "component_unit_cost": comp_cost_in,
        "ad_cost": ad_in,
    })
    res = compute_rob_month(preview_params, state["variable_lines"], state["fixed_lines"])

    st.markdown("#### Scenario Preview (Before Approval)")
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Sold / Attempted", f"{res['sold']} / {res['attempted']}", f"Cap: {res['effective_capacity']}")
    m2.metric("Revenue", f"${res['revenue']:,.2f}")
    m3.metric("Total Expense", f"${res['total_expense']:,.2f}")
    m4.metric("Operating Profit", f"${res['operating_profit']:,.2f}")
    m5.metric("Ending Cash", f"${res['ending_cash']:,.2f}", f"Stock: {res['ending_stock_units']} sets")

    if res["ending_cash"] < Decimal("1000.00"):
        st.warning("Finance Alert: Projected closing cash is below the $1,000 reserve threshold!")

    run_id_input = st.text_input("Unique Run ID (Duplicate-Run Protection)", value=f"run-v{state['state_version']}-{sim_date_in}")
    if st.button("Approve & Record Monthly Run to Ledger", type="primary"):
        if run_id_input in state["executed_run_ids"]:
            st.error(f"Duplicate Run Blocked: '{run_id_input}' has already been recorded.")
        else:
            state["params"].update(preview_params)
            state["params"]["opening_cash"] = float(res["ending_cash"])
            state["params"]["opening_stock_units"] = int(res["ending_stock_units"])
            state["params"]["restock_units"] = 0
            state["simulation_date"] = sim_date_in
            state["state_version"] += 1
            state["snapshot_id"] = f"snap-rob3-v{state['state_version']}"
            state["executed_run_ids"].append(run_id_input)
            state["ledger"].append({
                "run_id": run_id_input,
                "date": sim_date_in,
                "state_version": state["state_version"],
                "mode": "Normal",
                "requested": res["requested"],
                "attempted": res["attempted"],
                "failed": res["failed"],
                "sold": res["sold"],
                "revenue": float(res["revenue"]),
                "variable_expense": float(res["variable_expense"]),
                "fixed_expense": float(res["fixed_expense"]),
                "ad_cost": float(res["ad_cost"]),
                "total_expense": float(res["total_expense"]),
                "operating_profit": float(res["operating_profit"]),
                "closing_cash": float(res["ending_cash"]),
                "closing_stock": res["ending_stock_units"],
            })
            st.success(f"Recorded {run_id_input}. Advanced state to v{state['state_version']}.")
            st.rerun()

# TAB 2: AP Calculus Visuals
with tabs[1]:
    st.subheader("AP Calculus (Applied): Constrained Profit $P(p)$ and Derivative $P'(p)$")
    p0_calc = 120.0
    D0_calc = 40.0
    a_c = 2 * D0_calc
    b_c = D0_calc / p0_calc
    v_c = float(sum(state["variable_lines"].values()))
    F_c = float(sum(state["fixed_lines"].values()))
    cap_c = math.floor(state["params"]["staff_hours"] / state["params"]["hours_per_unit"])
    corner = (a_c - cap_c) / b_c

    prices = np.linspace(0, 240, 241)
    q_demand = np.maximum(0, a_c - b_c * prices)
    s_cont = np.minimum(cap_c, q_demand)
    s_int = np.floor(s_cont)

    prof_cont = (prices - v_c) * s_cont - F_c
    prof_int = (prices - v_c) * s_int - F_c

    deriv = np.where(prices < corner, cap_c, np.where(prices > corner, a_c + b_c * v_c - 2 * b_c * prices, np.nan))

    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.12,
        subplot_titles=(
            f"Monthly Profit P(p) with Capacity Cap = {cap_c} Kits (Continuous vs. Integer Units)",
            "Marginal Profit Derivative P'(p) ($ per $1 Price Change) — Undefined at Capacity Corner"
        )
    )
    fig.add_trace(go.Scatter(x=prices, y=prof_cont, name="Continuous Profit P(p)", line=dict(color="#1f77b4", width=2)), row=1, col=1)
    fig.add_trace(go.Scatter(x=prices, y=prof_int, name="Whole-Unit Integer Profit", line=dict(color="#ff7f0e", dash="dot")), row=1, col=1)
    fig.add_hline(y=0, line_dash="dash", line_color="gray", row=1, col=1)
    fig.add_vline(x=corner, line_dash="dash", line_color="#d62728", annotation_text=f"Corner p=${corner:.2f}", row=1, col=1)

    fig.add_trace(go.Scatter(x=prices, y=deriv, name="Derivative P'(p)", line=dict(color="#2ca02c", width=2)), row=2, col=1)
    fig.add_hline(y=0, line_dash="dash", line_color="gray", row=2, col=1)
    fig.add_vline(x=corner, line_dash="dash", line_color="#d62728", row=2, col=1)
    fig.add_trace(go.Scatter(
        x=[corner], y=[cap_c], mode="markers",
        marker=dict(size=10, color="white", line=dict(color="#d62728", width=2)),
        name="Undefined Corner (Jump Discontinuity in P')"
    ), row=2, col=1)

    fig.update_layout(height=620, xaxis2_title="Kit Price p ($/unit)", yaxis1_title="Profit ($/mo)", yaxis2_title="P'(p) (units)")
    st.plotly_chart(fig, use_container_width=True)

    sample_prices = [100, 120, 150, 180, 210]
    table_rows = []
    for sp in sample_prices:
        qd = max(0.0, a_c - b_c * sp)
        sc = min(float(cap_c), qd)
        si = math.floor(sc)
        table_rows.append({
            "Price ($)": sp,
            "Unconstrained Demand q(p)": round(qd, 2),
            "Constrained Continuous s(p)": round(sc, 2),
            "Integer Sold Kits": si,
            "Continuous Profit ($)": round((sp - v_c) * sc - F_c, 2),
            "Integer Profit ($)": round((sp - v_c) * si - F_c, 2),
            "Branch": "Capacity-Capped" if sp < corner else ("Corner Boundary" if abs(sp - corner) < 1e-6 else "Demand-Constrained")
        })
    st.dataframe(pd.DataFrame(table_rows), use_container_width=True)

# TAB 3: Fixture Test Runner
with tabs[2]:
    st.subheader("ROB-3 Acceptance Fixture Runner (Fixture-Test Mode)")
    st.warning("FIXTURE-TEST MODE: Uses explicit `capacity_override` from `sample_data/monthly_fixture.csv` to verify ledger math. Do not mix with live normal runs.")

    fixture_df = pd.read_csv("sample_data/monthly_fixture.csv")
    st.dataframe(fixture_df, use_container_width=True)

    if st.button("Run 3-Month ROB Fixture Verification"):
        sim_p = initial_state()["params"]
        sim_v = initial_state()["variable_lines"]
        sim_f = initial_state()["fixed_lines"]
        results_rows = []
        for _, row in fixture_df.iterrows():
            sim_p["requested_units"] = int(row["requested"])
            sim_p["ad_cost"] = float(row["ad_cost"])
            out = compute_rob_month(sim_p, sim_v, sim_f, capacity_override=int(row["capacity_override"]))
            results_rows.append({
                "Month": row["month"],
                "Sold": out["sold"],
                "Revenue ($)": float(out["revenue"]),
                "Total Expense ($)": float(out["total_expense"]),
                "Profit ($)": float(out["operating_profit"]),
                "Closing Cash ($)": float(out["ending_cash"]),
                "Closing Stock (sets)": out["ending_stock_units"],
                "Inventory Value ($)": float(out["ending_inventory_value"]),
            })
            sim_p["opening_cash"] = float(out["ending_cash"])
            sim_p["opening_stock_units"] = int(out["ending_stock_units"])
        st.dataframe(pd.DataFrame(results_rows), use_container_width=True)
        st.success("Expected: Jan ($3,600 rev, $1,050 profit, $6,950 cash, 70 stock) | Feb ($3,600 rev, $950 profit, $8,800 cash, 40 stock) | Mar ($2,640 rev, $610 profit, $10,070 cash, 18 stock).")

# TAB 4: Ledger & Save/Load JSON
with tabs[3]:
    st.subheader("Dated Event Ledger & Persistent JSON Snapshot")
    if state["ledger"]:
        st.dataframe(pd.DataFrame(state["ledger"]), use_container_width=True)
    else:
        st.write("No approved monthly runs recorded yet.")

    c_exp, c_imp = st.columns(2)
    with c_exp:
        st.markdown("#### Export Approved Snapshot (JSON)")
        st.download_button(
            label="Download Snapshot JSON",
            data=json.dumps(state, indent=2),
            file_name=f"{state['team_id']}_{state['snapshot_id']}.json",
            mime="application/json",
        )
    with c_imp:
        st.markdown("#### Restore or Import Snapshot (JSON)")
        uploaded = st.file_uploader("Upload Snapshot JSON", type=["json"])
        if uploaded is not None:
            try:
                imported = json.load(uploaded)
                ok, msg = validate_snapshot_import(imported, state["team_id"], state["state_version"])
                if ok:
                    st.session_state.sim_state = imported
                    st.success(f"Snapshot restored: {imported['snapshot_id']} (v{imported['state_version']})")
                    st.rerun()
                else:
                    st.error(msg)
            except Exception as exc:
                st.error(f"Invalid JSON file: {exc}")

    if st.button("Reset Studio to Initial Opening State"):
        st.session_state.sim_state = initial_state()
        st.rerun()

# TAB 5: Roadmap
with tabs[4]:
    st.subheader("Staged Implementation Status")
    st.markdown("""
- **Stage 1 (Implemented):** ROB-3 inputs, AP Calculus Applied piecewise model & visuals, deterministic ledger, duplicate-run protection, fixture test runner, and Save/Load JSON snapshot validation.
- **Stage 2 (Pending):** Departmental AI handoff tab, Report Center (CSV/PDF export, Income Statement, Cash Flow, Balance Sheet), and Costed Marketing Studio.
- **Stage 3 (Pending):** Frozen-snapshot Practice Assessment panel and Cross-Course Connections evidence log.
- **Stage 4 (Optional):** Fictional demonstration storefront with test checkout tokens.
    """)
