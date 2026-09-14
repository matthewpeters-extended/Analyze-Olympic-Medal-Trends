"""Phase 4: does hosting raise a country's medal share, and by how much.

Reads data/processed/medals.parquet and reference/host_nations.csv, writes

    docs/phase4_host_advantage.json   every number, for the README check
    reports/host_advantage.csv        one row per hosting event, full ledger
    reports/figures/*.png             two figures

Design
------
For each hosting event, compare the host's medal share at that Games against the
host's own mean share across up to two preceding and two following Games, counting
only Games where that same committee actually competed. This is a within country
design on purpose: it compares Norway hosting to Norway not hosting, never to some
other country, so it cannot be confounded by which countries tend to be good at the
Olympics in general.

What it cannot rule out is the reverse. Countries do not host at random. A country
often bids for and wins a Games during a period of rising investment in sport, so
some of the measured lift may be a cause of hosting rather than an effect of it.
This design reports a lift, not a causal estimate, and that limit is discussed in
PLAN.md and the README.

A hosting event is marked "clean" when at least one Games on each side is
available. Five of the fifty are edge cases, mostly the first and last Games in
each season's history, where the baseline can only look one direction. They are
kept in the ledger and excluded from the headline statistics.

Usage:
    python scripts/run_host_advantage.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from plotstyle import AQUA, BLUE, GRID, INK_FAINT, INK_SOFT, ORANGE, apply_style, caption, tidy  # noqa: E402

PROCESSED = ROOT / "data" / "processed"
FIGURES = ROOT / "reports" / "figures"
REPORT = ROOT / "docs" / "phase4_host_advantage.json"
FIGURE_NAMES = ["host_lift_ordered.png", "host_era_comparison.png"]

SOURCE = "Source: 18,952 Olympic medals, counted once each, 1896 to 2016."
WINDOW = 2
MODERN_FROM = 1950


def medal_shares(medals: pd.DataFrame, season: str) -> dict[str, tuple[int, pd.Series]]:
    sub = medals[medals["season"] == season]
    out: dict[str, tuple[int, pd.Series]] = {}
    for (games, year), rows in sub.groupby(["games", "year"]):
        counts = rows["noc"].value_counts()
        out[games] = (int(year), counts / counts.sum())
    return out


def build_ledger(medals: pd.DataFrame, hosts: pd.DataFrame) -> pd.DataFrame:
    host_noc = hosts.set_index("games")["host_noc"]
    records = []

    for season in ("Summer", "Winter"):
        shares = medal_shares(medals, season)
        order = sorted(shares, key=lambda games: shares[games][0])

        for index, games in enumerate(order):
            year, share = shares[games]
            host = host_noc.get(games)
            if host is None or host not in share.index:
                continue

            def neighbours(step: int) -> list[float]:
                found = []
                cursor = index + step
                while 0 <= cursor < len(order) and len(found) < WINDOW:
                    other_share = shares[order[cursor]][1]
                    if host in other_share.index:
                        found.append(float(other_share[host]))
                    cursor += step
                return found

            before = neighbours(-1)
            after = neighbours(1)
            if not before and not after:
                continue

            baseline = float(np.mean(before + after))
            records.append({
                "games": games,
                "year": year,
                "season": season,
                "host": host,
                "host_share_pct": round(100 * float(share[host]), 2),
                "baseline_share_pct": round(100 * baseline, 2),
                "lift_pp": round(100 * (float(share[host]) - baseline), 2),
                "n_before": len(before),
                "n_after": len(after),
                "clean": len(before) >= 1 and len(after) >= 1,
                "era": "modern" if year >= MODERN_FROM else "early",
            })

    return pd.DataFrame(records).sort_values(["season", "year"]).reset_index(drop=True)


def bootstrap_median_ci(values: np.ndarray, iterations: int = 20_000, seed: int = 0) -> tuple[float, float]:
    rng = np.random.RandomState(seed)
    n = len(values)
    medians = [np.median(rng.choice(values, size=n, replace=True)) for _ in range(iterations)]
    lo, hi = np.percentile(medians, [2.5, 97.5])
    return round(float(lo), 1), round(float(hi), 1)


def figure_ordered_lift(ledger: pd.DataFrame) -> None:
    clean = ledger[ledger["clean"]].sort_values("lift_pp").reset_index(drop=True)
    fig, ax = plt.subplots(figsize=(9, 0.185 * len(clean) + 1.0))

    colours = clean["season"].map({"Summer": BLUE, "Winter": ORANGE})
    y = np.arange(len(clean))
    ax.hlines(y, 0, clean["lift_pp"], color=colours, linewidth=2, zorder=3)
    ax.scatter(clean["lift_pp"], y, color=colours, s=14, zorder=4)

    labels = clean["host"] + "  " + clean["year"].astype(str)
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=8)
    ax.tick_params(axis="y", length=0)
    ax.set_ylim(-0.7, len(clean) - 0.3)

    median = clean["lift_pp"].median()
    ax.axvline(0, color=INK_SOFT, linewidth=1.0, zorder=2)
    ax.axvline(median, color=INK_FAINT, linewidth=1.4, linestyle=(0, (4, 3)), zorder=2)
    ax.annotate(f"median  +{median:.1f}pp", xy=(median, 3),
                xytext=(6, 0), textcoords="offset points", fontsize=9,
                color=INK_FAINT, va="center")

    # A symmetric log scale keeps the three big outliers (early Games with a tiny
    # or war thinned field) from crushing the other 42 points into a sliver near
    # zero, while still showing zero and negative values without distortion.
    ax.set_xscale("symlog", linthresh=5, linscale=1.0)
    ax.set_xlim(-6, 80)
    ax.set_xticks([-5, 0, 5, 10, 20, 40, 70])
    ax.xaxis.set_major_formatter(lambda value, _: f"{value:g}")

    ax.set_title("Host advantage, every hosting event since 1896")
    ax.set_xlabel("medal share at that Games, minus the host's own share in neighbouring Games (points, symlog scale)")
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for spine in ("top", "right", "left"):
        ax.spines[spine].set_visible(False)

    handles = [
        plt.Line2D([0], [0], color=BLUE, linewidth=2, label="Summer"),
        plt.Line2D([0], [0], color=ORANGE, linewidth=2, label="Winter"),
    ]
    ax.legend(handles=handles, loc="lower right", frameon=False)
    caption(fig, SOURCE + " Lift is a host's medal share at its own Games minus its mean share "
                 "in up to two Games before and two after, counting only Games it competed in. "
                 "Five hosting events with a baseline on one side only are excluded here; "
                 "see reports/host_advantage.csv for the full ledger.")
    fig.subplots_adjust(top=0.97, bottom=0.09)
    fig.savefig(FIGURES / "host_lift_ordered.png")
    plt.close(fig)


def figure_era_comparison(ledger: pd.DataFrame) -> None:
    clean = ledger[ledger["clean"]]
    fig, ax = plt.subplots(figsize=(9, 4.6))

    eras = [("early", f"before {MODERN_FROM}", 0, BLUE), ("modern", f"{MODERN_FROM} to 2016", 1, ORANGE)]
    rng = np.random.RandomState(0)
    for key, label, position, colour in eras:
        values = clean.loc[clean["era"] == key, "lift_pp"]
        jitter = rng.uniform(-0.16, 0.16, size=len(values))
        ax.scatter(np.full(len(values), position) + jitter, values, color=colour,
                   s=26, alpha=0.75, zorder=3, edgecolor="#fcfcfb", linewidth=0.6)
        median = values.median()
        ax.hlines(median, position - 0.24, position + 0.24, color=colour, linewidth=2.4, zorder=4)
        ax.annotate(f"median +{median:.1f}pp\nn={len(values)}", xy=(position, values.max()),
                    xytext=(0, 8), textcoords="offset points", ha="center", fontsize=9,
                    color=colour, fontweight="bold")

    ax.axhline(0, color=INK_SOFT, linewidth=1.0, zorder=1)
    ax.set_xlim(-0.6, 1.6)
    ax.set_xticks([0, 1])
    ax.set_xticklabels([f"before {MODERN_FROM}", f"{MODERN_FROM} to 2016"])
    ax.set_title("The lift is smaller and steadier once the Games professionalised")
    tidy(ax, "lift at hosting, in points of medal share", grid=False)
    ax.yaxis.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    caption(fig, SOURCE + f" Each point is one hosting event. The pre {MODERN_FROM} era mixes tiny, "
                 "regionally travelled early fields with the outlier of Games where wartime and "
                 "Depression era travel costs left the host facing almost no one.")
    fig.savefig(FIGURES / "host_era_comparison.png")
    plt.close(fig)


def main() -> int:
    apply_style()
    FIGURES.mkdir(parents=True, exist_ok=True)

    medals = pd.read_parquet(PROCESSED / "medals.parquet")
    medals = medals[medals["ioc_recognised"] & (medals["status"] != "non_country")]
    hosts = pd.read_csv(ROOT / "reference" / "host_nations.csv")

    ledger = build_ledger(medals, hosts)
    ledger.to_csv(ROOT / "reports" / "host_advantage.csv", index=False)

    figure_ordered_lift(ledger)
    figure_era_comparison(ledger)

    clean = ledger[ledger["clean"]]
    modern = clean[clean["era"] == "modern"]
    early = clean[clean["era"] == "early"]
    negative = clean[clean["lift_pp"] < 0]

    lift_lo, lift_hi = bootstrap_median_ci(clean["lift_pp"].to_numpy())
    modern_lo, modern_hi = bootstrap_median_ci(modern["lift_pp"].to_numpy())
    wilcoxon_all = stats.wilcoxon(clean["lift_pp"])
    wilcoxon_modern = stats.wilcoxon(modern["lift_pp"])

    report = {
        "hosting_events_total": int(len(ledger)),
        "hosting_events_clean": int(len(clean)),
        "hosting_events_edge_case": int((~ledger["clean"]).sum()),
        "median_lift_pp": round(float(clean["lift_pp"].median()), 1),
        "mean_lift_pp": round(float(clean["lift_pp"].mean()), 1),
        "std_lift_pp": round(float(clean["lift_pp"].std()), 1),
        "median_lift_ci95": [lift_lo, lift_hi],
        "wilcoxon_p_value": float(wilcoxon_all.pvalue),
        "negative_lift_count": int(len(negative)),
        "negative_lift_events": negative[["games", "host", "lift_pp"]].to_dict("records"),
        "median_lift_by_season": {
            season: round(float(clean.loc[clean["season"] == season, "lift_pp"].median()), 1)
            for season in ("Summer", "Winter")
        },
        "median_lift_early": round(float(early["lift_pp"].median()), 1),
        "median_lift_modern": round(float(modern["lift_pp"].median()), 1),
        "median_lift_modern_ci95": [modern_lo, modern_hi],
        "wilcoxon_p_value_modern": float(wilcoxon_modern.pvalue),
        "modern_negative_lift_count": int((modern["lift_pp"] < 0).sum()),
        "modern_events": int(len(modern)),
        "extreme_case": {
            "games": "1904 Summer", "host": "USA",
            "lift_pp": round(float(ledger.loc[ledger["games"] == "1904 Summer", "lift_pp"].iloc[0]), 1),
            "note": "almost no international field travelled to St Louis; see the concentration figures in Phase 3",
        },
        "figures": FIGURE_NAMES,
    }

    missing = [figure for figure in FIGURE_NAMES if not (FIGURES / figure).exists()]
    if missing:
        print(f"FAILED: figures not written: {missing}")
        return 1

    REPORT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")

    print(f"wrote reports/host_advantage.csv  rows={len(ledger)}")
    print(f"wrote docs/{REPORT.name}")
    print()
    print(f"  clean hosting events        {report['hosting_events_clean']} of {report['hosting_events_total']}")
    print(f"  median lift                 +{report['median_lift_pp']}pp"
          f"  95% CI [{lift_lo}, {lift_hi}]  p={report['wilcoxon_p_value']:.2e}")
    print(f"  negative lift                {report['negative_lift_count']} of {report['hosting_events_clean']}")
    print(f"  median lift, {MODERN_FROM} to 2016    +{report['median_lift_modern']}pp"
          f"  95% CI [{modern_lo}, {modern_hi}]  p={report['wilcoxon_p_value_modern']:.2e}"
          f"  (n={report['modern_events']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
