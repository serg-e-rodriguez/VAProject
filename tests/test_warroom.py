"""War Room glue (rewind, plan rows, value of a dollar, reveal) and its charts."""

import json
from dataclasses import replace
from unittest import mock

import numpy as np
import pandas as pd
import pytest

from campaign_intel import war_room_service as S
from campaign_intel.data import loaders as L
from campaign_intel.model import warroom as WR
from campaign_intel.model.assumptions import load_defaults
from campaign_intel.model.engine import simulate
from campaign_intel.model.optimizer import optimize
from campaign_intel.viz import charts as C

needs_snapshot = pytest.mark.skipif(not L.snapshot_ready(), reason="snapshot not built")
REAL_CHECK_AD_LINK = S.check_ad_link


@pytest.fixture(autouse=True)
def _no_network_link_checks(monkeypatch):
    """Page tests must not call Google or Meta; the link checker has its own tests below."""
    monkeypatch.setattr(S, "check_ad_link", lambda *a, **k: ("", "not checked in tests"))


@pytest.fixture
def a():
    return WR.with_env(load_defaults(), 5.0)


def test_weeks_left_and_timing():
    assert WR.weeks_left(WR.ELECTION_DAY - pd.Timedelta(weeks=8)) == 8
    assert WR.weeks_left(WR.ELECTION_DAY - pd.Timedelta(days=3)) == 1
    for t in WR.TIMINGS:
        w = WR.timing_weights(t, 6)
        assert w.sum() == pytest.approx(1) and (w > 0).all()
    assert WR.timing_weights("late", 6)[-1] > WR.timing_weights("late", 6)[0]
    assert WR.timing_weights("early", 6)[0] > WR.timing_weights("early", 6)[-1]


def test_spread_keeps_dollars():
    mix = WR.region_lines("CD1", 100_000, "both", ["meta", "youtube"])
    alloc = WR.spread(mix, "late", 5)
    assert alloc["dollars"].sum() == pytest.approx(100_000)
    assert set(alloc["week"]) == set(range(1, 6))
    assert WR.to_mix(alloc)["dollars"].sum() == pytest.approx(100_000)


def test_plan_rows_round_trip():
    mix = pd.concat([WR.region_lines("CD1", 200_000, "mobilization", ["youtube"]),
                     WR.region_lines("CD9", 50_000, "both", ["meta", "display"])], ignore_index=True)
    rows = WR.plan_rows(mix).set_index("unit_id")
    assert rows.loc["CD1", "goal"] == "mobilization" and rows.loc["CD1", "channels"] == ["youtube"]
    assert rows.loc["CD9", "goal"] == "both" and sorted(rows.loc["CD9", "channels"]) == ["display", "meta"]
    # budget-only edit rescales the exact mix; goal edit regenerates; dropped row disappears
    edited = pd.DataFrame([{"unit_id": "CD1", "budget": 400_000.0, "goal": "persuasion", "channels": ["youtube"]}])
    out = WR.apply_rows(mix, edited)
    assert out["dollars"].sum() == pytest.approx(400_000)
    assert set(out["audience"]) == {"persuasion"} and set(out["unit_id"]) == {"CD1"}
    same = WR.plan_rows(mix).assign(budget=lambda d: d["budget"] * 2)
    assert WR.apply_rows(mix, same)["dollars"].sum() == pytest.approx(500_000)


def test_diff_sentences():
    old = WR.region_lines("CD1", 100_000, "both", ["meta"])
    new = pd.concat([WR.region_lines("CD1", 150_000, "both", ["meta"]),
                     WR.region_lines("CD9", 80_000, "mobilization", ["youtube"])], ignore_index=True)
    d = WR.diff_sentences(old, new, {"CD1": "CD-1", "CD9": "CD-9"})
    assert [x["label"] for x in d] == ["CD-9", "CD-1"]
    assert d[0]["change"] == pytest.approx(80_000) and d[0]["goal"] == "Turn out Democrats"


@needs_snapshot
@pytest.mark.parametrize("race,mode", [("senate", "seats"), ("house", "seats"), ("house", "focus")])
def test_value_and_plan_raise_win_chance(race, mode, a):
    u = L.load_regions(race)
    ctx = WR.build_context(u, race, 8, 2e6, mode, target="CD1", a=a)
    v = WR.region_value(WR.empty_mix(), ctx, a, "late")
    assert len(v) == len(u) and (v["votes_per_step"] > 0).all() and (v["win_gain"] >= 0).all()
    if mode == "focus":
        assert (v.loc[v["unit_id"] != "CD1", "win_gain"] == 0).all()
    rec, _ = optimize(None, ctx, a, step=20_000, channels=WR.WR_CHANNELS)
    mix = WR.to_mix(rec)
    assert mix["dollars"].sum() == pytest.approx(2e6, rel=0.01)
    assert set(mix["channel"]) <= set(WR.WR_CHANNELS)
    r = simulate(WR.spread(mix, "late", 8), ctx, a, n_draws=1500)
    assert r.win_prob >= r.baseline_win_prob and r.total_delta_votes > 0
    # money already in a region lowers the value of the next $100K there (saturation)
    top = mix.groupby("unit_id")["dollars"].sum().idxmax()
    v2 = WR.region_value(mix, ctx, a, "late").set_index("unit_id")
    assert v2.loc[top, "votes_per_step"] < v.set_index("unit_id").loc[top, "votes_per_step"]
    for th in ("light", "dark"):
        C.win_chance_bar(r.baseline_win_prob, r.win_prob, *r.win_prob_interval, th).to_dict()
        C.outcome_dist(r.outcome_hist, th, ctx.majority - .5 if ctx.scope == "chamber" else 0, "x",
                       seats=ctx.scope == "chamber").to_dict()


