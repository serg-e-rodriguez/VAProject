"""
Region-level tables for the Senate (county) and House (congressional district) views, built from
the raw NCSBE files already downloaded by `ingest.ncsbe` plus the Census ZCTA->county file.

Tables
------
- candidates      : 2026 US Senate + US House nominees per race (from the 2026 ballot), with votes
- house_races     : per CD, 2026 US House result (Dem / Rep nominee, votes) and the 2024 seat holder
- demographics    : per county / CD / statewide x dimension (age, race, gender) x group x party:
                    registered voters (2024), registered (2022) and voted (2022)
- nc_zip_county   : NC ZIP code -> county (largest land-area overlap), for Google ad geo-targeting

Precinct -> CD uses the same 2026-ballot weights as `ingest.ncsbe` (precincts whose label is not on
the 2026 ballot are spread by their county's district mix). Counties are exact sums.
"""

from __future__ import annotations

import io
import logging
import urllib.request

import numpy as np
import pandas as pd

from campaign_intel.config import GEO_DIR
from campaign_intel.ingest import ncsbe

logger = logging.getLogger(__name__)

ZCTA_URL = "https://www2.census.gov/geo/docs/maps-data/data/rel2020/zcta520/tab20_zcta520_county20_natl.txt"
ZIP_COUNTY_CSV = GEO_DIR / "nc_zip_county.csv"

AGE = {"Age 18 - 25": "18–25", "Age 26 - 40": "26–40", "Age 41 - 65": "41–65", "Age Over 66": "66+"}
RACE = {"W": "White", "B": "Black", "A": "Asian", "I": "American Indian", "M": "Other / multiracial",
        "O": "Other / multiracial", "P": "Other / multiracial", "U": "Undesignated"}
SEX = {"F": "Women", "M": "Men", "U": "Undesignated"}
PARTY = {"DEM": "Dem", "REP": "Rep", "UNA": "Unaffiliated"}  # everything else -> "Other party"
DIMS = ("age", "race", "gender")


# ----------------------------------------------------------------------------- ZIP -> county
def zip_county() -> pd.DataFrame:
    """NC ZIP (ZCTA) -> county FIPS, by the largest land-area overlap. Cached as a small CSV."""
    if ZIP_COUNTY_CSV.exists():
        return pd.read_csv(ZIP_COUNTY_CSV, dtype=str)
    logger.info("Downloading Census ZCTA->county relationship file")
    raw = urllib.request.urlopen(ZCTA_URL, timeout=120).read().decode("utf-8-sig")
    rel = pd.read_csv(io.StringIO(raw), sep="|", dtype=str)
    rel = rel[rel["GEOID_COUNTY_20"].str.startswith("37", na=False) & rel["GEOID_ZCTA5_20"].notna()].copy()
    rel["area"] = pd.to_numeric(rel["AREALAND_PART"], errors="coerce").fillna(0)
    best = rel.sort_values("area", ascending=False).drop_duplicates("GEOID_ZCTA5_20")
    out = best.rename(columns={"GEOID_ZCTA5_20": "zip", "GEOID_COUNTY_20": "county_fips"})[["zip", "county_fips"]]
    out = out.sort_values("zip").reset_index(drop=True)
    ZIP_COUNTY_CSV.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(ZIP_COUNTY_CSV, index=False)
    return out


# ----------------------------------------------------------------------------- candidates & House
def _contest_table(results: pd.DataFrame, prefix: str) -> pd.DataFrame:
    sub = results[results["Contest Name"].str.startswith(prefix)]
    sub = sub[~sub["Choice"].str.contains("Write-In", case=False, na=False)]
    g = sub.groupby(["Contest Name", "Choice", "Choice Party"], as_index=False)["Total Votes"].sum()
    return g.rename(columns={"Contest Name": "contest", "Choice": "name", "Choice Party": "party",
                             "Total Votes": "votes"})


def candidates(r26: pd.DataFrame) -> pd.DataFrame:
    rows = []
    sen = _contest_table(r26, "US SENATE")
    sen = sen[sen["contest"] == "US SENATE"]
    for r in sen.itertuples():
        rows.append({"race": "senate", "unit_id": "NC", "party": r.party, "name": r.name, "votes": int(r.votes)})
    house = _contest_table(r26, "US HOUSE OF REPRESENTATIVES DISTRICT")
    house["unit_id"] = "CD" + house["contest"].str.extract(r"(\d+)\s*$")[0].astype(int).astype(str)
    for r in house.itertuples():
        rows.append({"race": "house", "unit_id": r.unit_id, "party": r.party, "name": r.name, "votes": int(r.votes)})
    return pd.DataFrame(rows)


