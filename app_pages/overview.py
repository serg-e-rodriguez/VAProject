"""
Overview (UI_Design.md §6.1): where is the money going, and where are we out-spent relative
to how close the race is?
"""

import streamlit as st

from campaign_intel.data.loaders import (
    fmt_money,
    load_advertisers,
    load_overview_kpis,
    load_platform_mix,
    load_statewide,
    load_units,
    load_weekly_by_side,
)
from campaign_intel.ui.components import chart_card_header, insight, kpi_card
from campaign_intel.ui.topbar import render_topbar
from campaign_intel.viz.charts import area_with_band, ranked_bar, side_scale
from campaign_intel.viz.maps import choropleth

render_topbar("Campaign Overview & Ad Landscape")
theme = st.session_state.get("theme", "dark")
unit_type, geo_mode = st.session_state.get("unit_type", "cd"), st.session_state.get("geo_mode", "district")
geo_key = "county" if geo_mode == "county" else unit_type

k = load_overview_kpis()
sw = load_statewide()

c1, c2, c3, c4 = st.columns(4, gap="medium")
with c1:
    kpi_card("NC political ad spend since Jul 1", fmt_money(k["total_mid"]), fidelity="modeled",
             band=f"Range {fmt_money(k['total_low'])} – {fmt_money(k['total_high'])} · Google + Meta, NC share",
             spark_data=k["weekly_total"])
with c2:
    d = (k["dem_sov_4w"] - k["dem_sov_prev4w"]) * 100
    kpi_card("Dem share of voice (4 wks)", f"{k['dem_sov_4w']:.1%}", delta=f"{d:+.1f} pts vs prior 4 wks",
             good_direction="up", fidelity="modeled", band="Share of partisan NC spend (classified advertisers)",
             spark_data=k["sov_series"])
with c3:
    g, gp = k["gop_last_week"], k["gop_prev_week"]
    chg = (g / gp - 1) * 100 if gp else 0
    kpi_card("GOP-side spend, last full week", fmt_money(g), delta=f"{chg:+.0f}% w/w", good_direction="down",
             fidelity="modeled", band=f"Week of {k['last_week']}", spark_data=k["gop_series"])
with c4:
    kpi_card("Ads active, last 7 days (Dem vs GOP)", f"{k['active_dem']:,} vs {k['active_gop']:,}",
             delta=f"+{k['new_dem_7d']:,} new Dem / +{k['new_gop_7d']:,} GOP", good_direction="neutral",
             fidelity="observed", band="Meta Ad Library + Google Transparency Report")

st.write("")
with st.container(border=True):
    h, ctrl = st.columns([7, 5])
    with h:
        chart_card_header("Electoral landscape", f"{'100 NC counties' if geo_mode == 'county' else geo_key.upper() + ' districts'} · "
                          "2024 presidential margin from NCSBE precinct results (purple outline = within 5 pts)",
                          fidelity="aggregated")
    opts = ["2024 margin", "Expected midterm turnout"] + (["Google spend (2026 map)"] if geo_key == "cd" else [])
    metric = ctrl.segmented_control("Map metric", opts, default=opts[0], key="ov_metric") or opts[0]
    units = load_units(unit_type, geo_mode)
    col = {"2024 margin": "dem_margin_pct", "Expected midterm turnout": "expected_turnout",
           "Google spend (2026 map)": "google_spend_2026_map"}[metric]
    m_col, l_col = st.columns([8, 4], gap="medium")
    with m_col:
        ch = choropleth(geo_key, units, col, metric, scale="diverging" if col == "dem_margin_pct" else "sequential",
                        theme=theme, fmt="+.1f" if col == "dem_margin_pct" else ",.0f",
                        extra_tooltips=[("dem_margin_pct", "2024 Dem margin", "+.1f"),
                                        ("registered_voters", "Registered", ",.0f")], selectable=False)
        st.altair_chart(ch, width="stretch")
        if col == "google_spend_2026_map":
            st.caption("Google's own district-level spend (geo_spend) for the 2026 congressional map — Observed, lifetime of that map.")
    with l_col:
        st.markdown("##### 🎯 Closest units")
        st.caption("Smallest 2024 presidential margins — where small shifts decide seats")
        close = units.assign(abs_m=units["dem_margin_pct"].abs()).nsmallest(8, "abs_m")
        st.dataframe(close[["name", "dem_margin_pct", "expected_turnout"]], hide_index=True, width="stretch",
                     column_config={"name": "Unit", "dem_margin_pct": st.column_config.NumberColumn("Margin", format="%+.1f"),
                                    "expected_turnout": st.column_config.NumberColumn("Exp. turnout", format="%d")})
        state_m = (sw["pres24_dem"] - sw["pres24_rep"]) / sw["pres24_total"] * 100
        insight(f"Statewide 2024 baseline: Dem {state_m:+.1f} pts",
                f"Harris {sw['pres24_dem']:,} vs Trump {sw['pres24_rep']:,} (NCSBE certified). "
                f"Expected midterm turnout {sw['voted22_total']:,} (2022 ballots cast).", tone="rep" if state_m < 0 else "dem")

s1, s2 = st.columns([7, 5], gap="medium")
with s1, st.container(border=True):
    chart_card_header("Weekly NC spend by side", "Each ad's NC spend spread across its delivery days · band = low–high "
                      "of the reported spend ranges", fidelity="modeled")
    w = load_weekly_by_side()
    w = w[w["side_group"].isin(["Dem side", "GOP side", "Unclassified"])]
    st.altair_chart(area_with_band(w, "week_start", "nc_spend_mid", "nc_spend_low", "nc_spend_high", "side_group",
                                   theme=theme), width="stretch")
    st.caption("Unclassified = advertisers not yet mapped to a side in seeds/advertiser_sides.csv.")
with s2, st.container(border=True):
    chart_card_header("Spend by platform", "NC-apportioned spend this cycle, with low–high range", fidelity="modeled")
    mix = load_platform_mix()
    st.altair_chart(ranked_bar(mix, "platform", "nc_spend_mid", theme, title="NC spend", low_col="nc_spend_low",
                               high_col="nc_spend_high", height=180), width="stretch")
    st.caption("Google: creatives since Jul 2025 targeting NC (multi-state ads apportioned 1/n states). "
               "Meta: ads delivered in NC since Jul 2026 × NC delivery share.")

with st.container(border=True):
    chart_card_header("Top advertisers in NC", "Ranked by modeled NC spend · colour = side", fidelity="modeled")
    adv = load_advertisers()
    st.altair_chart(ranked_bar(adv.head(15), "advertiser", "nc_spend_mid", theme, title="NC spend (mid)",
                               low_col="nc_spend_low", high_col="nc_spend_high", color_col="side_group",
                               color_scale=side_scale(theme)), width="stretch")
    with st.expander("Table view"):
        st.dataframe(adv.head(50)[["advertiser", "side_group", "platforms", "n_ads", "nc_spend_mid", "top_theme"]],
                     hide_index=True, width="stretch",
                     column_config={"nc_spend_mid": st.column_config.NumberColumn("NC spend (mid)", format="dollar")})