@needs_snapshot
def test_house_seat_target_is_one_more_than_start(a):
    ctx = WR.build_context(L.load_regions("house"), "house", 8, 2e6, "seats", a=a)
    assert ctx.majority == WR.seats_at_start(ctx, a) + 1


@needs_snapshot
def test_projection_and_spend_as_of(a):
    u = L.load_regions("senate")
    ctx = WR.build_context(u, "senate", 8, 2e6, a=a)
    pj = WR.projection(ctx, a)
    assert np.allclose(pj["proj_votes"], pj["base_votes"])
    early, late = L.spend_as_of("senate", "2026-08-01"), L.spend_as_of("senate", "2026-10-01")
    assert late["dem"] + late["gop"] >= early["dem"] + early["gop"]
    assert early["dem"] + early["dem_after"] == pytest.approx(late["dem"] + late["dem_after"])


# ----------------------------------------------------------------------------- War Room service (plan -> predict -> explain)
def _ps(race="house", **kw):
    kw.setdefault("asof", f"{WR.ELECTION_DAY - pd.Timedelta(weeks=8):%Y-%m-%d}")
    kw.setdefault("budget", 2_000_000.0)
    return S.PlanSettings(race=race, **kw)


@needs_snapshot
@pytest.mark.parametrize("race", ["house", "senate"])
def test_recommended_plan_spends_budget_and_raises_win_chance(race):
    ps = _ps(race)
    mix = S.recommend(ps)
    res = S.predict(ps, S.mix_key(mix))
    assert mix["dollars"].sum() == pytest.approx(ps.budget, rel=0.01)
    assert res.win_prob > res.baseline_win_prob and res.total_delta_votes > 0
    assert set(mix["channel"]) <= set(WR.WR_CHANNELS)


@needs_snapshot
def test_platform_setting_limits_the_plan():
    ps = _ps("senate", platforms=("meta", "display"))
    assert set(S.recommend(ps)["channel"]) <= {"meta", "display"}


@needs_snapshot
def test_messaging_mix_and_plan_table_reconcile_with_the_plan():
    ps = _ps("house")
    mix = S.recommend(ps)
    res = S.predict(ps, S.mix_key(mix))
    mm, plan = S.messaging_mix(ps, mix), S.plan_table(ps, mix, res)
    assert mm["dollars"].sum() == pytest.approx(mix["dollars"].sum(), rel=1e-6)
    assert plan["budget"].sum() == pytest.approx(mix["dollars"].sum(), rel=1e-6)
    assert (mm["votes_per_100k"] > 0).all()
    assert plan["delta_votes"].sum() == pytest.approx(res.total_delta_votes, rel=0.05)


@needs_snapshot
def test_headline_restates_model_numbers():
    ps = _ps("house")
    ctx, _, _ = S.race_context(ps)
    mix = S.recommend(ps)
    res = S.predict(ps, S.mix_key(mix))
    h = S.headline(ps, ctx, res, S.messaging_mix(ps, mix), S.plan_table(ps, mix, res))
    assert f"≈{res.total_delta_votes:,.0f} net votes" in h
    assert f"from {res.baseline_win_prob:.0%} to {res.win_prob:.0%}" in h
    empty = S.predict(ps, "")
    assert S.headline(ps, ctx, empty, S.messaging_mix(ps, None), S.plan_table(ps, S.mix_from(""), empty)).startswith(
        "No money is planned")


@needs_snapshot
def test_headline_reports_unspent_budget():
    ps = _ps("house", budget=10_000_000.0, house_mode="focus", target="CD1", platforms=("display",))
    ctx, _, _ = S.race_context(ps)
    mix = S.recommend(ps)
    res = S.predict(ps, S.mix_key(mix))
    assert res.total_spent < ps.budget - 1000
    assert "is not planned" in S.headline(ps, ctx, res, S.messaging_mix(ps, mix), S.plan_table(ps, mix, res))


@needs_snapshot
def test_budget_curve_is_monotone_in_votes():
    c = S.budget_curve(_ps("senate"))
    assert list(c["budget"]) == sorted(c["budget"]) and c["net_votes"].is_monotonic_increasing


@needs_snapshot
def test_context_uses_only_data_before_the_planning_date():
    ps = _ps("senate", asof="2026-09-15")
    ctx = S.build_context(ps, S.recommend(ps), "What about Wake?")
    blob = json.dumps(ctx, default=str)
    assert "actual26" not in blob and "result26" not in blob
    assert ctx["ad_spend_so_far"]["window"].endswith("2026-09-15")
    assert any(r["region"] == "Wake" for r in ctx["regions_asked_about"])
    assert {"prediction", "plan_by_region", "messaging_investment", "next_100k_best_regions", "budget_curve",
            "sensitivity", "messaging_evidence"} <= set(ctx)
    assert len(blob) < 40_000


