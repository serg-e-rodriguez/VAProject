"""
NCSBE ingestion: real precinct results and registration rolled up to districts and counties.

Sources (public, https://dl.ncsbe.gov/ENRS/):
- results_pct_20241105  : 2024 general precinct results (baseline = US PRESIDENT)
- results_pct_20261103  : 2026 general precinct results (backtest = US SENATE, unofficial)
- voter_stats_20241105  : registration by precinct x party
- voter_stats_20221108  : registration on 2022 Election Day (denominator for 2022 turnout)
- history_stats_20221108: who voted in 2022, by precinct x party

Method
------
Precinct -> district assignment comes from the results files themselves: every precinct
(including the absentee / early-vote pseudo-precincts) reports the US House, NC Senate and
NC House contests on its ballot. A precinct's weight in a district is that district's share
of the precinct's votes in the contest of that type (split precincts get fractional weights).
SD / HD use the 2024 ballots (same lines in 2026). CD uses the 2026 ballots because Congress
was redrawn in 2025 and the CD shapes are the 2026 map; 2024 precincts that were renamed, and
early-vote / absentee pseudo-precincts, are spread by their county's district mix (exact for the
counties that sit wholly inside one district). Every geography sums to the same statewide totals.

Midterm baseline: the 2024 presidential margin (pct) per unit is applied to an expected
midterm turnout, which is the unit's 2024 vote scaled by its county's 2022/2024 turnout ratio.
"""

from __future__ import annotations

import json
import logging
import urllib.request
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

from campaign_intel.config import DATA_DIR, GEO_DIR

logger = logging.getLogger(__name__)

RAW_DIR = DATA_DIR / "raw" / "ncsbe"
BASE_URL = "https://s3.amazonaws.com/dl.ncsbe.gov/ENRS"
FILES = {
    "results_2024": "2024_11_05/results_pct_20241105.zip",
    "results_2026": "2026_11_03/results_pct_20261103.zip",
    "voters_2024": "2024_11_05/voter_stats_20241105.zip",
    "voters_2022": "2022_11_08/voter_stats_20221108.zip",
    "history_2022": "2022_11_08/history_stats_20221108.zip",
}
CONTEST_PREFIX = {
    "cd": "US HOUSE OF REPRESENTATIVES DISTRICT",
    "sd": "NC STATE SENATE DISTRICT",
    "hd": "NC HOUSE OF REPRESENTATIVES DISTRICT",
}
UNIT_NAMES = {"cd": "Congressional District", "sd": "State Senate District", "hd": "State House District"}


# ----------------------------------------------------------------------------- IO helpers
def download(force: bool = False) -> dict[str, Path]:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    paths = {}
    for key, rel in FILES.items():
        p = RAW_DIR / Path(rel).name
        if force or not p.exists():
            logger.info("Downloading %s", rel)
            urllib.request.urlretrieve(f"{BASE_URL}/{rel}", p)
        paths[key] = p
    return paths


def _read_zip_tsv(path: Path) -> pd.DataFrame:
    with zipfile.ZipFile(path) as z:
        with z.open(z.namelist()[0]) as fh:
            df = pd.read_csv(fh, sep="\t", dtype=str, low_memory=False, encoding="latin-1")
    df.columns = [c.strip() for c in df.columns]
    return df.loc[:, [c for c in df.columns if c and not c.startswith("Unnamed")]]


def read_results(path: Path) -> pd.DataFrame:
    df = _read_zip_tsv(path)
    df["Total Votes"] = pd.to_numeric(df["Total Votes"], errors="coerce").fillna(0).astype(int)
    df["County"] = df["County"].str.strip().str.upper()
    df["Precinct"] = df["Precinct"].str.strip()
    df["Choice Party"] = df["Choice Party"].fillna("").str.strip()
    return df


def read_stats(path: Path) -> pd.DataFrame:
    df = _read_zip_tsv(path)
    df["total_voters"] = pd.to_numeric(df["total_voters"], errors="coerce").fillna(0).astype(int)
    df["county_desc"] = df["county_desc"].str.strip().str.upper()
    df["precinct_abbrv"] = df["precinct_abbrv"].fillna("").str.strip()
    return df


def county_fips_lookup() -> dict[str, str]:
    """Upper-case county name -> 5-digit FIPS, from the committed county GeoJSON."""
    geo = json.loads((GEO_DIR / "county.geojson").read_text())
    return {f["properties"]["name"].upper(): f["properties"]["county_fips"] for f in geo["features"]}


