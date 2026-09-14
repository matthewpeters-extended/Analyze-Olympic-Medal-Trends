"""Phase 2: participation trends.

Reads data/processed/athletes.parquet and writes

    docs/phase2_participation.json     every number, for the README check
    reports/participation_by_games.csv the full per Games table
    reports/figures/*.png              four figures

One grain trap to note before any of these numbers mean anything. The raw file has
271,116 rows but only 187,452 athlete by Games pairs, because an athlete entered in
four events appears four times. Counting rows would overstate participation and would
bias it towards whichever sports let one competitor enter many events. Everything here
counts distinct athletes within a Games.

Usage:
    python scripts/run_participation.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from plotstyle import AQUA, BLUE, GRID, INK_FAINT, INK_SOFT, ORANGE, apply_style, caption, label_end, tidy  # noqa: E402

PROCESSED = ROOT / "data" / "processed"
FIGURES = ROOT / "reports" / "figures"
REPORT = ROOT / "docs" / "phase2_participation.json"

# The figures this phase writes. Listed rather than globbed, so that a figure
# from another phase cannot wander into this phase's report.
FIGURE_NAMES = ['events_by_sex.png', 'female_share.png', 'nations_growth.png', 'participation_growth.png']

SOURCE = "Source: 271,116 Olympic athlete records, 1896 to 2016."


def build_table(athletes: pd.DataFrame) -> pd.DataFrame:
    """One row per Games, counting distinct athletes rather than event entries."""
    athletes = athletes.copy()
    athletes["event_sex"] = (
        athletes["event"].str.extract(r"(Women's|Men's|Mixed)", expand=False).fillna("Mixed")
    )

    rows = []
    for (games, year, season), sub in athletes.groupby(["games", "year", "season"]):
        people = sub.drop_duplicates("id")
        events = sub[["event", "event_sex"]].drop_duplicates()
        committees = sub[sub["status"] != "non_country"]
        rows.append({
            "games": games,
            "year": int(year),
            "season": season,
            "ioc_recognised": bool(sub["ioc_recognised"].all()),
            "athletes": len(people),
            "female": int((people["sex"] == "F").sum()),
            "male": int((people["sex"] == "M").sum()),
            "nations": committees["noc"].nunique(),
            "noc_codes": sub["noc"].nunique(),
            "sports": sub["sport"].nunique(),
            "events": len(events),
            "events_men": int((events["event_sex"] == "Men's").sum()),
            "events_women": int((events["event_sex"] == "Women's").sum()),
            "events_mixed": int((events["event_sex"] == "Mixed").sum()),
        })

    table = pd.DataFrame(rows).sort_values(["year", "season"]).reset_index(drop=True)
    table["female_share"] = 100 * table["female"] / table["athletes"]
    table["women_event_share"] = 100 * table["events_women"] / table["events"]
    return table


def figure_participation(table: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(9, 5))
    for season, colour in (("Summer", BLUE), ("Winter", ORANGE)):
        sub = table[table["season"] == season]
        ax.plot(sub["year"], sub["athletes"], color=colour, label=season, zorder=3)
        last = sub.iloc[-1]
        label_end(ax, last["year"], last["athletes"], season, colour)

    notes = (
        (1932, "Depression, and\nLos Angeles is far\nfrom everywhere", 1936, 3500),
        (1980, "Moscow boycott", 1988, 4300),
    )
    for year, note, text_x, text_y in notes:
        point = table[(table["year"] == year) & (table["season"] == "Summer")].iloc[0]
        ax.annotate(note, xy=(year, point["athletes"]), xytext=(text_x, text_y),
                    fontsize=9, color=INK_FAINT, ha="left", va="top",
                    arrowprops=dict(arrowstyle="-", color=GRID, linewidth=1.2))

    ax.set_title("Olympic participation, 1896 to 2016")
    ax.set_xlim(1890, 2030)
    ax.set_ylim(0, 12500)
    tidy(ax, "athletes at the Games")
    ax.legend(loc="upper left", bbox_to_anchor=(0.0, 0.95))
    caption(fig, SOURCE + " Athletes are counted once per Games, not once per event entry."
                 " No Games were held in 1916, 1940 or 1944.")
    fig.savefig(FIGURES / "participation_growth.png")
    plt.close(fig)


def figure_female_share(table: pd.DataFrame) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.8), sharey=True)
    for ax, season in zip(axes, ("Summer", "Winter")):
        sub = table[table["season"] == season]
        ax.axhline(50, color=GRID, linewidth=1.2, zorder=1)
        ax.annotate("parity", xy=(sub["year"].max(), 50), xytext=(sub["year"].max() + 1, 50),
                    fontsize=9, color=INK_FAINT, va="center", annotation_clip=False)
        ax.plot(sub["year"], sub["women_event_share"], color=ORANGE, label="share of events", zorder=2)
        ax.plot(sub["year"], sub["female_share"], color=BLUE, label="share of athletes", zorder=3)
        ax.set_title(season)
        ax.set_ylim(0, 58)
        ax.set_xlim(sub["year"].min() - 4, sub["year"].max() + 16)
        tidy(ax, "percent" if season == "Summer" else "")

    peak = table[table["season"] == "Winter"].set_index("year")
    axes[1].annotate(
        "1964: women were 35% of the\nprogramme but 18% of the field",
        xy=(1964, 35.3), xytext=(1966, 8), fontsize=9, color=INK_FAINT, ha="left",
        arrowprops=dict(arrowstyle="-", color=GRID, linewidth=1.2),
    )
    axes[0].legend(loc="upper left", bbox_to_anchor=(0.0, 1.0))
    fig.suptitle("The programme opened to women faster than the field filled",
                 x=0.005, ha="left", fontsize=13, fontweight="bold", y=1.04)
    caption(fig, SOURCE + " Both series count once per Games: distinct athletes, and distinct events on the programme.")
    fig.savefig(FIGURES / "female_share.png")
    plt.close(fig)


def figure_events_by_sex(table: pd.DataFrame) -> None:
    sub = table[(table["season"] == "Summer") & table["ioc_recognised"]]
    fig, ax = plt.subplots(figsize=(9, 5))
    bands = [
        ("events_men", "men's events", BLUE),
        ("events_women", "women's events", ORANGE),
        ("events_mixed", "mixed events", AQUA),
    ]
    ax.stackplot(
        sub["year"], *[sub[column] for column, _, _ in bands],
        colors=[colour for _, _, colour in bands],
        labels=[name for _, name, _ in bands],
        edgecolor="#fcfcfb", linewidth=1.5,
    )
    bottom = 0
    for column, name, colour in bands:
        last = sub.iloc[-1]
        ax.annotate(f"{name}  {int(last[column])}", xy=(last["year"] + 2, bottom + last[column] / 2),
                    color=colour, fontsize=10, fontweight="bold", va="center", annotation_clip=False)
        bottom += last[column]

    ax.set_title("Summer Olympic events by category")
    ax.set_xlim(1896, 2016)
    ax.set_ylim(0, 320)
    tidy(ax, "events on the programme")
    ax.legend(loc="upper left")
    caption(fig, SOURCE + " Events counted once per Games."
                 " The 1906 Intercalated Games are excluded, the IOC does not recognise them.")
    fig.savefig(FIGURES / "events_by_sex.png")
    plt.close(fig)


def figure_nations(table: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(9, 5))
    for season, colour in (("Summer", BLUE), ("Winter", ORANGE)):
        sub = table[table["season"] == season]
        ax.plot(sub["year"], sub["nations"], color=colour, label=season, zorder=3)
        last = sub.iloc[-1]
        label_end(ax, last["year"], last["nations"], season, colour)

    for year, note, shift in ((1976, "African boycott", 34), (1980, "United States\nled boycott", -30)):
        point = table[(table["year"] == year) & (table["season"] == "Summer")].iloc[0]
        ax.annotate(note, xy=(year, point["nations"]), xytext=(year - 12, point["nations"] + shift),
                    fontsize=9, color=INK_FAINT, ha="center",
                    arrowprops=dict(arrowstyle="-", color=GRID, linewidth=1.2))

    ax.set_title("National Olympic Committees represented")
    ax.set_xlim(1890, 2030)
    ax.set_ylim(0, 230)
    tidy(ax, "committees sending athletes")
    ax.legend(loc="upper left")
    caption(fig, SOURCE + " Neutral and refugee teams are excluded, they are not countries.")
    fig.savefig(FIGURES / "nations_growth.png")
    plt.close(fig)


def main() -> int:
    apply_style()
    FIGURES.mkdir(parents=True, exist_ok=True)

    athletes = pd.read_parquet(PROCESSED / "athletes.parquet")
    table = build_table(athletes)
    table.to_csv(ROOT / "reports" / "participation_by_games.csv", index=False)

    figure_participation(table)
    figure_female_share(table)
    figure_events_by_sex(table)
    figure_nations(table)

    summer = table[table["season"] == "Summer"].set_index("year")
    winter = table[table["season"] == "Winter"].set_index("year")

    report = {
        "raw_rows": int(len(athletes)),
        "athlete_games_pairs": int(athletes.groupby(["games", "id"]).ngroups),
        "row_to_athlete_inflation": round(len(athletes) / athletes.groupby(["games", "id"]).ngroups, 2),
        "summer_athletes_1896": int(summer.loc[1896, "athletes"]),
        "summer_athletes_2016": int(summer.loc[2016, "athletes"]),
        "summer_athlete_growth_factor": round(summer.loc[2016, "athletes"] / summer.loc[1896, "athletes"], 1),
        "summer_nations_1896": int(summer.loc[1896, "nations"]),
        "summer_nations_2016": int(summer.loc[2016, "nations"]),
        "summer_events_1896": int(summer.loc[1896, "events"]),
        "summer_events_2016": int(summer.loc[2016, "events"]),
        "female_share_summer": {
            str(year): round(float(summer.loc[year, "female_share"]), 1)
            for year in (1896, 1900, 1936, 1976, 1996, 2016)
        },
        "female_share_winter_first": round(float(winter["female_share"].iloc[0]), 1),
        "female_share_winter_last": round(float(winter["female_share"].iloc[-1]), 1),
        "women_event_share_summer_2016": round(float(summer.loc[2016, "women_event_share"]), 1),
        "female_share_summer_2016": round(float(summer.loc[2016, "female_share"]), 1),
        "share_gap_summer_2016": round(
            float(summer.loc[2016, "female_share"] - summer.loc[2016, "women_event_share"]), 1
        ),
        "first_games_with_women": str(table.loc[table["female"] > 0, "games"].iloc[0]),
        "winter_peak_share_gap_pp": round(float(
            (winter["women_event_share"] - winter["female_share"]).max()
        ), 1),
        "winter_peak_share_gap_year": int(
            (winter["women_event_share"] - winter["female_share"]).idxmax()
        ),
        "winter_mean_share_gap_1960_1992_pp": round(float(
            (winter["women_event_share"] - winter["female_share"]).loc[1960:1992].mean()
        ), 1),
        "summer_mean_share_gap_1960_1992_pp": round(float(
            (summer["women_event_share"] - summer["female_share"]).loc[1960:1992].mean()
        ), 1),
        "games_to_reach_25pct_female_summer": int(
            summer[summer["female_share"] >= 25].index.min()
        ),
        "nations_1976_summer": int(summer.loc[1976, "nations"]),
        "nations_1980_summer": int(summer.loc[1980, "nations"]),
        "nations_1984_summer": int(summer.loc[1984, "nations"]),
        "nations_1972_summer": int(summer.loc[1972, "nations"]),
        "summer_games_count": int((table["season"] == "Summer").sum()),
        "winter_games_count": int((table["season"] == "Winter").sum()),
        "figures": FIGURE_NAMES,
    }

    missing = [figure for figure in FIGURE_NAMES if not (FIGURES / figure).exists()]
    if missing:
        print(f"FAILED: figures not written: {missing}")
        return 1

    REPORT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")

    print(f"wrote reports/participation_by_games.csv  rows={len(table)}")
    for name in report["figures"]:
        print(f"wrote reports/figures/{name}")
    print(f"wrote docs/{REPORT.name}")
    print()
    print(f"  Summer athletes   {report['summer_athletes_1896']} in 1896 "
          f"-> {report['summer_athletes_2016']:,} in 2016 "
          f"({report['summer_athlete_growth_factor']} times)")
    print(f"  Summer nations    {report['summer_nations_1896']} -> {report['summer_nations_2016']}")
    print(f"  Female share      {report['female_share_summer']['1900']}% in 1900 "
          f"-> {report['female_share_summer']['2016']}% in 2016")
    print(f"  Women's events    {report['women_event_share_summer_2016']}% of the 2016 programme")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
