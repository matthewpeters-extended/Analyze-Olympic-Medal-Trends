"""Assertions on the Phase 1 outputs.

These are grain and identity checks. They exist so that a change to the cleaning rules
cannot quietly move a number the README quotes.

Run:
    ./.venv/bin/python -m pytest -q
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def medals() -> pd.DataFrame:
    return pd.read_parquet(ROOT / "data" / "processed" / "medals.parquet")


@pytest.fixture(scope="module")
def athletes() -> pd.DataFrame:
    return pd.read_parquet(ROOT / "data" / "processed" / "athletes.parquet")


@pytest.fixture(scope="module")
def report() -> dict:
    return json.loads((ROOT / "docs" / "phase1_cleaning.json").read_text())


@pytest.fixture(scope="module")
def noc_map() -> pd.DataFrame:
    return pd.read_csv(ROOT / "reference" / "noc_country_map.csv")


def test_athletes_keeps_every_raw_row(athletes, report):
    assert len(athletes) == report["raw_rows"] == 271_116


def test_medal_count_is_stable(medals, report):
    assert len(medals) == report["medals_awarded"] == 18_952


def test_team_medals_are_collapsed(medals):
    team = medals[medals["is_team_event"]]
    assert not team.duplicated(["games", "event", "medal", "noc"]).any()


def test_team_medals_really_are_teams(medals):
    assert (medals.loc[medals["is_team_event"], "team_size"] >= 1).all()
    assert (medals.loc[~medals["is_team_event"], "team_size"] == 1).all()


def test_beats_the_naive_dedupe(report):
    """The usual (games, event, medal, noc) dedupe drops real medals. Prove it still does."""
    assert report["medals_recovered_over_naive_dedupe"] > 0
    assert report["medals_awarded"] > report["naive_dedupe_medals"]


def test_known_team_gold_appears_once(medals):
    """The Dream Team won one gold, not twelve."""
    hit = medals[
        (medals["games"] == "1992 Summer")
        & (medals["event"] == "Basketball Men's Basketball")
        & (medals["medal"] == "Gold")
    ]
    assert len(hit) == 1
    assert hit.iloc[0]["noc"] == "USA"
    assert hit.iloc[0]["team_size"] > 1


def test_tied_individual_medals_survive(medals):
    """Athens 1896 awarded two silvers in the men's high jump, both to the United States."""
    hit = medals[
        (medals["games"] == "1896 Summer")
        & (medals["event"] == "Athletics Men's High Jump")
        & (medals["medal"] == "Silver")
        & (medals["noc"] == "USA")
    ]
    assert len(hit) == 2


def test_every_noc_is_mapped(athletes, noc_map):
    assert set(athletes["noc"]) <= set(noc_map["noc"])
    assert athletes["rollup_noc"].notna().all()
    assert noc_map["noc"].is_unique


def test_rollup_targets_exist(noc_map):
    assert set(noc_map["rollup_noc"]) <= set(noc_map["noc"])


def test_non_countries_are_flagged(noc_map):
    assert set(noc_map.loc[noc_map["status"] == "non_country", "noc"]) == {"IOA", "ROT", "UNK"}


def test_every_dissolved_state_carries_a_note(noc_map):
    dissolved = noc_map[noc_map["status"] != "active"]
    assert dissolved["note"].str.len().gt(0).all()


def test_germany_rolls_up_but_stays_separate_by_noc(noc_map):
    rollups = noc_map.set_index("noc")["rollup_noc"]
    assert rollups["GDR"] == rollups["FRG"] == rollups["GER"] == "GER"
    assert len({"GDR", "FRG", "GER"}) == 3


def test_unrecognised_games_are_flagged_not_dropped(athletes, report):
    assert report["rows_1906"] == 1_733
    assert report["medals_art_competitions"] == 156
    assert (athletes["year"] == 1906).sum() == 1_733
    assert (~athletes["ioc_recognised"]).sum() == report["rows_not_ioc_recognised"]


def test_every_games_has_a_host(athletes):
    assert athletes["host_noc"].notna().all()


def test_host_flag_matches_a_known_case(medals):
    """Moscow 1980 was hosted by the Soviet Union."""
    moscow = medals[medals["games"] == "1980 Summer"]
    assert (moscow["host_noc"] == "URS").all()
    assert moscow.loc[moscow["noc"] == "URS", "is_host"].all()
    assert not moscow.loc[moscow["noc"] != "URS", "is_host"].any()