# ----------------------------------------------------------------------------- core steps
def precinct_district_weights(results: pd.DataFrame) -> pd.DataFrame:
    """(county, precinct, unit_type, unit_id, weight) from the district contests on each ballot."""
    frames = []
    for utype, prefix in CONTEST_PREFIX.items():
        sub = results[results["Contest Name"].str.startswith(prefix)].copy()
        sub["num"] = sub["Contest Name"].str.extract(r"(\d+)\s*$")[0].astype(int)
        g = sub.groupby(["County", "Precinct", "num"], as_index=False)["Total Votes"].sum()
        tot = g.groupby(["County", "Precinct"])["Total Votes"].transform("sum")
        # Precincts with zero votes in the contest still belong to the district: equal split.
        n = g.groupby(["County", "Precinct"])["num"].transform("count")
        g["weight"] = np.where(tot > 0, g["Total Votes"] / tot.replace(0, 1), 1.0 / n)
        g["unit_type"] = utype
        g["unit_id"] = utype.upper() + g["num"].astype(str)
        frames.append(g[["County", "Precinct", "unit_type", "unit_id", "weight"]])
    return pd.concat(frames, ignore_index=True)


def contest_votes(results: pd.DataFrame, contest: str) -> pd.DataFrame:
    """Per precinct: dem, rep, other, total votes for one statewide contest (write-ins dropped)."""
    sub = results[results["Contest Name"] == contest]
    sub = sub[~sub["Choice"].str.contains("Write-In", case=False, na=False)]
    party = np.select([sub["Choice Party"] == "DEM", sub["Choice Party"] == "REP"], ["dem", "rep"], "other")
    piv = (
        sub.assign(party=party)
        .pivot_table(index=["County", "Precinct"], columns="party", values="Total Votes", aggfunc="sum", fill_value=0)
        .reset_index()
    )
    for c in ["dem", "rep", "other"]:
        if c not in piv.columns:
            piv[c] = 0
    piv["total"] = piv["dem"] + piv["rep"] + piv["other"]
    piv.columns.name = None
    return piv[["County", "Precinct", "dem", "rep", "other", "total"]]


def _apply_weights(df: pd.DataFrame, weights: pd.DataFrame, value_cols: list[str],
                   left_keys=("County", "Precinct")) -> pd.DataFrame:
    """
    Distributes precinct-level values to districts. Rows whose precinct label is not in the
    weight table (renamed precincts, pseudo-precincts) are spread using their county's
    vote-weighted district mix, so nothing is dropped.
    """
    if weights["unit_type"].nunique() > 1:  # match each district type on its own keys
        return pd.concat([_apply_weights(df, w, value_cols, left_keys) for _, w in weights.groupby("unit_type")],
                         ignore_index=True)
    lk = list(left_keys)
    w = weights.rename(columns={"County": lk[0], "Precinct": lk[1]})
    keyset = set(zip(w[lk[0]], w[lk[1]]))
    matched_mask = np.array([k in keyset for k in zip(df[lk[0]], df[lk[1]])], dtype=bool)
    matched = df[matched_mask].merge(w, on=lk)
    for c in value_cols:
        matched[c] = matched[c] * matched["weight"]

    out = [matched[[lk[0], "unit_type", "unit_id", *value_cols]]]
    unmatched = df[~matched_mask]
    if not unmatched.empty:
        cmix = w.groupby([lk[0], "unit_type", "unit_id"], as_index=False)["weight"].sum()
        cmix["weight"] = cmix["weight"] / cmix.groupby([lk[0], "unit_type"])["weight"].transform("sum")
        um = unmatched.groupby(lk[0], as_index=False)[value_cols].sum().merge(cmix, on=lk[0])
        for c in value_cols:
            um[c] = um[c] * um["weight"]
        out.append(um[[lk[0], "unit_type", "unit_id", *value_cols]])
    res = pd.concat(out, ignore_index=True)
    return res.groupby([lk[0], "unit_type", "unit_id"], as_index=False)[value_cols].sum()


