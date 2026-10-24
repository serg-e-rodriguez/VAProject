"""
War Room Flagship Page Layout per UI_Design.md §6.5 and Project_Design.md §7.
Interactive budget allocation simulator, vectorized Monte Carlo outcome engine,
greedy marginal dollar optimizer, and scenario comparator.
"""

import pandas as pd
import streamlit as st

from campaign_intel.config import AUDIENCES, CHANNELS, DEFAULT_BUDGET, DEFAULT_WEEKS
from campaign_intel.data.loaders import load_geo_baselines
from campaign_intel.model.assumptions import Assumptions, apply_preset, load_defaults
from campaign_intel.model.engine import RaceContext, simulate
from campaign_intel.model.optimizer import optimize
from campaign_intel.model.scenarios import delete_scenario, list_scenarios, save_scenario
from campaign_intel.ui.components import chart_card_header, kpi_card, model_ribbon
from campaign_intel.ui.topbar import render_topbar
from campaign_intel.viz.charts import histogram, marginal_votes_ranked, win_prob_bar

# 1. Top Bar & Ribbon
render_topbar("War Room — Budget Allocator & Outcome Simulator")
model_ribbon()

theme = st.session_state.get("theme", "dark")
scope = st.session_state.get("scope", "statewide")
target_unit = st.session_state.get("target_unit", None)
unit_type = st.session_state.get("unit_type", "cd")
geo_mode = st.session_state.get("geo_mode", "district")

# Load baseline units
df_units = load_geo_baselines(unit_type=unit_type, geo_mode=geo_mode)
unit_ids = df_units["unit_id"].tolist() if not df_units.empty else ["CD1"]

# Initialize Assumptions in session state
if "war_room_assumptions" not in st.session_state:
    st.session_state.war_room_assumptions = load_defaults()
a = st.session_state.war_room_assumptions

# Initialize Allocation in session state
if "allocation" not in st.session_state or st.session_state.allocation.empty:
    # Calibrated starting allocation ($1.2M initial plan across battleground CDs)
    st.session_state.allocation = pd.DataFrame([
        {"unit_id": "CD1", "channel": "meta", "audience": "mobilization", "week": 6, "dollars": 120_000.0},
        {"unit_id": "CD1", "channel": "youtube", "audience": "persuasion", "week": 7, "dollars": 180_000.0},
        {"unit_id": "CD13", "channel": "meta", "audience": "persuasion", "week": 6, "dollars": 150_000.0},
        {"unit_id": "CD13", "channel": "youtube", "audience": "mobilization", "week": 7, "dollars": 200_000.0},
        {"unit_id": "CD13", "channel": "search", "audience": "persuasion", "week": 8, "dollars": 100_000.0},
        {"unit_id": "CD12", "channel": "meta", "audience": "mobilization", "week": 7, "dollars": 150_000.0},
        {"unit_id": "CD4", "channel": "meta", "audience": "mobilization", "week": 8, "dollars": 100_000.0},
    ])