@needs_snapshot
def test_ads_between_prorates_by_flight_days():
    a = S.ads_between("house", L.CYCLE_START, L.snapshot_date().normalize())
    assert a["p_spend"].sum() == pytest.approx(L.load_ads("house")["w_nc_spend_mid"].sum(), rel=1e-6)
    early = S.ads_between("house", L.CYCLE_START, pd.Timestamp("2026-09-01"))
    assert early["p_spend"].sum() < a["p_spend"].sum() and (early["frac"] <= 1).all()


def test_regions_mentioned_parses_districts_and_counties():
    r = pd.DataFrame({"unit_id": ["CD1", "CD13", "37183"], "label": ["CD-1", "CD-13", "Wake"]})
    assert S.regions_mentioned("compare district 13 with nc-01 and wake", r) == ["CD1", "CD13", "37183"]
    assert S.regions_mentioned("what about CD-130", r) == []


def test_gemini_missing_key_raises():
    with pytest.raises(S.GeminiError, match="No Gemini API key"):
        S.call_gemini("sys", "q", api_key="")


def test_gemini_key_env_names(monkeypatch):
    for n in ("GEMINI_API", "GEMINI_API_KEY", "GEMINI_KEY", "GOOGLE_API_KEY"):
        monkeypatch.delenv(n, raising=False)
    monkeypatch.setenv("GEMINI_KEY", "k2")
    assert S.gemini_api_key() == "k2"
    monkeypatch.setenv("GEMINI_API", "k1")
    assert S.gemini_api_key() == "k1"


def _resp(status, payload):
    r = mock.Mock(status_code=status)
    r.json.return_value = payload
    return r


def test_gemini_falls_back_after_busy_model(monkeypatch):
    monkeypatch.setattr(S.time, "sleep", lambda *_: None)
    ok = _resp(200, {"candidates": [{"content": {"parts": [{"text": '{"a": 1}'}]}}]})
    busy = _resp(503, {"error": {"message": "high demand"}})
    with mock.patch.object(S.requests, "post", side_effect=[busy, busy, ok]) as post:
        assert S.call_gemini("sys", "q", api_key="k", models=["m1", "m2"]) == ('{"a": 1}', "m2")
    assert post.call_count == 3
    assert "key=" not in post.call_args.args[0]  # key travels in a header, never the URL
    assert post.call_args.kwargs["headers"]["x-goog-api-key"] == "k"


def test_gemini_non_json_200_falls_through_and_bad_key_is_fatal():
    bad = mock.Mock(status_code=200)
    bad.json.side_effect = ValueError("nope")
    ok = _resp(200, {"candidates": [{"content": {"parts": [{"text": "{}"}]}}]})
    with mock.patch.object(S.requests, "post", side_effect=[bad, ok]):
        assert S.call_gemini("s", "q", api_key="k", models=["m1", "m2"]) == ("{}", "m2")
    for status, msg in ((403, "denied"), (400, "API key not valid.")):
        with mock.patch.object(S.requests, "post", return_value=_resp(status, {"error": {"message": msg}})) as p:
            with pytest.raises(S.GeminiError, match="rejected the API key"):
                S.call_gemini("s", "q", api_key="k", models=["m1", "m2"])
        assert p.call_count == 1


@needs_snapshot
def test_analyze_plan_keeps_only_known_metrics_and_sources():
    ps = _ps("house")
    mix = S.recommend(ps)
    sec = {"summary": "s", "observations": [{"text": "o", "source": "made_up"}, {"text": "p", "source": "war_room_model"}],
           "interpretations": ["i"] * 6, "metric_ids": ["win_plan", "fake_metric", "net_votes"]}
    raw = json.dumps({"headline": "H", "sections": {k: sec for k in list(S.SECTION_KEYS)[:-1]}})
    with mock.patch.object(S, "call_gemini", return_value=(raw, "mock-model")) as call:
        res = S.analyze_plan(ps, mix, "focus on turnout", api_key="k")
    rep = res["report"]["sections"]
    assert rep["summary"]["metric_ids"] == ["win_plan", "net_votes"]
    assert [o["source"] for o in rep["summary"]["observations"]] == [None, "war_room_model"]
    assert len(rep["summary"]["interpretations"]) == 4 and rep["limits"]["missing"] is True
    assert "focus on turnout" in call.call_args.args[1]
    assert S.PlanSettings(**res["settings"]) == ps  # the analysis view can rebuild the exact plan


@needs_snapshot
def test_report_schema_constrains_ids():
    ps = _ps("house")
    ctx = S.build_context(ps, S.recommend(ps))
    sec = S.report_schema(ctx)["properties"]["sections"]["properties"]["summary"]["properties"]
    assert set(sec["metric_ids"]["items"]["enum"]) == set(ctx["metrics"])
    assert set(sec["observations"]["items"]["properties"]["source"]["enum"]) == set(ctx["sources"])


@needs_snapshot
@pytest.mark.parametrize("raw", [[1, 2], {"headline": None, "sections": {"summary": {
    "summary": None, "interpretations": "One string", "metric_ids": [{"a": 1}, "budget"],
    "observations": [{"text": "x\n\n[link](http://e.x)", "source": ["war_room_model"]}]}}}])
def test_clean_report_tolerates_malformed_output(raw):
    ps = _ps("house")
    ctx = S.build_context(ps, S.recommend(ps), with_risks=False)
    if not isinstance(raw, dict):
        with pytest.raises(S.GeminiError):
            S.clean_report(raw, ctx)
        return
    sec = S.clean_report(raw, ctx)["sections"]["summary"]
    assert sec["summary"] == "" and sec["interpretations"] == ["One string"]
    assert sec["metric_ids"] == ["budget"] and sec["observations"][0]["source"] is None
    assert "\n" not in sec["observations"][0]["text"]


