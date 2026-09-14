"""Assertions on the Phase 4 host advantage outputs."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def ledger() -> pd.DataFrame:
    return pd.read_csv(ROOT / "reports" / "host_advantage.csv")


@pytest.fixture(scope="module")
def report() -> dict:
    return json.loads((ROOT / "docs" / "phase4_host_advantage.json").read_text())


def test_one_row_per_recognised_hosting_event(ledger):
    """51 Games minus the 1906 Intercalated Games, which the IOC does not recognise."""
    assert len(ledger) == 50
    assert "1906 Summer" not in set(ledger["games"])


def test_clean_flag_matches_the_neighbour_counts(ledger):
    assert ((ledger["n_before"] >= 1) & (ledger["n_after"] >= 1) == ledger["clean"]).all()


def test_edge_cases_are_the_boundary_games(ledger):
    """Edge cases cluster at the start and end of each season's history, by construction."""
    edge = ledger[~ledger["clean"]]
    assert len(edge) == 5
    assert set(edge["games"]) <= {"1896 Summer", "2016 Summer", "1924 Winter", "1984 Winter", "2014 Winter"}


def test_lift_equals_host_share_minus_baseline(ledger):
    computed = ledger["host_share_pct"] - ledger["baseline_share_pct"]
    assert (computed.round(2) - ledger["lift_pp"]).abs().max() < 0.02


def test_host_advantage_is_positive_on_average(report):
    """The headline claim. A one sided test would overstate confidence, so this uses
    the bootstrap CI: it must exclude zero, on the low side, to count as a real effect."""
    lo, hi = report["median_lift_ci95"]
    assert lo > 0
    assert report["median_lift_pp"] > 0
    assert report["wilcoxon_p_value"] < 0.001


def test_effect_survives_in_the_modern_era_alone(report):
    """Pre-1950 Games are a different sport in a different world. The claim should
    not depend on including them."""
    lo, hi = report["median_lift_modern_ci95"]
    assert lo > 0
    assert report["wilcoxon_p_value_modern"] < 0.01
    assert report["median_lift_modern"] < report["median_lift_early"]


def test_effect_is_not_universal(report):
    """Some hosts do worse than their own baseline. The design should show that,
    not paper over it with an average."""
    assert 2 <= report["negative_lift_count"] <= 8
    assert report["negative_lift_count"] < report["hosting_events_clean"] / 4


def test_1904_is_flagged_as_the_extreme_not_hidden(ledger, report):
    row = ledger[ledger["games"] == "1904 Summer"].iloc[0]
    assert row["host"] == "USA"
    assert row["lift_pp"] > 50
    assert report["extreme_case"]["games"] == "1904 Summer"


def test_moscow_1980_is_a_real_boycott_thinned_host_gain(ledger):
    """The Soviet Union's own lift in the Games it boycotted itself, 1984, is absent
    from the ledger; but 1980, which it hosted, should show a large lift consistent
    with the concentration finding in Phase 3."""
    row = ledger[ledger["games"] == "1980 Summer"].iloc[0]
    assert row["host"] == "URS"
    assert row["lift_pp"] > 10


def test_figures_exist_and_are_not_blank(report):
    for name in report["figures"]:
        path = ROOT / "reports" / "figures" / name
        assert path.exists() and path.stat().st_size > 15_000