def build(force_download: bool = False) -> dict[str, pd.DataFrame]:
    paths = download(force_download)
    fips = county_fips_lookup()

    r24 = read_results(paths["results_2024"])
    r26 = read_results(paths["results_2026"])
    # SD/HD lines were the same in 2024 and 2026 -> exact 2024 ballot assignment.
    # Congress was redrawn in 2025 (CD-1 / CD-3); the app's CD shapes are the 2026 map, so CD
    # assignment comes from the 2026 ballots (renamed / pseudo-precincts spread by county mix).
    w24, w26 = precinct_district_weights(r24), precinct_district_weights(r26)
    weights = pd.concat([w24[w24["unit_type"] != "cd"], w26[w26["unit_type"] == "cd"]], ignore_index=True)
    pres = contest_votes(r24, "US PRESIDENT")

    # --- Midterm turnout ratio per county: 2022 ballots (history) / 2024 presidential votes
    hist22 = read_stats(paths["history_2022"])
    vot22 = read_stats(paths["voters_2022"])
    voted22_cty = hist22.groupby("county_desc")["total_voters"].sum()
    pres_cty = pres.groupby("County")["total"].sum()
    midterm_ratio = (voted22_cty / pres_cty).rename("midterm_ratio")

    # Party-level 2022 turnout rates per county (for the mobilization universe)
    dem_voted22 = hist22[hist22["party_cd"] == "DEM"].groupby("county_desc")["total_voters"].sum()
    dem_reg22 = vot22[vot22["party_cd"] == "DEM"].groupby("county_desc")["total_voters"].sum()
    dem_rate22 = (dem_voted22 / dem_reg22).clip(0, 1).rename("dem_turnout22")
    all_rate22 = (voted22_cty / vot22.groupby("county_desc")["total_voters"].sum()).clip(0, 1).rename("turnout22")

    # --- Registration (2024 Election Day) by precinct x party
    v24 = read_stats(paths["voters_2024"])
    reg = (
        v24.assign(party=np.select([v24.party_cd == "DEM", v24.party_cd == "REP", v24.party_cd == "UNA"],
                                   ["reg_dem", "reg_rep", "reg_una"], "reg_oth"))
        .pivot_table(index=["county_desc", "precinct_abbrv"], columns="party", values="total_voters",
                     aggfunc="sum", fill_value=0)
        .reset_index()
        .rename(columns={"county_desc": "County", "precinct_abbrv": "Precinct"})
    )
    reg.columns.name = None
    reg["registered_voters"] = reg[["reg_dem", "reg_rep", "reg_una", "reg_oth"]].sum(axis=1)
    reg = reg.merge(dem_rate22.rename_axis("County").reset_index(), on="County", how="left")
    reg["mobilization_universe"] = reg["reg_dem"] * (1 - reg["dem_turnout22"].fillna(dem_rate22.mean()))

    # --- Expected midterm turnout per precinct
    pres = pres.merge(midterm_ratio.rename_axis("County").reset_index(), on="County", how="left")
    pres["expected_turnout"] = pres["total"] * pres["midterm_ratio"].fillna(midterm_ratio.median())

    vote_cols = ["dem", "rep", "other", "total", "expected_turnout"]
    reg_cols = ["registered_voters", "reg_dem", "reg_rep", "reg_una", "reg_oth", "mobilization_universe"]

    # County x district pieces (district rollups and the county<->district crosswalk)
    pv = _apply_weights(pres, weights, vote_cols)
    rg = _apply_weights(reg, weights, reg_cols)
    piece = pv.merge(rg, on=["County", "unit_type", "unit_id"], how="outer").fillna(0.0)
    piece["county_fips"] = piece["County"].map(fips)

    # --- 2026 backtest (US SENATE), assigned with the SAME 2024 precinct weights (2024 lines)
    sen26 = contest_votes(r26, "US SENATE")
    bt = _apply_weights(sen26, pd.concat([w24[w24["unit_type"] != "cd"], w26[w26["unit_type"] == "cd"]]),
                        ["dem", "rep", "other", "total"])

    out: dict[str, pd.DataFrame] = {}
    for utype in ["cd", "sd", "hd"]:
        p = piece[piece["unit_type"] == utype]
        u = p.groupby("unit_id", as_index=False)[vote_cols + reg_cols].sum()
        b = bt[bt["unit_type"] == utype].groupby("unit_id", as_index=False)[["dem", "rep", "other", "total"]].sum()
        u = u.merge(b.add_prefix("actual26_").rename(columns={"actual26_unit_id": "unit_id"}), on="unit_id", how="left")
        u["district_num"] = u["unit_id"].str[2:].astype(int)
        u["name"] = UNIT_NAMES[utype] + " " + u["district_num"].astype(str)
        u["unit_type"] = utype
        # 2022 turnout rate: registration-weighted average of the counties the unit covers
        cw = p.merge(all_rate22.rename_axis("County").reset_index(), on="County")
        tr = (cw["turnout22"] * cw["registered_voters"]).groupby(cw["unit_id"]).sum() / \
            cw["registered_voters"].groupby(cw["unit_id"]).sum()
        u["turnout22_rate"] = u["unit_id"].map(tr)
        out[f"units_{utype}"] = _finalize(u.sort_values("district_num"))

    # Counties: exact sums (no weights needed)
    c = piece[piece["unit_type"] == "cd"].groupby(["County", "county_fips"], as_index=False)[vote_cols + reg_cols].sum()
    b = sen26.groupby("County", as_index=False)[["dem", "rep", "other", "total"]].sum()
    c = c.merge(b.add_prefix("actual26_").rename(columns={"actual26_County": "County"}), on="County", how="left")
    c["unit_id"] = c["county_fips"]
    c["name"] = c["County"].str.title()
    c["unit_type"] = "county"
    c["turnout22_rate"] = c["County"].map(all_rate22)
    out["units_county"] = _finalize(c.sort_values("name"))

    # County <-> district crosswalk (registered-voter shares), used to allocate county-level ad data
    xw = piece[["county_fips", "unit_type", "unit_id", "registered_voters"]].copy()
    xw["share_of_county"] = xw["registered_voters"] / xw.groupby(["county_fips", "unit_type"])["registered_voters"].transform("sum")
    out["county_district_crosswalk"] = xw

    # Statewide check figures
    out["statewide"] = pd.DataFrame([{
        "pres24_dem": int(pres["dem"].sum()), "pres24_rep": int(pres["rep"].sum()),
        "pres24_total": int(pres["total"].sum()),
        "voted22_total": int(voted22_cty.sum()),
        "registered_2024": int(reg["registered_voters"].sum()),
        "sen26_dem": int(sen26["dem"].sum()), "sen26_rep": int(sen26["rep"].sum()),
        "sen26_total": int(sen26["total"].sum()),
        "sen26_dem_candidate": _top_candidate(r26, "US SENATE", "DEM"),
        "sen26_rep_candidate": _top_candidate(r26, "US SENATE", "REP"),
        "sen26_file_date": _zip_member_date(paths["results_2026"]),
    }])
    return out


