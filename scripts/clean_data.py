"""Phase 1: clean the raw file and write the two tables everything else reads.

Outputs
-------
data/processed/athletes.parquet   athlete by event grain, the raw rows plus derived flags
data/processed/medals.parquet     one row per medal actually awarded
docs/phase1_cleaning.json         every count this script measured, for the README check

The five defects fixed here are listed in PLAN.md. The largest by far is that the raw
file stores a team medal once per squad member, so a hockey gold appears twenty times.

Counting medals correctly
-------------------------
The usual fix is to drop duplicates on (games, event, medal, noc). That is close, and it
is wrong in one direction: it also collapses the cases where a single country legitimately
won two of the same medal in the same event. Two bronzes are awarded in boxing, judo and
wrestling, and ties for a place happened often in the early Games. Athens 1896 alone has
two American silvers in the men's high jump.

So the rule here classifies each event instance first:

    median size of the (medal, noc) groups >= 2   ->  team event, collapse to one medal
    otherwise                                     ->  individual event, one medal per row

The median is what makes this robust. It survives an individual event where two athletes
from one country tied, because most groups there are still size one, and it survives a
team event where one squad is recorded with a single member. The rule was checked against
a list of known team and individual events and disagrees with it exactly once, on the 1900
mixed doubles in tennis, where the pairs really were made of players from different
countries. Per athlete counting is the right answer there, which is what the rule does.

Usage:
    python scripts/clean_data.py
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "olympics.csv"
PROCESSED = ROOT / "data" / "processed"
REFERENCE = ROOT / "reference"
REPORT = ROOT / "docs" / "phase1_cleaning.json"

UNRECOGNISED_YEAR = 1906
UNRECOGNISED_SPORT = "Art Competitions"


def classify_events(medals: pd.DataFrame) -> set[tuple[str, str]]:
    """Return the (games, event) instances that are team events."""
    sizes = medals.groupby(["games", "event", "medal", "noc"]).size().rename("n").reset_index()
    median = sizes.groupby(["games", "event"])["n"].median()
    return set(median[median >= 2].index)


def main() -> int:
    report: dict[str, object] = {}

    raw = pd.read_csv(RAW)
    report["raw_rows"] = len(raw)
    report["raw_athletes"] = int(raw["id"].nunique())
    report["raw_nocs"] = int(raw["noc"].nunique())
    report["raw_games"] = int(raw["games"].nunique())
    report["raw_sports"] = int(raw["sport"].nunique())
    report["raw_events"] = int(raw["event"].nunique())
    report["raw_year_min"] = int(raw["year"].min())
    report["raw_year_max"] = int(raw["year"].max())

    report["missing_pct"] = {
        column: round(100 * raw[column].isna().mean(), 1)
        for column in ("age", "height", "weight")
    }

    # Defect 2 and 3: the 1906 Intercalated Games and the Art Competitions are in the
    # file but not in the IOC record. Flagged, never silently dropped.
    is_1906 = raw["year"] == UNRECOGNISED_YEAR
    is_art = raw["sport"] == UNRECOGNISED_SPORT
    raw["ioc_recognised"] = ~(is_1906 | is_art)
    report["rows_1906"] = int(is_1906.sum())
    report["rows_art_competitions"] = int(is_art.sum())
    report["medals_art_competitions"] = int((is_art & raw["medal"].notna()).sum())
    report["rows_not_ioc_recognised"] = int((~raw["ioc_recognised"]).sum())

    # Defect 4: country identity. See reference/noc_country_map.csv and the script that
    # builds it for the reasoning behind every non identity mapping.
    noc_map = pd.read_csv(REFERENCE / "noc_country_map.csv").fillna({"note": ""})
    unmapped = sorted(set(raw["noc"]) - set(noc_map["noc"]))
    if unmapped:
        print(f"FAILED: no mapping for {unmapped}. Rerun scripts/build_noc_map.py.")
        return 1
    raw = raw.merge(noc_map[["noc", "entity_name", "status", "rollup_noc"]], on="noc", how="left")
    report["noc_status_counts"] = {
        str(k): int(v) for k, v in noc_map["status"].value_counts().items()
    }
    report["nocs_rolled_up"] = int((noc_map["noc"] != noc_map["rollup_noc"]).sum())

    hosts = pd.read_csv(REFERENCE / "host_nations.csv").fillna({"note": ""})
    raw = raw.merge(hosts[["games", "host_noc"]], on="games", how="left")
    raw["is_host"] = raw["noc"] == raw["host_noc"]

    PROCESSED.mkdir(parents=True, exist_ok=True)
    raw.to_parquet(PROCESSED / "athletes.parquet", index=False)
    print(f"wrote data/processed/athletes.parquet  rows={len(raw):,}")

    # Defect 1: team medals stored once per athlete.
    medal_rows = raw[raw["medal"].notna()].copy()
    report["athlete_medal_rows"] = len(medal_rows)
    report["naive_dedupe_medals"] = len(
        medal_rows.drop_duplicates(["games", "event", "medal", "noc"])
    )

    team_instances = classify_events(medal_rows)
    key = pd.MultiIndex.from_arrays([medal_rows["games"], medal_rows["event"]])
    medal_rows["is_team_event"] = key.isin(team_instances)

    individual = medal_rows[~medal_rows["is_team_event"]].copy()
    individual["team_size"] = 1
    team = medal_rows[medal_rows["is_team_event"]].copy()
    team["team_size"] = team.groupby(["games", "event", "medal", "noc"])["id"].transform("size")
    team = team.drop_duplicates(["games", "event", "medal", "noc"])

    columns = [
        "games", "year", "season", "city", "sport", "event", "medal",
        "noc", "entity_name", "status", "rollup_noc",
        "is_team_event", "team_size", "ioc_recognised", "host_noc", "is_host",
    ]
    medals = pd.concat([individual[columns], team[columns]], ignore_index=True)
    medals = medals.sort_values(["year", "season", "sport", "event", "medal"]).reset_index(drop=True)
    medals.to_parquet(PROCESSED / "medals.parquet", index=False)
    print(f"wrote data/processed/medals.parquet    rows={len(medals):,}")

    report["event_instances"] = int(medal_rows.groupby(["games", "event"]).ngroups)
    report["team_event_instances"] = len(team_instances)
    report["medals_awarded"] = len(medals)
    report["medals_from_individual_events"] = len(individual)
    report["medals_from_team_events"] = len(team)
    report["medals_recovered_over_naive_dedupe"] = (
        report["medals_awarded"] - report["naive_dedupe_medals"]
    )
    report["inflation_factor_of_raw_medal_rows"] = round(
        report["athlete_medal_rows"] / report["medals_awarded"], 2
    )
    report["medals_ioc_recognised"] = int(medals["ioc_recognised"].sum())
    report["medal_type_counts"] = {
        str(k): int(v) for k, v in medals["medal"].value_counts().items()
    }
    report["largest_team_size"] = int(medals["team_size"].max())

    REPORT.parent.mkdir(exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(f"wrote docs/{REPORT.name}")

    print()
    print(f"  athlete medal rows      {report['athlete_medal_rows']:,}")
    print(f"  naive dedupe            {report['naive_dedupe_medals']:,}")
    print(f"  medals actually awarded {report['medals_awarded']:,}"
          f"  (+{report['medals_recovered_over_naive_dedupe']} the naive rule loses)")
    print(f"  of which IOC recognised {report['medals_ioc_recognised']:,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
