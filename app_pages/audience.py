"""
Audience Intelligence (UI_Design.md §6.2): which demographics see which messages, and where
are the gaps between what they see and what they care about?
"""

import pandas as pd
import streamlit as st

from campaign_intel.data.loaders import (
    load_ads,
    load_delivery_by_demo,
    load_survey_issue_benchmarks,
    load_survey_platform_benchmarks,
    load_theme_by_age,
)
from campaign_intel.processing.ads import AGE_ORDER
from campaign_intel.ui.components import chart_card_header, insight, kpi_card
from campaign_intel.ui.topbar import render_topbar
from campaign_intel.viz.charts import grouped_bar, heatmap, side_scale

render_topbar("Audience Intelligence & Message Delivery")
theme = st.session_state.get("theme", "dark")

demo = load_delivery_by_demo()
demo = demo[demo["age"].isin(AGE_ORDER)]
ads = load_ads()
dem_demo = demo[demo["side_group"] == "Dem side"]

c1, c2, c3, c4 = st.columns(4, gap="medium")
with c1:
    by_age = dem_demo.groupby("age")["impressions"].sum()
    share = by_age / by_age.sum() if by_age.sum() else by_age
    top = share.idxmax() if len(share) else "—"
    kpi_card("Dem side's most-reached age group", top, delta=f"{share.max():.0%} of NC impressions" if len(share) else None,
             good_direction="neutral", fidelity="modeled", band="Meta delivery breakdown × NC impressions",
             spark_data=[share.get(a, 0) for a in AGE_ORDER])
with c2:
    g = dem_demo.groupby("gender")["impressions"].sum()
    tot = g.sum() or 1
    kpi_card("Dem-side delivery by gender", f"{g.get('female', 0) / tot:.0%} F / {g.get('male', 0) / tot:.0%} M",
             fidelity="modeled", band="Meta demographic_distribution (impression-weighted)")
with c3:
    meta_dem = ads[(ads["platform"] == "Meta") & (ads["side_group"] == "Dem side")]
    fr = meta_dem["is_fundraising"].mean() if len(meta_dem) else 0
    kpi_card("Dem-side Meta ads that fundraise", f"{fr:.0%}", delta=f"{int(meta_dem['is_fundraising'].sum()):,} ads",
             good_direction="neutral", fidelity="observed", band="ActBlue / donate language — excluded from message analysis")
with c4:
    flat = ads[ads["platform"] == "Meta"].explode("message_themes").dropna(subset=["message_themes"])
    nth = flat.groupby("message_themes")["nc_spend_mid"].sum()
    nth = (nth / nth.sum() >= 0.01).sum() if nth.sum() else 0
    kpi_card("Message themes in use", f"{nth} themes", fidelity="modeled",
             band="Keyword classifier · themes with ≥1% of Meta NC spend")

st.write("")
with st.container(border=True):
    h, v = st.columns([8, 4])
    with h:
        chart_card_header("Theme delivery by age group", "Share of each age group's NC Meta impressions whose ad text "
                          "carries the theme (ads can carry several)", fidelity="modeled")
    view = v.segmented_control("Perspective", ["Us", "Opponent", "Gap"], default="Us", key="aud_view") or "Us"
    df = load_theme_by_age(view)
    if df.empty:
        st.info("No Meta delivery data in the snapshot.")
    else:
        st.altair_chart(heatmap(df, "age_cohort", "theme", "pct", is_gap=view == "Gap", theme=theme,
                                val_title="Dem − GOP (pts)" if view == "Gap" else "% of impressions", x_sort=AGE_ORDER),
                        width="stretch")
        st.caption("Us = Dem side (Cooper campaign + allies) · Opponent = GOP side · Gap > 0 (blue) = Dem side says it more.")

s1, s2 = st.columns([7, 5], gap="medium")
with s1, st.container(border=True):
    chart_card_header("Where each age group got news in the past 24 hours", "CCES 2024 (UNC module, national sample, "
                      "n = 1,000) · weighted (teamweight), 95% CIs · cells with n<30 suppressed", fidelity="aggregated")
    plat = load_survey_platform_benchmarks()
    if not plat.empty:
        st.altair_chart(grouped_bar(plat, "age_cohort", "pct", "platform", "ci_low", "ci_high",
                                    y_title="% in past 24 hours", theme=theme, x_title="Age group"), width="stretch")
with s2, st.container(border=True):
    chart_card_header("Message gaps worth a look", "Computed from the heatmap and the CCES economic items", fidelity="modeled")
    gap = load_theme_by_age("Gap")
    if not gap.empty:
        by_theme = gap.groupby("theme")[["Dem side", "GOP side"]].mean()
        by_theme["gap"] = by_theme["Dem side"] - by_theme["GOP side"]
        opp_lead = by_theme.sort_values("gap").head(2)
        for th, r in opp_lead.iterrows():
            if r.gap < 0:
                worst = gap[gap["theme"] == th].sort_values("pct").iloc[0]
                insight(f"GOP side owns “{th}”", f"{r['GOP side']:.0f}% of GOP-side impressions vs {r['Dem side']:.0f}% of ours; "
                        f"widest among {worst.age_cohort} ({worst.pct:+.0f} pts).", tone="rep")
        us_lead = by_theme.sort_values("gap", ascending=False).head(1)
        for th, r in us_lead.iterrows():
            if r.gap > 0:
                insight(f"We lead on “{th}”", f"{r['Dem side']:.0f}% of our impressions vs {r['GOP side']:.0f}% of theirs.", tone="dem")
    iss = load_survey_issue_benchmarks()
    econ = gap[gap["theme"].str.startswith("Economy")] if not gap.empty else pd.DataFrame()
    if not iss.empty and not econ.empty:
        pr = iss[iss["theme"].str.startswith("Prices")].set_index("age_cohort")["pct"]
        joined = econ.set_index("age_cohort").join(pr.rename("concern"), how="inner")
        if not joined.empty:
            j = joined.assign(diff=joined["concern"] - joined["Dem side"]).sort_values("diff").iloc[-1]
            insight(f"Cost of living: {j.name} voters", f"{j.concern:.0f}% say prices rose a lot (CCES, national), yet only "
                    f"{j['Dem side']:.0f}% of our impressions to {j.name} mention the economy.")

with st.container(border=True):
    chart_card_header("Delivery by age and gender", "NC Meta impressions by side (modeled from each ad's delivery breakdown)",
                      fidelity="modeled")
    d = demo[demo["side_group"].isin(["Dem side", "GOP side"]) & demo["gender"].isin(["female", "male"])]
    d = d.assign(group=d["age"] + " " + d["gender"].str[0].str.upper())
    order = [f"{a} {g}" for a in AGE_ORDER for g in ["F", "M"]]
    d["group"] = pd.Categorical(d["group"], categories=order, ordered=True)
    d = d.sort_values("group").assign(group=lambda x: x["group"].astype(str))
    d["share"] = d["impressions"] / d.groupby("side_group")["impressions"].transform("sum") * 100
    st.altair_chart(grouped_bar(d, "group", "share", "side_group", y_title="% of side's NC impressions", theme=theme,
                                color_scale=side_scale(theme), x_title="Age · gender", height=260), width="stretch")