@st.fragment
def render_war_room_core():
    """
    Renders allocation builder and outcome simulation inside a Streamlit fragment
    to ensure instantaneous, lag-free reactive updates per §8.3.
    """
    alloc_df = st.session_state.allocation
    total_spent = float(pd.to_numeric(alloc_df["dollars"], errors="coerce").fillna(0.0).sum()) if not alloc_df.empty else 0.0
    budget_left = max(0.0, DEFAULT_BUDGET - total_spent)

    # Build RaceContext
    ctx = RaceContext(
        scope="district" if scope == "district" else "statewide",
        unit_type=unit_type if geo_mode == "district" else "county",
        target_unit=target_unit,
        weeks=DEFAULT_WEEKS,
        budget=DEFAULT_BUDGET,
        units=df_units
    )

    # Run Monte Carlo simulation
    sim_res = simulate(
        allocation=alloc_df,
        ctx=ctx,
        a=st.session_state.war_room_assumptions,
        n_draws=4000,
        seed=42
    )

    # KPI Row
    k1, k2, k3, k4 = st.columns(4, gap="medium")
    with k1:
        spent_pct = (total_spent / DEFAULT_BUDGET) * 100
        kpi_card(
            label="Budget Remaining",
            value=f"${budget_left:,.0f}",
            delta=f"{spent_pct:.1f}% planned",
            good_direction="neutral",
            fidelity="modeled",
            band=f"${total_spent:,.0f} of $2.00M allocated",
            spark_data=[DEFAULT_BUDGET, DEFAULT_BUDGET * 0.8, DEFAULT_BUDGET * 0.5, budget_left]
        )
    with k2:
        prob_delta = (sim_res.win_prob - sim_res.baseline_win_prob) * 100
        kpi_card(
            label="Projected Win Probability",
            value=f"{sim_res.win_prob * 100:.1f}%",
            delta=f"{prob_delta:+.1f} pts",
            good_direction="up",
            fidelity="modeled",
            band=f"Baseline {sim_res.baseline_win_prob * 100:.1f}% · Range {sim_res.win_prob_interval[0]*100:.0f}–{sim_res.win_prob_interval[1]*100:.0f}%",
            spark_data=[sim_res.baseline_win_prob * 100, sim_res.win_prob * 100]
        )
    with k3:
        kpi_card(
            label="Estimated Net Margin Lift (ΔV)",
            value=f"+{sim_res.total_delta_votes:,.0f} Votes",
            delta="Simulated causals",
            good_direction="up",
            fidelity="modeled",
            band="Saturating reach model",
            spark_data=[0, sim_res.total_delta_votes * 0.4, sim_res.total_delta_votes * 0.8, sim_res.total_delta_votes]
        )
    with k4:
        cpv_str = f"${sim_res.cost_per_net_vote:.1f}" if sim_res.cost_per_net_vote > 0 else "—"
        kpi_card(
            label="Cost Per Net Vote",
            value=f"{cpv_str} / vote",
            delta="Efficiency index",
            good_direction="up",
            fidelity="modeled",
            band="Spend / simulated votes",
            spark_data=[220, 180, 150, max(1.0, sim_res.cost_per_net_vote)]
        )

    st.write("")

    # Two-Column Builder & Outcome Grid per §6.5
    col_builder, col_outcome = st.columns([6, 6], gap="medium")

    # LEFT COLUMN: ALLOCATION BUILDER
    with col_builder:
        with st.container(border=True):
            chart_card_header(
                title="Allocation Builder",
                subtitle="Unit · Channel · Audience · Week · Dollars ($)",
                fidelity="modeled"
            )

            # Budget meter progress bar
            st.progress(min(1.0, total_spent / DEFAULT_BUDGET), text=f"Budget Allocated: ${total_spent:,.0f} / ${DEFAULT_BUDGET:,.0f}")

            # Editable Table
            edited_alloc = st.data_editor(
                st.session_state.allocation,
                column_config={
                    "unit_id": st.column_config.SelectboxColumn("Target Unit", options=unit_ids, required=True),
                    "channel": st.column_config.SelectboxColumn("Channel", options=CHANNELS, required=True),
                    "audience": st.column_config.SelectboxColumn("Audience", options=AUDIENCES, required=True),
                    "week": st.column_config.NumberColumn("Week", min_value=1, max_value=ctx.weeks, step=1, required=True),
                    "dollars": st.column_config.NumberColumn("Budget ($)", min_value=0.0, step=10_000.0, format="$%d", required=True),
                },
                num_rows="dynamic",
                use_container_width=True,
                key="war_room_data_editor"
            )

            if not edited_alloc.equals(st.session_state.allocation):
                st.session_state.allocation = edited_alloc
                st.rerun()

            # Optimizer Trigger Button
            opt_c1, opt_c2 = st.columns([7, 5])
            with opt_c1:
                if st.button("⚡ Auto-Optimize Remaining Budget", type="primary", use_container_width=True):
                    with st.spinner("Evaluating greedy marginal returns..."):
                        rec_alloc, diff_df = optimize(
                            current=st.session_state.allocation,
                            ctx=ctx,
                            a=st.session_state.war_room_assumptions,
                            step=10_000.0
                        )
                        st.session_state.optimized_recommendation = rec_alloc
                        st.session_state.optimized_diff = diff_df

            with opt_c2:
                if st.button("Reset Plan", use_container_width=True):
                    st.session_state.allocation = pd.DataFrame(columns=["unit_id", "channel", "audience", "week", "dollars"])
                    st.session_state.pop("optimized_recommendation", None)
                    st.session_state.pop("optimized_diff", None)
                    st.rerun()

            # Display optimizer results if run
            if "optimized_diff" in st.session_state and not st.session_state.optimized_diff.empty:
                st.markdown("##### 💡 Recommended Dollar Shifts")
                st.dataframe(
                    st.session_state.optimized_diff.rename(columns={
                        "unit_id": "Unit",
                        "channel": "Channel",
                        "audience": "Audience",
                        "week": "Week",
                        "delta_dollars": "+$ Dollars",
                        "marginal_votes": "+Net Votes (ΔV)"
                    }),
                    column_config={
                        "+$ Dollars": st.column_config.NumberColumn(format="$%,d"),
                        "+Net Votes (ΔV)": st.column_config.NumberColumn(format="+%.1f"),
                    },
                    use_container_width=True,
                    hide_index=True
                )
                if st.button("Accept Recommended Plan", type="primary"):
                    st.session_state.allocation = st.session_state.optimized_recommendation
                    st.session_state.pop("optimized_recommendation", None)
                    st.session_state.pop("optimized_diff", None)
                    st.rerun()

    # RIGHT COLUMN: OUTCOME PANEL
    with col_outcome:
        with st.container(border=True):
            chart_card_header(
                title="Outcome & Margin Uncertainty",
                subtitle="Monte Carlo Simulation (4,000 draws) · Correlated polling error and saturation",
                fidelity="modeled"
            )

            st.markdown(f"**Win Probability Range: {sim_res.win_prob * 100:.1f}%** *(Baseline: {sim_res.baseline_win_prob * 100:.1f}%)*")
            gauge = win_prob_bar(
                win_prob=sim_res.win_prob,
                baseline_win_prob=sim_res.baseline_win_prob,
                interval=sim_res.win_prob_interval,
                theme=theme
            )
            st.altair_chart(gauge, use_container_width=True)

            st.markdown("##### Projected Net Margin Distribution")
            st.caption("Distribution of projected vote margin (0 line separates Dem win from GOP win)")
            hist_chart = histogram(sim_res.margin_hist, theme=theme)
            st.altair_chart(hist_chart, use_container_width=True)

            st.markdown("##### Top Net Votes Gained by Unit")
            ranked_chart = marginal_votes_ranked(sim_res.delta_votes_by_unit, theme=theme)
            st.altair_chart(ranked_chart, use_container_width=True)

    # 4. WEEKLY PACING STACKED BAR CHART
    with st.container(border=True):
        chart_card_header(
            title="Weekly Spend Flight Pacing vs. Election Day",
            subtitle="Pacing allocation by week × channel (decay model weights late spend higher)",
            fidelity="modeled"
        )
        if not alloc_df.empty:
            alloc_display = alloc_df.copy()
            alloc_display["week_label"] = alloc_display["week"].apply(lambda w: f"Week {w} (E-{ctx.weeks - w}w)")
            pacing_chart = marginal_votes_ranked(
                alloc_display,
                unit_col="week_label",
                votes_col="dollars",
                theme=theme
            )
            st.altair_chart(pacing_chart, use_container_width=True)
        else:
            st.info("Add allocation line items above to see pacing schedule.")