# ----------------------------------------------------------------------------- page
def _app(race):
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file("../app_pages/war_room.py", default_timeout=180)
    at.session_state["race"], at.session_state["theme"] = race, "light"
    return at


def _charts(at):
    def walk(n):
        for c in getattr(n, "children", {}).values():
            yield c
            yield from walk(c)
    return sum(getattr(e, "type", "") == "vega_lite_chart" for e in walk(at._tree))


@needs_snapshot
@pytest.mark.parametrize("race", ["house", "senate"])
def test_plan_view_is_lean_and_analysis_view_is_isolated(race):
    from dataclasses import asdict

    at = _app(race)
    at.run()
    assert not at.exception and _charts(at) == 2  # step 1: spend map + top Republican spending
    at.session_state[f"wrw_{race}_step"] = at.session_state[f"wrp_{race}_step"] = 4
    at.run()
    assert not at.exception
    assert _charts(at) == 4  # step 4: map, ranked plan, messaging mix, budget curve
    md = " ".join(m.value for m in at.markdown)
    assert "Where to put the money" in md and "What the money buys" in md
    ps = _ps(race, asof=at.session_state[f"wrw_{race}_asof"])
    mix = S.recommend(ps)
    ctx = S.build_context(ps, mix)
    at.session_state[f"wr_{race}_result"] = {"created": "t", "model": "m", "settings": asdict(ps), "plan": S.mix_key(mix),
                                              "context": ctx, "report": S.clean_report({"headline": "Gen"}, ctx)}
    at.session_state["wr_view"] = "analysis"
    at.session_state[f"wrw_{race}_budget"] = at.session_state[f"wrp_{race}_budget"] = 500_000
    at.run()
    md = " ".join(m.value for m in at.markdown)
    assert not at.exception and "Gen" in md and "Where to put the money" not in md
    at.button(key="wrb_back_top").click().run()
    assert not at.exception and at.session_state["wr_view"] == "plan"
    assert at.session_state[f"wrw_{race}_budget"] == 500_000


@needs_snapshot
def test_edited_plan_drives_predictions_and_reset_restores():
    at = _app("house")
    at.run()
    ps = _ps("house", asof=at.session_state["wrw_house_asof"])
    mine = WR.region_lines("CD1", 300_000.0, "mobilization", ["meta"])
    at.session_state["wr_house_mix"] = S.mix_key(mine)
    at.session_state["wrw_house_step"] = at.session_state["wrp_house_step"] = 4
    at.run()
    assert not at.exception
    want = S.predict(ps, S.mix_key(mine))
    assert any(f"≈{want.total_delta_votes:,.0f} net votes" in m.value for m in at.markdown)
    at.button(key="wrb_reset").click().run()
    assert not at.exception and at.session_state["wr_house_mix"] is None


# ----------------------------------------------------------------------------- regressions from the second review
@needs_snapshot
def test_spend_before_uses_nothing_after_the_planning_date():
    asof = "2026-10-27"
    sp = S.spend_before("house", asof)
    a = S.ads_between("house", L.CYCLE_START, pd.Timestamp(asof) - pd.Timedelta(days=1))
    assert sp["gop"] == pytest.approx(a.loc[a["side"] == "GOP side", "p_spend"].sum())
    later = S.spend_before("house", "2026-10-29")
    assert later["gop"] >= sp["gop"] and 0 <= sp["gop_share"] <= 1


@needs_snapshot
@pytest.mark.parametrize("race", ["house", "senate"])
def test_recommendation_is_at_least_as_good_as_the_old_optimizer(race):
    ps = _ps(race)
    ctx, a, _ = S.race_context(ps)
    old, _ = optimize(None, ctx, a, step=10_000 if race == "house" else 20_000, channels=list(ps.platforms))
    old_res = simulate(WR.spread(WR.to_mix(old), ps.timing, ps.weeks), ctx, a)
    new_res = S.predict(ps, S.mix_key(S.recommend(ps)))
    assert new_res.total_delta_votes >= old_res.total_delta_votes * 0.99


@needs_snapshot
def test_frequency_cap_keeps_the_plan_diverse_and_explains_unplanned_money():
    ps = _ps("senate")
    assert S.recommend(ps).groupby("channel")["dollars"].sum().max() < 0.9 * ps.budget
    big = _ps("senate", budget=10_000_000.0, asof="2026-10-27")
    ctx, _, _ = S.race_context(big)
    mix = S.recommend(big)
    res = S.predict(big, S.mix_key(mix))
    assert res.total_spent < big.budget
    assert "frequency cap" in S.headline(big, ctx, res, S.messaging_mix(big, mix), S.plan_table(big, mix, res))


@needs_snapshot
def test_messaging_mix_adds_up_to_the_headline_votes():
    ps = _ps("senate")
    mix = S.recommend(ps)
    assert S.messaging_mix(ps, mix)["net_votes"].sum() == pytest.approx(S.predict(ps, S.mix_key(mix)).total_delta_votes,
                                                                         rel=1e-6)


@needs_snapshot
def test_headline_never_compares_a_platform_with_itself():
    ps = _ps("senate", platforms=("meta",))
    ctx, _, _ = S.race_context(ps)
    mix = S.recommend(ps)
    res = S.predict(ps, S.mix_key(mix))
    assert "per dollar" not in S.headline(ps, ctx, res, S.messaging_mix(ps, mix), S.plan_table(ps, mix, res))


