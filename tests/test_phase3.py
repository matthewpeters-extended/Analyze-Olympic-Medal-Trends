"""Assertions on the Phase 3 concentration outputs and on the break finder."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from changepoint import find_breaks  # noqa: E402


@pytest.fixture(scope="module")
def table() -> pd.DataFrame:
    return pd.read_csv(ROOT / "reports" / "concentration_by_games.csv")


@pytest.fixture(scope="module")
def report() -> dict:
    return json.loads((ROOT / "docs" / "phase3_concentration.json").read_text())


# the break finder


def test_finds_a_planted_break():
    values = np.array([1, 1, 1.1, 0.9, 1, 5, 5.1, 4.9, 5, 5.2])
    breaks, segments = find_breaks(values)
    assert breaks == [5]
    assert len(segments) == 2
    assert segments[0].mean == pytest.approx(1.0, abs=0.05)
    assert segments[1].mean == pytest.approx(5.0, abs=0.1)


def test_finds_nothing_in_noise():
    noise = np.random.RandomState(0).normal(0, 1, 40)
    breaks, segments = find_breaks(noise)
    assert breaks == []
    assert len(segments) == 1


def test_finds_nothing_in_a_constant_series():
    breaks, segments = find_breaks(np.ones(20))
    assert breaks == []


def test_respects_the_minimum_segment_length():
    """One wild point at the end must not become a regime of its own."""
    values = np.concatenate([np.ones(15), [40.0]])
    breaks, segments = find_breaks(values, min_size=3)
    assert all(segment.n >= 3 for segment in segments)


# the concentration table


def test_one_row_per_recognised_games(table):
    """51 Games in the file, minus the 1906 Intercalated Games the IOC does not count."""
    assert len(table) == 50
    assert 1906 not in set(table["year"])


def test_shares_are_ordered(table):
    assert (table["top5_share"] >= table["top3_share"]).all()
    assert (table["top3_share"] >= table["leader_share"]).all()
    assert (table["top5_share"] <= 100.0001).all()


def test_effective_number_is_the_reciprocal_of_hhi(table):
    assert np.allclose(table["effective_countries"], 1 / table["hhi"])


def test_effective_number_never_exceeds_the_winner_count(table):
    assert (table["effective_countries"] <= table["winners"] + 1e-9).all()


def test_merging_states_can_only_lower_the_effective_number(table):
    assert (table["effective_countries_remerged"] <= table["effective_countries"] + 1e-9).all()


# the findings


def test_summer_has_three_regimes_breaking_in_1912_and_1996(report):
    assert len(report["summer_regimes"]) == 3
    assert report["summer_break_years"] == [1912, 1996]


def test_the_cold_war_is_not_a_break(report):
    """The 1912 to 1992 plateau spans both world wars, the Cold War and every boycott."""
    plateau = report["summer_regimes"][1]
    assert plateau["from_year"] == 1912
    assert plateau["to_year"] == 1992
    assert plateau["games_count"] == 18
    assert not any(1945 <= year <= 1992 for year in report["summer_break_years"])


def test_most_of_the_modern_broadening_is_redefinition(report):
    assert report["rise_actual"] > report["rise_after_remerging"] > 0
    assert 50 <= report["pct_of_rise_that_is_redefinition"] <= 65


def test_st_louis_1904_is_the_extreme(table, report):
    assert report["st_louis_1904_leader_share"] > 80
    assert report["st_louis_1904_effective"] < 2
    assert table["leader_share"].max() == pytest.approx(report["st_louis_1904_leader_share"], abs=0.05)


def test_a_boycott_concentrates_only_when_it_thins_the_field(report):
    """1980 left 80 nations and spiked concentration. 1984 left 140 and did not."""
    assert report["moscow_1980_effective"] < report["plateau_mean_effective"]
    assert report["los_angeles_1984_effective"] == pytest.approx(
        report["plateau_mean_effective"], abs=0.5
    )


def test_figures_exist_and_are_not_blank(report):
    expected = {"bloc_shares.png", "concentration_regimes.png",
                "fragmentation_counterfactual.png", "top5_share.png"}
    assert expected <= set(report["figures"])
    for name in expected:
        path = ROOT / "reports" / "figures" / name
        assert path.exists() and path.stat().st_size > 20_000