# Render core fragment
render_war_room_core()

# 5. ASSUMPTIONS (COLLAPSIBLE EXPANDER PER §6.5)
with st.expander("⚙️ War Room Model Assumptions & Sensitivity Presets", expanded=False):
    st.markdown("##### Scenario Calibration Presets")
    preset_choice = st.pills(
        "Load Model Preset",
        options=["Default Baseline", "Conservative", "Optimistic"],
        default="Default Baseline",
        key="war_room_preset_choice"
    )

    if preset_choice == "Conservative":
        st.session_state.war_room_assumptions = apply_preset(st.session_state.war_room_assumptions, "conservative")
    elif preset_choice == "Optimistic":
        st.session_state.war_room_assumptions = apply_preset(st.session_state.war_room_assumptions, "optimistic")
    elif preset_choice == "Default Baseline":
        st.session_state.war_room_assumptions = load_defaults()

    a_curr = st.session_state.war_room_assumptions

    s1, s2, s3 = st.columns(3)
    with s1:
        st.markdown("**Causal Effect Sizes**")
        p_val = st.slider("Persuasion Net Votes / Reached Voter (p)", 0.0, 0.010, float(a_curr.persuasion_p[1]), step=0.0005, format="%.4f")
        t_val = st.slider("Turnout Lift / Reached Target (t)", 0.0, 0.015, float(a_curr.turnout_t[1]), step=0.0005, format="%.4f")
        ret_val = st.slider("Weekly Retention Decay (ρ)", 0.3, 0.9, float(a_curr.retention_rho[1]), step=0.05)

    with s2:
        st.markdown("**Platform CPM Costs ($)**")
        cpm_meta = st.slider("Meta CPM ($)", 5.0, 30.0, float(a_curr.cpm.get("meta", (8, 14, 20))[1]), step=1.0)
        cpm_yt = st.slider("YouTube CPM ($)", 8.0, 35.0, float(a_curr.cpm.get("youtube", (11, 18, 25))[1]), step=1.0)
        cpm_ctv = st.slider("Connected TV (CTV) CPM ($)", 15.0, 60.0, float(a_curr.cpm.get("ctv", (25, 35, 50))[1]), step=1.0)

    with s3:
        st.markdown("**Macro Environment & Error**")
        env_shift = st.slider("Statewide Environment Shift (pts)", -10.0, 10.0, float(a_curr.env_shift_pts), step=0.5, format="%+.1f pts")
        err_state = st.slider("Statewide Polling Error (σ pts)", 1.0, 6.0, float(a_curr.sigma_state), step=0.5)
        err_unit = st.slider("District Extra Error (σ_d pts)", 1.0, 5.0, float(a_curr.sigma_unit), step=0.5)

    # Update assumptions with slider adjustments
    st.session_state.war_room_assumptions = Assumptions(
        cpm={
            "meta": (cpm_meta * 0.6, cpm_meta, cpm_meta * 1.4),
            "youtube": (cpm_yt * 0.6, cpm_yt, cpm_yt * 1.4),
            "search": a_curr.cpm.get("search", (15, 24, 35)),
            "display": a_curr.cpm.get("display", (4, 6.5, 9)),
            "ctv": (cpm_ctv * 0.7, cpm_ctv, cpm_ctv * 1.4),
        },
        saturation_k=a_curr.saturation_k,
        persuasion_p=(0.0, p_val, p_val * 2.5),
        turnout_t=(0.0, t_val, t_val * 2.5),
        retention_rho=(ret_val * 0.7, ret_val, min(0.95, ret_val * 1.3)),
        opp_lambda=a_curr.opp_lambda,
        sigma_state=err_state,
        sigma_unit=err_unit,
        env_shift_pts=env_shift,
    )

