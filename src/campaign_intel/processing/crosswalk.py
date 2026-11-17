"""
MEDSL 2022 US Senate county returns (cross-check of the NCSBE baseline) and vote-method splits.
District-level figures are built from NCSBE precinct files in campaign_intel.ingest.ncsbe.
"""

import numpy as np
import pandas as pd

from campaign_intel.config import DATA_DIR


def load_senate_2022_baseline() -> pd.DataFrame:
    """
    Parses MEDSL 2022 U.S. Senate returns (senate_2022.csv) for North Carolina.
    Drops write-ins; computes candidate votes and margins by county and vote mode.
    Guarantees county totals sum from candidatevotes (per §6.4 item 9 & 10).
    """
    csv_file = DATA_DIR / "senate_2022.csv"
    if not csv_file.exists():
        return pd.DataFrame()

    df = pd.read_csv(csv_file, low_memory=False)
    nc = df[df["state_po"] == "NC"].copy()

    # Drop write-ins per §6.4
    nc = nc[nc["writein"].astype(str).str.lower() != "true"]

    # Clean county FIPS as 5-character string
    nc["county_fips"] = nc["county_fips"].apply(lambda x: str(int(float(x))).zfill(5) if pd.notna(x) else "")
    nc["county_name"] = nc["county_name"].str.title().str.strip()

    # Party simplified
    def clean_party(row):
        cand = str(row["candidate"]).upper()
        p = str(row["party_detailed"]).upper()
        if "BUDD" in cand or "REPUBLICAN" in p:
            return "REP"
        elif "BEASLEY" in cand or "DEMOCRAT" in p:
            return "DEM"
        return "OTHER"

    nc["party_clean"] = nc.apply(clean_party, axis=1)

    return nc


def get_county_baselines() -> pd.DataFrame:
    """
    Rolls up 2022 Senate baseline results by county.
    Returns: county_fips, county_name, dem_votes, rep_votes, other_votes, total_votes, margin_votes, dem_margin_pct.
    """
    nc = load_senate_2022_baseline()
    if nc.empty:
        return pd.DataFrame()

    piv = nc.pivot_table(
        index=["county_fips", "county_name"],
        columns="party_clean",
        values="candidatevotes",
        aggfunc="sum",
        fill_value=0.0
    ).reset_index()

    piv["dem_votes"] = piv.get("DEM", 0.0)
    piv["rep_votes"] = piv.get("REP", 0.0)
    piv["other_votes"] = piv.get("OTHER", 0.0)
    piv["total_votes"] = piv["dem_votes"] + piv["rep_votes"] + piv["other_votes"]
    piv["margin_votes"] = piv["dem_votes"] - piv["rep_votes"]
    piv["baseline_margin_votes"] = piv["margin_votes"]
    piv["dem_margin_pct"] = np.where(
        piv["total_votes"] > 0,
        (piv["margin_votes"] / piv["total_votes"]) * 100.0,
        0.0
    )
    piv["unit_id"] = piv["county_fips"]
    piv["name"] = piv["county_name"]
    piv["unit_type"] = "county"

    return piv[["unit_id", "name", "county_fips", "dem_votes", "rep_votes", "other_votes", "total_votes", "margin_votes", "dem_margin_pct", "unit_type"]]


def get_vote_method_splits() -> pd.DataFrame:
    """
    Rolls up vote methods (One Stop, Absentee by Mail, Election Day, Provisional) from 2022 baseline.
    """
    nc = load_senate_2022_baseline()
    if nc.empty:
        return pd.DataFrame()

    modes = nc.groupby(["mode", "party_clean"], as_index=False)["candidatevotes"].sum()
    modes.rename(columns={"mode": "vote_method", "candidatevotes": "votes"}, inplace=True)
    return modes