def test_mix_from_drops_zero_dollar_lines():
    js = S.mix_key(WR.region_lines("CD1", 0.0, "both", ["meta"]))
    assert S.mix_from(js).empty


@needs_snapshot
def test_sensitivity_in_context_is_direction_explicit():
    ps = _ps("senate")
    ctx = S.build_context(ps, S.recommend(ps))
    for r in ctx["sensitivity"]:
        assert r["win_chance_if_unfavourable"] <= r["win_chance_if_favourable"]


@needs_snapshot
def test_settings_survive_visiting_another_page():
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file("../app.py", default_timeout=180)
    at.session_state["race"], at.session_state["theme"] = "senate", "light"
    at.run()
    at.switch_page("app_pages/war_room.py").run()
    at.session_state["wrw_senate_budget"] = at.session_state["wrp_senate_budget"] = 500_000
    at.run()
    at.switch_page("app_pages/regions.py").run()
    at.switch_page("app_pages/war_room.py").run()
    assert not at.exception and at.session_state["wrw_senate_budget"] == 500_000


# ----------------------------------------------------------------------------- opponent inputs + steps
@needs_snapshot
@pytest.mark.parametrize("race", ["house", "senate"])
def test_region_spend_reconciles_with_totals(race):
    asof = "2026-09-08"
    rs, sp = S.region_spend_before(race, asof), S.spend_before(race, asof)
    assert rs["dem"].sum() == pytest.approx(sp["dem"], rel=1e-6)
    assert rs["gop"].sum() == pytest.approx(sp["gop"], rel=1e-6)
    assert rs["gop_sov"].between(0, 1).all()


@needs_snapshot
def test_audience_pressure_is_relative_and_theme_aware():
    ap = S.audience_pressure("senate", "2026-09-08")
    assert set(ap["idx"]) == {"persuasion", "mobilization"} and all(0.5 < v < 1.5 for v in ap["idx"].values())
    by = ap["by_age"]
    assert list(by["age"]) == S.VOTER_AGES and by["w_all"].sum() == pytest.approx(1)
    themed = S.audience_pressure("senate", "2026-09-08", ("economy",))
    assert themed["gop_impressions"] < ap["gop_impressions"] and themed["dem_impressions"] == ap["dem_impressions"]


@needs_snapshot
def test_opponent_inputs_change_the_prediction():
    ps = _ps("senate")
    mix = S.recommend(ps)
    eff = S.opponent_effect(ps, mix)
    assert eff["votes_with"] < eff["votes_without"]
    strong = S.opponent_effect(replace(ps, opp_lambda=1.0), mix)
    assert strong["votes_with"] < eff["votes_with"]
    _, a, _ = S.race_context(replace(ps, opp_on=False))
    assert a.opp_lambda == 0
    ctx_on, a_on, _ = S.race_context(ps)
    assert a_on.opp_lambda == 0.5 and ctx_on.units["opp_share"].nunique() > 1  # per-region share of voice


@needs_snapshot
def test_context_carries_opponent_block():
    ps = _ps("house", messages=(("economy", 1.0),))
    c = S.build_context(ps, S.recommend(ps))
    o = c["opponent"]
    assert o["accounted_for"] and c["our_messaging"]["mix"] == {"Economy & Cost of Living": 1.0}
    assert o["effect_on_this_plan"]["net_votes_with_opponent_pressure"] <= o["effect_on_this_plan"]["net_votes_without"]
    assert len(o["spend_by_region_before_planning_date"]) <= 12


@needs_snapshot
def test_steps_navigate_and_keep_inputs():
    at = _app("house")
    at.run()
    at.button(key="wrb_next_1").click().run()
    assert not at.exception and at.session_state["wrw_house_step"] == 2 and _charts(at) == 2
    at.session_state["wrw_house_opp_lambda"] = at.session_state["wrp_house_opp_lambda"] = 1.0
    at.button(key="wrb_next_2").click().run()
    at.button(key="wrb_next_3").click().run()
    at.button(key="wrb_next_4").click().run()
    assert not at.exception and at.session_state["wrw_house_step"] == 5
    at.session_state["wrw_house_step"] = at.session_state["wrp_house_step"] = 2
    at.run()
    assert not at.exception and at.session_state["wrw_house_opp_lambda"] == 1.0


# ----------------------------------------------------------------------------- our messaging + Gemini planner
@needs_snapshot
def test_theme_stats_measure_fit_and_contest():
    ts = S.theme_stats("senate", "2026-09-08").set_index("theme")
    assert "fundraising" not in ts.index
    assert ts.loc["healthcare", "gop_sov"] == 0 and ts.loc["veterans", "gop_sov"] == 1
    ok = ts[ts["enough_data"]]
    assert ok["fit_persuasion"].between(0.5, 1.5).all()
    assert (ts.loc[~ts["enough_data"], ["fit_persuasion", "fit_mobilization"]] == 1.0).all().all()


