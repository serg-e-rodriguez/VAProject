"""
Electorate & Turnout (UI_Design.md §6.4): how many persuadable and mobilizable voters are in
each place, and how did they turn out last midterm?
"""

import altair as alt
import streamlit as st

from campaign_intel.data.loaders import load_statewide, load_units, load_vote_methods
from campaign_intel.ui.components import chart_card_header, kpi_card
from campaign_intel.ui.styles import get_tokens
from campaign_intel.ui.topbar import render_topbar
from campaign_intel.viz.charts import grouped_bar
from campaign_intel.viz.maps import choropleth

render_topbar("NC Electorate & Turnout")
theme = st.session_state.get("theme", "dark")
unit_type, geo_mode = st.session_state.get("unit_type", "cd"), st.session_state.get("geo_mode", "district")
geo_key = "county" if geo_mode == "county" else unit_type
units = load_units(unit_type, geo_mode)
sw = load_statewide()

reg = units["registered_voters"].sum()
c1, c2, c3, c4 = st.columns(4, gap="medium")
with c1:
    kpi_card("Registered voters", f"{reg:,.0f}", fidelity="aggregated", band="NCSBE voter_stats, 2024 Election Day")
with c2:
    una = units["reg_una"].sum()
    kpi_card("Unaffiliated (persuasion universe)", f"{una / reg:.1%}", delta=f"{una:,.0f} voters", good_direction="neutral",
             fidelity="aggregated", band=f"Dem {units['reg_dem'].sum() / reg:.1%} · Rep {units['reg_rep'].sum() / reg:.1%}")
with c3:
    kpi_card("Mobilization universe", f"{units['mobilization_universe'].sum():,.0f}", fidelity="modeled",
             band="Dem registrants × (1 − county 2022 Dem turnout rate)")
with c4:
    kpi_card("2022 midterm turnout", f"{sw['voted22_total'] / units['registered_voters'].sum():.1%}",
             delta=f"{sw['voted22_total']:,} ballots", good_direction="neutral", fidelity="aggregated",
             band="NCSBE history_stats 2022 vs 2024 registration")

st.write("")
with st.container(border=True):
    h, ctrl = st.columns([7, 5])
    with h:
        chart_card_header("Target universes", f"{'Counties' if geo_mode == 'county' else geo_key.upper() + ' districts'} · "
                          "NCSBE registration and 2022 history rolled up through precincts", fidelity="aggregated")
    opts = {"Persuasion universe": "persuasion_universe", "Mobilization universe": "mobilization_universe",
            "Registered voters": "registered_voters", "2022 turnout rate": "turnout22_rate"}
    choice = ctrl.segmented_control("Universe", list(opts), default="Persuasion universe", key="el_metric") or "Persuasion universe"
    col = opts[choice]
    st.altair_chart(choropleth(geo_key, units, col, choice, scale="sequential", theme=theme,
                               fmt=".1%" if col == "turnout22_rate" else ",.0f",
                               extra_tooltips=[("dem_margin_pct", "2024 Dem margin", "+.1f"),
                                               ("registered_voters", "Registered", ",.0f")], selectable=False,
                               swing_pts=5.0), width="stretch")
    st.caption("Purple outline = units within 5 pts in 2024. Mobilization is modeled: the voter file's individual history "
               "is aggregated to county party turnout rates before it reaches the app.")

s1, s2 = st.columns([5, 7], gap="medium")
with s1, st.container(border=True):
    chart_card_header("How NC voted in 2022", "US Senate votes by method and party (MEDSL county returns)", fidelity="aggregated")
    vm = load_vote_methods()
    vm = vm[vm["party_clean"].isin(["DEM", "REP"])].assign(
        party=lambda d: d["party_clean"].map({"DEM": "Beasley (D)", "REP": "Budd (R)"}),
        vote_method=lambda d: d["vote_method"].str.title())
    t = get_tokens(theme)
    st.altair_chart(grouped_bar(vm, "vote_method", "votes", "party", y_title="Votes", theme=theme, x_title=None,
                                color_scale=alt.Scale(domain=["Beasley (D)", "Budd (R)"], range=[t["dem"], t["rep"]])),
                    width="stretch")
    st.caption("Early (One-Stop) voting leaned Dem; Election Day leaned GOP — late mobilization money targets the latter.")
with s2, st.container(border=True):
    chart_card_header("Universe table", "Sortable · all figures are precinct roll-ups", fidelity="aggregated")
    st.dataframe(units[["name", "registered_voters", "reg_dem", "reg_rep", "reg_una", "persuasion_universe",
                        "mobilization_universe", "turnout22_rate", "dem_margin_pct"]],
                 hide_index=True, width="stretch", height=380,
                 column_config={"name": "Unit", "registered_voters": st.column_config.NumberColumn("Registered", format="%d"),
                                "reg_dem": st.column_config.NumberColumn("Dem", format="%d"),
                                "reg_rep": st.column_config.NumberColumn("Rep", format="%d"),
                                "reg_una": st.column_config.NumberColumn("Unaffiliated", format="%d"),
                                "persuasion_universe": st.column_config.NumberColumn("Persuasion", format="%d"),
                                "mobilization_universe": st.column_config.NumberColumn("Mobilization", format="%d"),
                                "turnout22_rate": st.column_config.NumberColumn("2022 turnout", format="percent"),
                                "dem_margin_pct": st.column_config.NumberColumn("2024 margin", format="%+.1f")})