# 6. SCENARIO PERSISTENCE & SIDE-BY-SIDE COMPARISON PER §7.8
with st.container(border=True):
    chart_card_header(
        title="Saved Scenarios & Comparative Analytics",
        subtitle="Save budget allocations to SQLite and compare metrics side by side",
        fidelity="modeled"
    )

    save_c1, save_c2 = st.columns([8, 4])
    with save_c1:
        scenario_name_input = st.text_input("Scenario Name", placeholder="e.g. Battleground Push 1.2M", label_visibility="collapsed")
    with save_c2:
        if st.button("Save Current Plan as Scenario", use_container_width=True) and scenario_name_input.strip():
            save_scenario(
                name=scenario_name_input.strip(),
                scope=scope,
                unit_type=unit_type,
                allocation=st.session_state.allocation,
                assumptions_dict={"env_shift": st.session_state.war_room_assumptions.env_shift_pts},
                results_dict={"budget": DEFAULT_BUDGET}
            )
            st.success(f"Scenario '{scenario_name_input}' saved successfully!")
            st.rerun()

    scenarios = list_scenarios()
    if scenarios:
        st.markdown("##### 📁 Compare Scenarios Side by Side")
        selected_scenario_names = st.multiselect(
            "Select up to 3 scenarios to compare:",
            options=[s["name"] for s in scenarios],
            default=[scenarios[0]["name"]] if scenarios else []
        )

        if selected_scenario_names:
            comp_cols = st.columns(len(selected_scenario_names))
            for idx, s_name in enumerate(selected_scenario_names):
                matching = next((s for s in scenarios if s["name"] == s_name), None)
                if matching:
                    with comp_cols[idx]:
                        with st.container(border=True):
                            st.markdown(f"**{matching['name']}**")
                            st.caption(f"Created: {matching['created_at'][:16].replace('T', ' ')}")
                            s_alloc = matching["allocation"]
                            s_spent = float(pd.to_numeric(s_alloc["dollars"], errors="coerce").fillna(0.0).sum()) if not s_alloc.empty else 0.0
                            st.metric("Total Spend", f"${s_spent:,.0f}")
                            st.metric("Line Items", f"{len(s_alloc)} flights")
                            if st.button(f"Load '{s_name}'", key=f"load_scen_{matching['id']}"):
                                st.session_state.allocation = s_alloc
                                st.rerun()
                            if st.button("Delete", key=f"del_scen_{matching['id']}"):
                                delete_scenario(matching["id"])
                                st.rerun()
    else:
        st.info("No saved scenarios yet. Build a budget plan above and save it to compare.")
