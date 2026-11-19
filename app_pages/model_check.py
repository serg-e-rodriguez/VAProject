"""
Model Check: how close the model's pre-election estimate came to the 2026 results.

This is the only page that reads the 2026 results. The planning pages are built for running a midterm
campaign and use only what was known before Election Day.
"""

import streamlit as st

from campaign_intel import model_check as M
from campaign_intel.config import RACES
from campaign_intel.data.loaders import fmt_margin, fmt_num, unit_type
from campaign_intel.state import race, theme
from campaign_intel.ui.components import (
    bullets,
    chart,
    kpi,
    page_header,
    party_tone,
    section,
    source,
)
from campaign_intel.viz.charts import reveal_board

R, T = race(), theme()
UT = unit_type(R)
words = RACES[R]
page_header("Model Check",
            f"How close the model's estimate came to the 2026 {words['label']} results. "
            "The planning pages never use these results; this page is the check.")

with st.container(border=True):
    env = st.slider("National mood the model assumes (points toward Democrats vs 2024)", -10.0, 30.0,
                    float(M.DEFAULT_ENV), 0.5, key="mc_env",
                    help=f"The War Room's default is {M.DEFAULT_ENV:+.0f}. Move it to see how the estimate and "
                         "its misses change.")
d, s = M.compare(R, env)

k1, k2, k3, k4 = st.columns(4, gap="small")
with k1:
    if R == "senate":
        kpi("Statewide: estimate vs result", f"{fmt_margin(s['proj_total_pct'])} → {fmt_margin(s['actual_total_pct'])}",
            f"Model estimate, then the 2026 Senate result · win chance {M.baseline_win_prob(R, env):.0%}",
            tone=party_tone(s["actual_total_pct"]),
            help="Estimate: 2024 margin on a midterm-sized electorate plus the national mood, before any new ads.")
    else:
        kpi("Seats: estimate vs result", f"D {s['proj_seats']} → D {s['actual_seats']}",
            "Districts the model favours us in, then districts Democrats won in 2026",
            tone=party_tone(s["actual_seats"] - 7))
with k2:
    kpi(f"{words['units_word'].capitalize()} called right", f"{s['called']} of {s['n']}",
        "Same winner in the estimate and the result")
with k3:
    kpi("Average miss", f"{s['avg_miss']:.1f} pts",
        f"Results were {abs(s['bias']):.1f} pts more {'Democratic' if s['bias'] > 0 else 'Republican'} "
        "than estimated (turnout-weighted)")
with k4:
    kpi("National mood that fits", f"{s['implied_env']:+.1f} pts",
        f"Model assumed {s['env']:+.1f} · turnout {fmt_num(s['actual_turnout'])} vs {fmt_num(s['proj_turnout'])} estimated")

with st.container(border=True):
    if UT == "county":
        big = d.nlargest(25, "proj_turnout")
        section("The 25 largest counties: where the model started, its estimate, and the result",
                "Grey tick = 2024 margin. Hollow dot = the model's estimate. Solid dot = 2026 Senate result.")
    else:
        big = d
        section("Each district: where the model started, its estimate, and the result",
                "Grey tick = 2024 presidential margin. Hollow dot = the model's estimate. "
                "Solid dot = 2026 House result.")
    chart(reveal_board(big, T, proj_title="Model estimate"))

c1, c2 = st.columns([5, 7], gap="medium")
with c1, st.container(border=True):
    section("What this tells us")
    worst = d.reindex(d["miss_pct"].abs().sort_values(ascending=False).index).head(3)
    notes = [
        (f"The model's estimate was {abs(s['bias']):.1f} points too "
         f"{'Republican' if s['bias'] > 0 else 'Democratic'} on average. The 2026 results fit a national mood of "
         f"{s['implied_env']:+.1f} points vs 2024; the model assumed {s['env']:+.1f}."),
        f"It picked the right winner in {s['called']} of {s['n']} {words['units_word']}.",
        "Biggest misses: " + "; ".join(f"{r.label} ({r.miss_pct:+.0f} pts)" for r in worst.itertuples()) + ".",
        (f"Turnout was {s['actual_turnout'] / s['proj_turnout'] - 1:+.0%} vs the model's midterm-sized electorate "
         "(2022 turnout rates on 2024 registration)."),
        ("The estimate is the model's baseline: it leaves out every ad effect, so a miss in the same direction "
         "everywhere points to the national-mood setting, not to the ad model."),
    ]
    bullets(notes)
with c2, st.container(border=True):
    section(f"Every {words['unit_word']}", "Sorted by the size of the miss.")
    tbl = d.assign(abs_miss=d["miss_pct"].abs()).sort_values("abs_miss", ascending=False)
    st.dataframe(tbl[["label", "start_pct", "proj_pct", "actual_pct", "miss_pct", "called"]], hide_index=True,
                 width="stretch", height=360,
                 column_config={"label": words["unit_word"].capitalize(),
                                "start_pct": st.column_config.NumberColumn("2024", format="%+.1f"),
                                "proj_pct": st.column_config.NumberColumn("Estimate", format="%+.1f"),
                                "actual_pct": st.column_config.NumberColumn("2026 result", format="%+.1f"),
                                "miss_pct": st.column_config.NumberColumn("Miss", format="%+.1f",
                                                                          help="Result minus estimate (D−R points)"),
                                "called": st.column_config.CheckboxColumn("Right winner")})
source(f"Results: {s['results_note']} ({'US House, by district' if UT == 'cd' else 'US Senate, by county'}). "
       "Margins are D−R points.")