def house_races(r24: pd.DataFrame, r26: pd.DataFrame) -> pd.DataFrame:
    """One row per CD: 2026 nominees and result, plus who won the seat in 2024."""
    cand = candidates(r26)
    h = cand[cand["race"] == "house"]
    out = []
    h24 = _contest_table(r24, "US HOUSE OF REPRESENTATIVES DISTRICT")
    h24["unit_id"] = "CD" + h24["contest"].str.extract(r"(\d+)\s*$")[0].astype(int).astype(str)
    for uid, g in h.groupby("unit_id"):
        d = g[g["party"] == "DEM"].sort_values("votes", ascending=False)
        r = g[g["party"] == "REP"].sort_values("votes", ascending=False)
        tot = int(g["votes"].sum())
        dv = int(d["votes"].iloc[0]) if len(d) else 0
        rv = int(r["votes"].iloc[0]) if len(r) else 0
        prev = h24[h24["unit_id"] == uid].sort_values("votes", ascending=False)
        out.append({
            "unit_id": uid, "district_num": int(uid[2:]),
            "dem_candidate": d["name"].iloc[0] if len(d) else "", "rep_candidate": r["name"].iloc[0] if len(r) else "",
            "house26_dem": dv, "house26_rep": rv, "house26_total": tot,
            "house26_margin_pct": (dv - rv) / tot * 100 if tot else np.nan,
            "held_by_2024": {"DEM": "Dem", "REP": "Rep"}.get(prev["party"].iloc[0], "Other") if len(prev) else "",
            "holder_2024": prev["name"].iloc[0] if len(prev) else "",
        })
    return pd.DataFrame(out).sort_values("district_num").reset_index(drop=True)


# ----------------------------------------------------------------------------- demographics
def _groups(df: pd.DataFrame) -> pd.DataFrame:
    """Adds dimension groups + party group columns to a voter_stats / history_stats frame."""
    d = df.copy()
    d["age_g"] = d["age"].map(AGE)
    hisp = d["ethnic_code"].eq("HL")
    d["race_g"] = np.where(hisp, "Hispanic / Latino", d["race_code"].map(RACE).fillna("Undesignated"))
    d["gender_g"] = d["sex_code"].map(SEX).fillna("Undesignated")
    d["party_g"] = d["party_cd"].map(PARTY).fillna("Other party")
    d = d.rename(columns={"county_desc": "County", "precinct_abbrv": "Precinct"})
    return d[d["age_g"].notna()]


def _wide(d: pd.DataFrame, measure: str) -> pd.DataFrame:
    """Precinct rows x '<dim>|<group>|<party>' columns of voter counts (one measure)."""
    frames = []
    for dim in DIMS:
        p = d.pivot_table(index=["County", "Precinct"], columns=[f"{dim}_g", "party_g"], values="total_voters",
                          aggfunc="sum", fill_value=0)
        p.columns = [f"{measure}|{dim}|{g}|{pty}" for g, pty in p.columns]
        frames.append(p)
    return pd.concat(frames, axis=1).fillna(0).reset_index()


def _long(wide: pd.DataFrame, id_cols: list[str]) -> pd.DataFrame:
    m = wide.melt(id_vars=id_cols, var_name="key", value_name="n")
    parts = m["key"].str.split("|", expand=True)
    m["measure"], m["dim"], m["group"], m["party"] = parts[0], parts[1], parts[2], parts[3]
    return m.drop(columns="key")


def demographics(paths: dict, cd_weights: pd.DataFrame, fips: dict[str, str]) -> pd.DataFrame:
    sources = {
        "reg24": _groups(ncsbe.read_stats(paths["voters_2024"])),
        "reg22": _groups(ncsbe.read_stats(paths["voters_2022"])),
        "voted22": _groups(ncsbe.read_stats(paths["history_2022"])),
    }
    longs = []
    for measure, d in sources.items():
        w = _wide(d, measure)
        cols = [c for c in w.columns if c.startswith(measure + "|")]
        # counties: exact
        cty = w.groupby("County", as_index=False)[cols].sum()
        cty["unit_type"], cty["unit_id"] = "county", cty["County"].map(fips)
        longs.append(_long(cty.drop(columns="County"), ["unit_type", "unit_id"]))
        # congressional districts: precinct weights from the 2026 ballots
        cd = ncsbe._apply_weights(w, cd_weights, cols)
        cd = cd.groupby("unit_id", as_index=False)[cols].sum()
        cd["unit_type"] = "cd"
        longs.append(_long(cd, ["unit_type", "unit_id"]))
        st = pd.DataFrame([w[cols].sum()])
        st["unit_type"], st["unit_id"] = "state", "NC"
        longs.append(_long(st, ["unit_type", "unit_id"]))
    allm = pd.concat(longs, ignore_index=True)
    out = allm.pivot_table(index=["unit_type", "unit_id", "dim", "group", "party"], columns="measure", values="n",
                           aggfunc="sum", fill_value=0).reset_index()
    out.columns.name = None
    for c in ["reg24", "reg22", "voted22"]:
        out[c] = out[c].round().astype("int64")
    return out


def build() -> dict[str, pd.DataFrame]:
    paths = ncsbe.download()
    fips = ncsbe.county_fips_lookup()
    r24, r26 = ncsbe.read_results(paths["results_2024"]), ncsbe.read_results(paths["results_2026"])
    w26 = ncsbe.precinct_district_weights(r26)
    cd_w = w26[w26["unit_type"] == "cd"]
    return {
        "candidates": candidates(r26),
        "house_races": house_races(r24, r26),
        "demographics": demographics(paths, cd_w, fips),
        "nc_zip_county": zip_county(),
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    for k, v in build().items():
        print(k, v.shape)
        print(v.head(3).to_string())