@needs_snapshot
def test_message_multipliers():
    none = S.message_multipliers("senate", "2026-09-08", (), 0.5)
    assert none == {"persuasion": 1.0, "mobilization": 1.0}
    health = S.message_multipliers("senate", "2026-09-08", (("healthcare", 1.0),), 0.5)
    vets = S.message_multipliers("senate", "2026-09-08", (("veterans", 1.0),), 0.5)
    assert health["persuasion"] > 1 > vets["persuasion"]  # uncontested issue beats an issue they own
    mixed = S.message_multipliers("senate", "2026-09-08", (("healthcare", 0.5), ("veterans", 0.5)), 0.5)
    assert mixed["persuasion"] == pytest.approx((health["persuasion"] + vets["persuasion"]) / 2)


@needs_snapshot
def test_messages_change_the_prediction_and_comparison_ranks_them():
    ps = _ps("senate")
    base = S.predict(ps, S.mix_key(S.recommend(ps))).total_delta_votes
    hp = replace(ps, messages=(("healthcare", 1.0),))
    assert S.predict(hp, S.mix_key(S.recommend(hp))).total_delta_votes > base
    mc = S.message_comparison(ps)
    assert "No specific theme" in set(mc["label"]) and mc["net_votes"].is_monotonic_decreasing


@needs_snapshot
def test_apply_proposal_respects_permissions_and_budget():
    ps = _ps("house")
    mix = S.recommend(ps)
    raw = {"area_plan": [{"region": "CD-1", "dollars": 3_000_000, "goal": "persuasion", "platforms": ["meta"]},
                         {"region": "Nowhere", "dollars": 10}],
           "messages": [{"theme": "healthcare", "share": 2}, {"theme": "abortion", "share": 1}]}
    new_mix, new_ps, notes = S.apply_proposal(ps, mix, raw, {"areas", "messages"})
    assert new_mix["dollars"].sum() == pytest.approx(ps.budget) and set(new_mix["unit_id"]) == {"CD1"}
    assert any("Nowhere" in n for n in notes)  # the $3M row is clamped to the $2M budget
    assert new_ps.messages == (("healthcare", 1.0),)  # abortion has no data and is dropped
    same_mix, _, _ = S.apply_proposal(ps, mix, raw, {"messages"})
    assert S.mix_key(same_mix) == S.mix_key(mix)  # no area permission: plan untouched
    t_mix, t_ps, _ = S.apply_proposal(ps, mix, raw, {"tactics"})
    assert t_ps.messages == () and t_mix["dollars"].sum() == pytest.approx(mix["dollars"].sum())


@needs_snapshot
def test_gemini_plan_keeps_the_best_scoring_round():
    ps = _ps("house")
    mix = S.recommend(ps)
    good = {"messages": [{"theme": "healthcare", "share": 1}], "rationale": ["uncontested"], "expected_effect": "up"}
    bad = {"messages": [{"theme": "veterans", "share": 1}], "rationale": ["owned by them"], "expected_effect": "down"}
    with mock.patch.object(S, "call_gemini", side_effect=[(json.dumps(good), "m"), (json.dumps(bad), "m")]) as call:
        out = S.gemini_plan(ps, mix, {"messages"}, api_key="k")
    assert call.call_count == 2 and "SCORED BY THE MODEL" in call.call_args_list[1].args[1]
    assert out["best"]["round"] == 1 and out["best"]["messages"] == (("healthcare", 1.0),)
    assert out["best"]["after"]["net_votes"] > out["before"]["net_votes"]
    with pytest.raises(S.GeminiError, match="permission"):
        S.gemini_plan(ps, mix, set(), api_key="k")


@needs_snapshot
def test_planner_schema_only_exposes_permitted_fields():
    sch = S.planner_schema({"messages"}, ["healthcare"])
    assert "messages" in sch["properties"] and "area_plan" not in sch["properties"]
    sch = S.planner_schema({"areas"}, ["healthcare"])
    row = sch["properties"]["area_plan"]["items"]["properties"]
    assert "dollars" in row and "goal" not in row and "messages" not in sch["properties"]


@needs_snapshot
def test_page_applies_gemini_changes_only_when_better_and_can_undo():
    at = _app("house")
    at.session_state["wrw_house_step"] = at.session_state["wrp_house_step"] = 5
    at.session_state["wrw_house_perm_messages"] = at.session_state["wrp_house_perm_messages"] = True
    at.run()
    good = {"messages": [{"theme": "healthcare", "share": 1}], "rationale": ["r"], "expected_effect": "e"}
    with mock.patch.object(S, "call_gemini", return_value=(json.dumps(good), "m")):
        at.button(key="wrb_agent").click().run()
    assert not at.exception and at.session_state["wr_house_agent"]["applied"]
    assert at.session_state["wrw_house_msg_themes"] == ["healthcare"]
    at.button(key="wrb_undo").click().run()
    assert not at.exception and at.session_state["wrw_house_msg_themes"] == []
    bad = {"messages": [{"theme": "veterans", "share": 1}], "rationale": ["r"], "expected_effect": "e"}
    with mock.patch.object(S, "call_gemini", return_value=(json.dumps(bad), "m")):
        at.button(key="wrb_agent").click().run()
    assert not at.exception and not at.session_state["wr_house_agent"]["applied"]
    assert at.session_state["wrw_house_msg_themes"] == []


# ----------------------------------------------------------------------------- regressions from the third review
@needs_snapshot
def test_theme_fit_is_one_for_an_audience_shaped_like_the_electorate():
    w = S._audience_weights()
    rel = w["all"] / w["all"]
    d = pd.Series([0.4, 0.3, 0.2, 0.1], index=S.VOTER_AGES)
    assert float((d * rel).sum() / (w["all"] * rel).sum()) == pytest.approx(1.0)
    ts = S.theme_stats("senate", "2026-07-14").set_index("theme")
    assert ts.loc["crime", "fit_persuasion"] > 1 > ts.loc["healthcare", "fit_persuasion"]


