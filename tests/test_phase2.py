"""Assertions on the Phase 2 participation outputs."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def table() -> pd.DataFrame:
    return pd.read_csv(ROOT / "reports" / "participation_by_games.csv")


@pytest.fixture(scope="module")
def report() -> dict:
    return json.loads((ROOT / "docs" / "phase2_participation.json").read_text())


def test_one_row_per_games(table):
    assert len(table) == 51
    assert table["games"].is_unique


def test_sexes_sum_to_athletes(table):
    assert (table["female"] + table["male"] == table["athletes"]).all()


def test_event_categories_sum_to_events(table):
    total = table["events_men"] + table["events_women"] + table["events_mixed"]
    assert (total == table["events"]).all()


def test_athletes_are_counted_once_per_games(table, report):
    """Not once per event entry. Rows overstate participation by roughly half."""
    assert table["athletes"].sum() == report["athlete_games_pairs"] == 187_452
    assert report["raw_rows"] == 271_116
    assert report["row_to_athlete_inflation"] > 1.4


def test_first_games_had_no_women(table):
    first = table.iloc[0]
    assert first["games"] == "1896 Summer"
    assert first["female"] == 0
    assert first["athletes"] == 176


def test_female_share_is_monotone_in_spirit(table):
    """Not strictly rising Games to Games, but every 20 year window is higher."""
    summer = table[table["season"] == "Summer"].set_index("year")["female_share"]
    for year in (1936, 1956, 1976, 1996):
        assert summer.loc[year + 20] > summer.loc[year]


def test_2016_is_near_parity_but_not_at_it(report):
    assert 44 < report["female_share_summer_2016"] < 46
    assert 43 < report["women_event_share_summer_2016"] < 45


def test_neutral_teams_are_not_counted_as_nations(table):
    """2016 carried Individual Olympic Athletes and a Refugee team. Neither is a country."""
    row = table[table["games"] == "2016 Summer"].iloc[0]
    assert row["noc_codes"] - row["nations"] == 2
    assert row["nations"] == 205


def test_boycott_years_show_in_the_nation_count(report):
    assert report["nations_1976_summer"] < report["nations_1972_summer"]
    assert report["nations_1980_summer"] < report["nations_1976_summer"]
    assert report["nations_1984_summer"] > report["nations_1972_summer"]


def test_programme_ran_ahead_of_the_field(report):
    """The share of women's events led the share of women athletes for decades."""
    assert report["winter_peak_share_gap_pp"] > 15
    assert report["winter_mean_share_gap_1960_1992_pp"] > report["summer_mean_share_gap_1960_1992_pp"]
    assert report["share_gap_summer_2016"] < 1


def test_figures_exist_and_are_not_blank(report):
    expected = {"events_by_sex.png", "female_share.png", "nations_growth.png", "participation_growth.png"}
    assert set(report["figures"]) == expected
    for name in expected:
        path = ROOT / "reports" / "figures" / name
        assert path.exists()
        assert path.stat().st_size > 20_000
