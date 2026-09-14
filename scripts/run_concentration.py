"""Phase 3: how concentrated are Olympic medals, and when did that change.

Reads data/processed/medals.parquet and writes

    docs/phase3_concentration.json      every number, for the README check
    reports/concentration_by_games.csv  the full per Games table
    reports/figures/*.png               four figures

Measures
--------
Medals are counted at the grain Phase 1 established, one row per medal actually
awarded, so a team gold counts once. Shares are of the medals awarded at that
Games. Neutral and refugee teams are excluded, and the 1906 Intercalated Games and
the Art Competitions are excluded, because the IOC does not recognise them.

    top 5 share       what the five leading committees took, in percent
    hhi               Herfindahl Hirschman index, the sum of squared shares. The
                      same statistic used to measure market concentration.
    effective number  1 / hhi. The number of equally sized committees that would
                      produce the observed concentration. This is the readable
                      version and it is what the break search runs on.

Breaks are located rather than assumed. See src/changepoint.py.

Usage:
    python scripts/run_concentration.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from changepoint import find_breaks  # noqa: E402
from plotstyle import AQUA, BAND, BLUE, GRID, INK_FAINT, ORANGE, apply_style, caption, label_end, tidy  # noqa: E402

PROCESSED = ROOT / "data" / "processed"
FIGURES = ROOT / "reports" / "figures"
REPORT = ROOT / "docs" / "phase3_concentration.json"

# The figures this phase writes. Listed rather than globbed, so that a figure
# from another phase cannot wander into this phase's report.
FIGURE_NAMES = ['bloc_shares.png', 'concentration_regimes.png', 'fragmentation_counterfactual.png', 'top5_share.png']

SOURCE = "Source: 18,952 Olympic medals, counted once each, 1896 to 2016."

# Successor groupings for the counterfactual. These undo the redefinition of three
# states so that the post 1992 series can be compared with the pre 1992 series on
# like terms. They are deliberately separate from reference/noc_country_map.csv,
# which keeps these entities distinct because that is what the IOC does.
SOVIET = {
    "URS", "EUN", "ARM", "AZE", "BLR", "EST", "GEO", "KAZ", "KGZ", "LAT",
    "LTU", "MDA", "RUS", "TJK", "TKM", "UKR", "UZB",
}
YUGOSLAV = {"YUG", "BIH", "CRO", "KOS", "MKD", "MNE", "SCG", "SLO", "SRB"}
CZECHOSLOVAK = {"TCH", "CZE", "SVK"}

REGIME_LABELS = {
    ("Summer", 0): "founding era",
    ("Summer", 1): "the long plateau",
    ("Summer", 2): "after the Soviet split",
}


def remerge(noc: str) -> str:
    if noc in SOVIET:
        return "SOVIET"
    if noc in YUGOSLAV:
        return "YUGOSLAV"
    if noc in CZECHOSLOVAK:
        return "CZECHOSLOVAK"
    return noc


def effective_number(codes: pd.Series) -> float:
    shares = codes.value_counts() / len(codes)
    return 1.0 / float((shares**2).sum())


def herfindahl(codes: pd.Series) -> float:
    shares = codes.value_counts() / len(codes)
    return float((shares**2).sum())


def build_table(medals: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (games, year, season), sub in medals.groupby(["games", "year", "season"]):
        counts = sub["noc"].value_counts()
        shares = 100 * counts / counts.sum()
        rows.append({
            "games": games,
            "year": int(year),
            "season": season,
            "medals": len(sub),
            "winners": int(counts.size),
            "leader": counts.index[0],
            "leader_share": float(shares.iloc[0]),
            "top3_share": float(shares.head(3).sum()),
            "top5_share": float(shares.head(5).sum()),
            "hhi": herfindahl(sub["noc"]),
            "effective_countries": effective_number(sub["noc"]),
            "effective_countries_remerged": effective_number(sub["noc"].map(remerge)),
        })
    return pd.DataFrame(rows).sort_values(["year", "season"]).reset_index(drop=True)


def detect_regimes(table: pd.DataFrame, season: str) -> tuple[pd.DataFrame, list[dict]]:
    sub = table[table["season"] == season].reset_index(drop=True)
    breaks, segments = find_breaks(sub["effective_countries"].to_numpy())
    described = [{
        "from_year": int(sub["year"].iloc[segment.start]),
        "to_year": int(sub["year"].iloc[segment.stop - 1]),
        "games_count": segment.n,
        "mean_effective_countries": round(segment.mean, 1),
    } for segment in segments]
    return sub, described


def figure_regimes(table: pd.DataFrame, regimes: dict[str, list[dict]]) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(11, 5), sharey=True)
    for ax, season in zip(axes, ("Summer", "Winter")):
        sub = table[table["season"] == season].set_index("year")
        colour = BLUE if season == "Summer" else ORANGE
        for index, regime in enumerate(regimes[season]):
            left = regime["from_year"] - (2 if index else 4)
            right = regime["to_year"] + (2 if index < len(regimes[season]) - 1 else 4)
            if index % 2:
                ax.axvspan(left, right, color=BAND, zorder=0, linewidth=0)
            ax.hlines(regime["mean_effective_countries"], regime["from_year"], regime["to_year"],
                      color=INK_FAINT, linewidth=1.4, linestyle=(0, (4, 3)), zorder=2)
            # Regime labels sit at the top of their band rather than next to the
            # dashed line. Chasing a clear spot beside a wandering series is how
            # labels end up on top of it. Heights alternate so that two narrow
            # bands in a row cannot collide.
            ax.annotate(f"mean {regime['mean_effective_countries']}",
                        xy=((max(left, sub.index.min()) + right) / 2,
                            25.8 if index % 2 == 0 else 23.4),
                        ha="center", va="center", fontsize=9, color=INK_FAINT, zorder=4)
        ax.plot(sub.index, sub["effective_countries"], color=colour, zorder=3)
        ax.set_title(season)
        ax.set_ylim(0, 27.5)
        tidy(ax, "effective number of medal winning countries" if season == "Summer" else "")

    axes[0].annotate("the Cold War sits inside\none regime, not on a break",
                     xy=(1972, 12.2), xytext=(1928, 19.0), fontsize=9, color=INK_FAINT,
                     arrowprops=dict(arrowstyle="-", color=INK_FAINT, linewidth=1.0))
    fig.suptitle("Medal concentration changed twice, and not when you would guess",
                 x=0.005, ha="left", fontsize=13, fontweight="bold", y=1.02)
    caption(fig, SOURCE + " Shaded bands are the regimes found by binary segmentation with a BIC "
                 "penalty, searching every split point rather than assumed dates.")
    fig.savefig(FIGURES / "concentration_regimes.png")
    plt.close(fig)


def figure_counterfactual(table: pd.DataFrame) -> None:
    sub = table[(table["season"] == "Summer") & (table["year"] >= 1976)]
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(sub["year"], sub["effective_countries"], color=BLUE, zorder=3)
    ax.plot(sub["year"], sub["effective_countries_remerged"], color=ORANGE, zorder=3)
    last = sub.iloc[-1]
    label_end(ax, last["year"], last["effective_countries"], "as recorded", BLUE, dx=1.5)
    label_end(ax, last["year"], last["effective_countries_remerged"],
              "with the successor states\nput back together", ORANGE, dx=1.5)
    ax.fill_between(sub["year"], sub["effective_countries_remerged"], sub["effective_countries"],
                    color=GRID, alpha=0.6, zorder=1, label="redefinition of countries")
    ax.axvline(1992, color=GRID, linewidth=1.2, zorder=1)
    ax.annotate("Soviet Union dissolves", xy=(1992, 5), xytext=(1993, 5),
                fontsize=9, color=INK_FAINT, va="center")
    ax.set_title("More than half of the post 1992 broadening is bookkeeping")
    ax.set_xlim(1974, 2032)
    ax.set_ylim(0, 27)
    tidy(ax, "effective number of medal winning countries")
    ax.legend(loc="upper left")
    caption(fig, SOURCE + " The orange line recombines the Soviet, Yugoslav and Czechoslovak "
                 "successor states into one competitor each, the way they entered before 1992."
                 " The two lines are identical before 1992, when there was nothing to recombine.")
    fig.savefig(FIGURES / "fragmentation_counterfactual.png")
    plt.close(fig)


def figure_top5(table: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(9, 5))
    for season, colour in (("Summer", BLUE), ("Winter", ORANGE)):
        sub = table[table["season"] == season]
        ax.plot(sub["year"], sub["top5_share"], color=colour, label=season, zorder=3)
        last = sub.iloc[-1]
        label_end(ax, last["year"], last["top5_share"], season, colour)

    summer = table[table["season"] == "Summer"].set_index("year")
    notes = (
        (1904, "St Louis: almost nobody\ntravelled, and the hosts\ntook 83 percent", 1908, 99),
        (1980, "Moscow, with 80 nations\nafter the boycott", 1986, 82),
        (1984, "Los Angeles, with 140 nations\nafter the return boycott", 1934, 38),
    )
    for year, note, text_x, text_y in notes:
        ax.annotate(note, xy=(year, summer.loc[year, "top5_share"]), xytext=(text_x, text_y),
                    fontsize=9, color=INK_FAINT, ha="left", va="top",
                    arrowprops=dict(arrowstyle="-", color=GRID, linewidth=1.2))

    ax.set_title("Share of medals taken by the five leading committees")
    ax.set_xlim(1890, 2032)
    ax.set_ylim(20, 100)
    tidy(ax, "percent of medals at that Games")
    ax.legend(loc="lower left")
    caption(fig, SOURCE + " A boycott raises concentration only when it thins the field, "
                 "which 1980 did and 1984 did not.")
    fig.savefig(FIGURES / "top5_share.png")
    plt.close(fig)


def figure_blocs(medals: pd.DataFrame, athletes: pd.DataFrame) -> None:
    """Medal share for the three Cold War heavyweights.

    A boycott is absence, not a zero. If a committee sent nobody to a Games it gets
    a gap in its line, not a value of zero percent, and the same rule hides East
    Germany before 1968 and after 1988 rather than drawing it flat along the axis.
    """
    summer = medals[(medals["season"] == "Summer") & medals["year"].between(1952, 1992)]
    entered = athletes[(athletes["season"] == "Summer") & athletes["year"].between(1952, 1992)]
    totals = summer.groupby("year").size()
    years = totals.index

    series = {
        "United States": (("USA",), BLUE, (1960, 15.4), (0, -20)),
        "Soviet Union": (("URS", "EUN"), ORANGE, (1980, 30.9), (5, 5)),
        "East Germany": (("GDR",), AQUA, (1980, 20.0), (7, -3)),
    }
    fig, ax = plt.subplots(figsize=(9, 5))
    for name, (codes, colour, anchor, offset) in series.items():
        present = entered[entered["noc"].isin(codes)].groupby("year").size().reindex(years).notna()
        counts = summer[summer["noc"].isin(codes)].groupby("year").size().reindex(years, fill_value=0)
        share = (100 * counts / totals).where(present)
        ax.plot(years, share.values, color=colour, label=name, zorder=3)
        ax.annotate(name, xy=anchor, xytext=offset, textcoords="offset points",
                    color=colour, fontsize=10, fontweight="bold",
                    ha="center" if offset[0] == 0 else "left", va="bottom")

    for year, note, side, height in (
        (1980, "1980: the United States\nand 64 others stay home", "right", 2.0),
        (1984, "1984: the Soviet Union\nand 13 others stay home", "left", 6.0),
    ):
        offset = -1 if side == "right" else 1
        ax.annotate(note, xy=(year + offset, height), fontsize=9,
                    color=INK_FAINT, ha=side, va="center")
        ax.axvline(year, color=GRID, linewidth=1.2, zorder=1)

    ax.set_title("The Cold War podium, Summer Games 1952 to 1992")
    ax.set_xlim(1950, 1996)
    ax.set_ylim(0, 35)
    tidy(ax, "percent of medals at that Games")
    ax.legend(loc="upper left")
    caption(fig, SOURCE + " A gap in a line means the committee did not enter that Games."
                 " The Soviet line includes the 1992 Unified Team, and East Germany entered"
                 " separately only from 1968 to 1988.")
    fig.savefig(FIGURES / "bloc_shares.png")
    plt.close(fig)


def main() -> int:
    apply_style()
    FIGURES.mkdir(parents=True, exist_ok=True)

    medals = pd.read_parquet(PROCESSED / "medals.parquet")
    medals = medals[medals["ioc_recognised"] & (medals["status"] != "non_country")]
    athletes = pd.read_parquet(PROCESSED / "athletes.parquet")

    table = build_table(medals)
    table.to_csv(ROOT / "reports" / "concentration_by_games.csv", index=False)

    regimes = {}
    for season in ("Summer", "Winter"):
        _, described = detect_regimes(table, season)
        regimes[season] = described

    figure_regimes(table, regimes)
    figure_counterfactual(table)
    figure_top5(table)
    figure_blocs(medals, athletes)

    summer = table[table["season"] == "Summer"].set_index("year")
    plateau = summer.loc[1912:1992]
    modern = summer.loc[1996:2016]

    actual_rise = modern["effective_countries"].mean() - plateau["effective_countries"].mean()
    remerged_rise = modern["effective_countries_remerged"].mean() - plateau["effective_countries"].mean()

    report = {
        "medals_analysed": int(len(medals)),
        "summer_regimes": regimes["Summer"],
        "winter_regimes": regimes["Winter"],
        "summer_break_years": [regime["from_year"] for regime in regimes["Summer"][1:]],
        "winter_break_years": [regime["from_year"] for regime in regimes["Winter"][1:]],
        "plateau_mean_effective": round(float(plateau["effective_countries"].mean()), 1),
        "plateau_span_games": int(len(plateau)),
        "modern_mean_effective": round(float(modern["effective_countries"].mean()), 1),
        "modern_mean_effective_remerged": round(float(modern["effective_countries_remerged"].mean()), 1),
        "rise_actual": round(float(actual_rise), 1),
        "rise_after_remerging": round(float(remerged_rise), 1),
        "pct_of_rise_that_is_redefinition": round(100 * (1 - remerged_rise / actual_rise)),
        "st_louis_1904_leader_share": round(float(summer.loc[1904, "leader_share"]), 1),
        "st_louis_1904_effective": round(float(summer.loc[1904, "effective_countries"]), 1),
        "st_louis_1904_winners": int(summer.loc[1904, "winners"]),
        "moscow_1980_effective": round(float(summer.loc[1980, "effective_countries"]), 1),
        "moscow_1980_leader_share": round(float(summer.loc[1980, "leader_share"]), 1),
        "los_angeles_1984_effective": round(float(summer.loc[1984, "effective_countries"]), 1),
        "los_angeles_1984_leader_share": round(float(summer.loc[1984, "leader_share"]), 1),
        "top5_share_1896": round(float(summer.loc[1896, "top5_share"]), 1),
        "top5_share_2016": round(float(summer.loc[2016, "top5_share"]), 1),
        "winners_1896": int(summer.loc[1896, "winners"]),
        "winners_2016": int(summer.loc[2016, "winners"]),
        "figures": FIGURE_NAMES,
    }
    missing = [figure for figure in FIGURE_NAMES if not (FIGURES / figure).exists()]
    if missing:
        print(f"FAILED: figures not written: {missing}")
        return 1

    REPORT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")

    print(f"wrote reports/concentration_by_games.csv  rows={len(table)}")
    print(f"wrote docs/{REPORT.name}")
    print()
    print("  Summer regimes found by searching every split point:")
    for regime in regimes["Summer"]:
        print(f"    {regime['from_year']} to {regime['to_year']}"
              f"  {regime['mean_effective_countries']:>5} effective countries"
              f"  ({regime['games_count']} Games)")
    print()
    print(f"  rise from the plateau to the modern era   {report['rise_actual']}")
    print(f"  the same rise with successor states merged {report['rise_after_remerging']}")
    print(f"  so {report['pct_of_rise_that_is_redefinition']} percent of it is redefinition, not broadening")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