@needs_snapshot
def test_contest_baseline_counts_each_ad_once():
    a = S.ads_between("senate", L.CYCLE_START, pd.Timestamp("2026-09-07"))
    a = a[(a["platform"] == "Meta") & a["side"].isin(["Dem side", "GOP side"])]
    want = a.loc[a["side"] == "GOP side", "p_spend"].sum() / a["p_spend"].sum()
    assert S.meta_gop_share("senate", "2026-09-08") == pytest.approx(want)


def test_five_pct_shares():
    assert S.five_pct_shares([("a", 0.98), ("b", 0.02)]) == (("a", 1.0),)
    assert sum(w for _, w in S.five_pct_shares([("a", 1), ("b", 1), ("c", 1)])) == pytest.approx(1)
    assert S.five_pct_shares([("a", 0.0)]) == ()


@needs_snapshot
def test_apply_proposal_rejects_non_finite_numbers():
    ps = _ps("house")
    mix = S.recommend(ps)
    raw = {"area_plan": [{"region": "CD-1", "dollars": float("inf")}, {"region": "CD-2", "dollars": 1e400}],
           "messages": [{"theme": "healthcare", "share": float("inf")}, {"theme": "economy", "share": 1}]}
    new_mix, new_ps, notes = S.apply_proposal(ps, mix, raw, {"areas", "messages"})
    assert np.isfinite(new_mix["dollars"]).all() and new_mix.empty
    assert new_ps.messages == (("economy", 1.0),) and any("non-numeric" in n for n in notes)


@needs_snapshot
def test_revision_round_shows_gemini_its_previous_proposal():
    ps = _ps("house")
    prop = {"messages": [{"theme": "healthcare", "share": 1}], "rationale": ["r"], "expected_effect": "e"}
    with mock.patch.object(S, "call_gemini", return_value=(json.dumps(prop), "m")) as call:
        S.gemini_plan(ps, S.recommend(ps), {"messages"}, api_key="k")
    second = call.call_args_list[1].args[1]
    assert "YOUR LAST PROPOSAL" in second and "healthcare" in second.split("YOUR LAST PROPOSAL")[1]


@needs_snapshot
def test_messages_only_permission_never_moves_area_dollars():
    at = _app("house")
    at.session_state["wrw_house_step"] = at.session_state["wrp_house_step"] = 5
    at.session_state["wrw_house_perm_messages"] = at.session_state["wrp_house_perm_messages"] = True
    at.run()
    before = S.mix_key(S.recommend(_ps("house", asof=at.session_state["wrw_house_asof"])))
    good = {"messages": [{"theme": "healthcare", "share": 1}], "rationale": ["r"], "expected_effect": "e"}
    with mock.patch.object(S, "call_gemini", return_value=(json.dumps(good), "m")):
        at.button(key="wrb_agent").click().run()
    assert at.session_state["wr_house_agent"]["applied"]
    frozen = S.mix_from(at.session_state["wr_house_mix"]).groupby("unit_id")["dollars"].sum()
    assert frozen.round(0).equals(S.mix_from(before).groupby("unit_id")["dollars"].sum().round(0))


@needs_snapshot
def test_undo_turns_off_after_a_later_edit():
    at = _app("house")
    at.session_state["wrw_house_step"] = at.session_state["wrp_house_step"] = 5
    at.session_state["wrw_house_perm_messages"] = at.session_state["wrp_house_perm_messages"] = True
    at.run()
    good = {"messages": [{"theme": "healthcare", "share": 1}], "rationale": ["r"], "expected_effect": "e"}
    with mock.patch.object(S, "call_gemini", return_value=(json.dumps(good), "m")):
        at.button(key="wrb_agent").click().run()
    at.session_state["wrw_house_msg_themes"] = at.session_state["wrp_house_msg_themes"] = ["crime"]
    at.run()
    assert not at.exception and not any(b.key == "wrb_undo" for b in at.button)


@needs_snapshot
def test_deselecting_the_step_bar_does_not_crash():
    at = _app("senate")
    at.session_state["wrw_senate_step"] = at.session_state["wrp_senate_step"] = 3
    at.run()
    at.button_group(key="wrw_senate_step").set_value(None).run()
    assert not at.exception and at.session_state["wrw_senate_step"] == 3


@needs_snapshot
def test_messages_survive_visiting_another_page():
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file("../app.py", default_timeout=240)
    at.session_state["race"], at.session_state["theme"] = "senate", "light"
    at.run()
    at.switch_page("app_pages/war_room.py").run()
    at.session_state["wrw_senate_step"] = at.session_state["wrp_senate_step"] = 3
    at.run()
    at.multiselect(key="wrw_senate_msg_themes").set_value(["economy", "crime"]).run()
    at.switch_page("app_pages/regions.py").run()
    at.switch_page("app_pages/war_room.py").run()
    assert not at.exception and at.session_state["wrw_senate_msg_themes"] == ["economy", "crime"]