def _top_candidate(results: pd.DataFrame, contest: str, party: str) -> str:
    sub = results[(results["Contest Name"] == contest) & (results["Choice Party"] == party)]
    if sub.empty:
        return ""
    return str(sub.groupby("Choice")["Total Votes"].sum().idxmax())


def _zip_member_date(path: Path) -> str:
    with zipfile.ZipFile(path) as z:
        y, m, d, hh, mm, _ = z.infolist()[0].date_time
    return f"{y:04d}-{m:02d}-{d:02d} {hh:02d}:{mm:02d}"


def _finalize(u: pd.DataFrame) -> pd.DataFrame:
    u = u.rename(columns={"dem": "dem_votes_2024", "rep": "rep_votes_2024", "other": "other_votes_2024",
                          "total": "total_votes_2024"})
    u["dem_margin_pct"] = (u["dem_votes_2024"] - u["rep_votes_2024"]) / u["total_votes_2024"] * 100
    u["expected_turnout"] = u["expected_turnout"].round()
    u["baseline_margin_votes"] = (u["dem_margin_pct"] / 100 * u["expected_turnout"]).round()
    u["persuasion_universe"] = u["reg_una"].round()
    u["mobilization_universe"] = u["mobilization_universe"].round()
    if "actual26_total" in u.columns:
        u["actual26_margin_pct"] = (u["actual26_dem"] - u["actual26_rep"]) / u["actual26_total"] * 100
    keep = ["unit_id", "name", "unit_type", "district_num", "county_fips",
            "dem_votes_2024", "rep_votes_2024", "other_votes_2024", "total_votes_2024", "dem_margin_pct",
            "expected_turnout", "baseline_margin_votes", "turnout22_rate",
            "registered_voters", "reg_dem", "reg_rep", "reg_una", "reg_oth",
            "persuasion_universe", "mobilization_universe",
            "actual26_dem", "actual26_rep", "actual26_other", "actual26_total", "actual26_margin_pct"]
    u = u[[c for c in keep if c in u.columns]].reset_index(drop=True)
    for c in ["dem_votes_2024", "rep_votes_2024", "other_votes_2024", "total_votes_2024", "registered_voters",
              "reg_dem", "reg_rep", "reg_una", "reg_oth", "actual26_dem", "actual26_rep", "actual26_other",
              "actual26_total"]:
        if c in u.columns:
            u[c] = u[c].round().astype("int64")
    return u