@needs_snapshot
def test_unusable_theme_is_ignored_consistently():
    at = _app("senate")
    at.session_state["wrw_senate_msg_themes"] = at.session_state["wrp_senate_msg_themes"] = ["education", "economy"]
    at.session_state["wrw_senate_asof"] = at.session_state["wrp_senate_asof"] = "2026-07-14"  # education has no data yet
    at.run()
    assert not at.exception
    ps_seen = S.PlanSettings(race="senate", asof="2026-07-14", budget=2e6, messages=(("economy", 1.0),))
    at.session_state["wrw_senate_step"] = at.session_state["wrp_senate_step"] = 4
    at.run()
    want = S.predict(ps_seen, S.mix_key(S.recommend(ps_seen))).total_delta_votes
    assert any(f"≈{want:,.0f} net votes" in m.value for m in at.markdown)
    assert at.session_state["wrw_senate_msg_themes"] == ["education", "economy"]  # selection is not overwritten


@needs_snapshot
def test_apply_proposal_scales_total_down_to_budget():
    ps = _ps("house")
    raw = {"area_plan": [{"region": "CD-1", "dollars": 1_500_000}, {"region": "CD-9", "dollars": 1_500_000}]}
    new_mix, _, notes = S.apply_proposal(ps, S.recommend(ps), raw, {"areas"})
    assert new_mix["dollars"].sum() == pytest.approx(ps.budget) and any("Scaled" in n for n in notes)


# ----------------------------------------------------------------------------- ad links, change view, escaping
def _check(*args):
    return REAL_CHECK_AD_LINK.__wrapped__(*args) if hasattr(REAL_CHECK_AD_LINK, "__wrapped__") else REAL_CHECK_AD_LINK(*args)


def test_google_link_shown_only_when_it_answers_200():
    ok, bad = mock.Mock(status_code=200), mock.Mock(status_code=404)
    with mock.patch.object(S.requests, "get", return_value=ok):
        assert _check("Google", "CR1", "https://adstransparency.google.com/x", "", "2026-09-01")[0]
    with mock.patch.object(S.requests, "get", return_value=bad):
        url, note = _check("Google", "CR2", "https://adstransparency.google.com/y", "", "2026-09-01")
    assert url == "" and "404" in note


def test_meta_link_shown_only_when_the_api_finds_the_ad(monkeypatch):
    import campaign_intel.config as cfg

    monkeypatch.setattr(cfg, "META_AD_TOKEN", "tok")
    found = _resp(200, {"data": [{"id": "111"}, {"id": "222"}]})
    with mock.patch.object(S.requests, "get", return_value=found) as get:
        url, note = _check("Meta", "222", "https://www.facebook.com/ads/archive/render_ad/?id=222", "p1", "2026-09-01")
    assert url == "https://www.facebook.com/ads/library/?id=222" and "verified" in note
    assert get.call_args.kwargs["params"]["search_page_ids"] == '["p1"]'
    with mock.patch.object(S.requests, "get", return_value=_resp(200, {"data": [{"id": "111"}]})):
        assert _check("Meta", "333", "", "p1", "2026-09-01") == ("", "not found in the Meta Ad Library")
    monkeypatch.setattr(cfg, "META_AD_TOKEN", "")
    assert _check("Meta", "444", "", "p1", "2026-09-01")[0] == ""


def test_link_check_network_error_hides_the_link():
    with mock.patch.object(S.requests, "get", side_effect=S.requests.ConnectionError("down")):
        url, note = _check("Google", "CR3", "https://adstransparency.google.com/z", "", "2026-09-01")
    assert url == "" and "not verified" in note


@needs_snapshot
def test_plan_diff_lists_money_and_tactic_changes():
    before = WR.region_lines("CD1", 300_000.0, "persuasion", ["meta"])
    after = pd.concat([WR.region_lines("CD1", 100_000.0, "mobilization", ["display"]),
                       WR.region_lines("CD9", 200_000.0, "persuasion", ["meta"])])
    d = S.plan_diff("house", S.mix_key(before), S.mix_key(after)).set_index("area")
    assert d.loc["CD-1", "change"] == pytest.approx(-200_000) and d.loc["CD-9", "before"] == 0
    assert d.loc["CD-1", "use_changed"] and d.loc["CD-1", "use_after"].startswith("Turn out Democrats")


@needs_snapshot
def test_planner_result_separates_changes_from_reasoning():
    at = _app("house")
    for n_, v in (("step", 5), ("perm_messages", True)):
        at.session_state[f"wrw_house_{n_}"] = at.session_state[f"wrp_house_{n_}"] = v
    at.run()
    prop = {"messages": [{"theme": "healthcare", "share": 1}], "expected_effect": "More votes.",
            "observations": [{"text": "Healthcare's Republican share is 0.", "source": "war_room_model"}],
            "reasoning": ["An uncontested issue isn't diluted by their ads."]}
    with mock.patch.object(S, "call_gemini", return_value=(json.dumps(prop), "m")):
        at.button(key="wrb_agent").click().run()
    md = " ".join(m.value for m in at.markdown)
    assert not at.exception and "What Gemini changed" in md and "Why: Gemini" in md
    assert "Before: No specific theme" in md and "After: Healthcare 100%" in md
    assert md.index("What it relied on") < md.index("Its reasoning")


def test_escape_is_single_pass():
    import importlib.util

    spec = importlib.util.spec_from_file_location("_wr_src", "app_pages/war_room.py")
    src = spec.loader.get_source("_wr_src")
    assert "_HTML_ENT.get(c) or _MD_ENT.get(c, c)" in src  # one pass: '#' inside &#39; is never re-escaped
