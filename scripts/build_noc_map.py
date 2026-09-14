"""Build the NOC reference tables.

Two files land in reference/, which is tracked in git because they are hand made
decisions rather than downloaded data:

  reference/noc_country_map.csv   one row per NOC code seen in the raw data
  reference/host_nations.csv      one row per Games, the host NOC

The Kaggle companion file noc_regions.csv is not mirrored publicly, so this project
builds its own mapping. That turns out to be an advantage: every judgement call below
is written down next to the row it affects, which noc_regions.csv does not do.

Columns in noc_country_map.csv
-----------------------------
noc            three letter code exactly as it appears in the raw data
entity_name    the name the team competed under
status         active | dissolved | non_country
rollup_noc     the code to group by for a "modern country" view of the data
note           why, for every row where the answer is not the identity

Two views of the same data fall out of this:

  by noc          what the IOC does. Soviet Union, East Germany and Germany are three
                  separate competitors. This is the default for every medal table here.
  by rollup_noc   territory based. Bohemia becomes Czech Republic, Rhodesia becomes
                  Zimbabwe, the two Germanys become Germany.

Neither view is correct in the abstract. They answer different questions, so the
analysis reports which one it used every time.

Usage:
    python scripts/build_noc_map.py
"""

from __future__ import annotations

import csv
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "olympics.csv"
REFERENCE = ROOT / "reference"

# noc -> (status, rollup_noc, note)
#
# Anything not listed here is status "active", rolls up to itself, and needs no note.
OVERRIDES: dict[str, tuple[str, str, str]] = {
    # States that dissolved into several successors. No single successor exists, so the
    # entity keeps its own identity in both views. Splitting the medals between the
    # successor states would require knowing each athlete's home republic, which this
    # data does not record.
    "URS": ("dissolved", "URS", "Soviet Union, 1952 to 1988. Dissolved into 15 states in 1991. Kept whole."),
    "TCH": ("dissolved", "TCH", "Czechoslovakia, 1920 to 1992. Split into Czech Republic and Slovakia in 1993. Kept whole."),
    "YUG": ("dissolved", "YUG", "Yugoslavia, 1920 to 1992. Split into six states. Kept whole."),
    "ANZ": ("dissolved", "ANZ", "Australasia, a joint Australia and New Zealand team in 1908 and 1912. Kept whole."),
    "WIF": ("dissolved", "WIF", "West Indies Federation, a joint Jamaica, Trinidad and Barbados team in 1960. Kept whole."),
    "AHO": ("dissolved", "AHO", "Netherlands Antilles, dissolved 2010. Athletes went to the Netherlands or to new committees. Kept whole."),

    # Post Soviet transition. The Unified Team of 1992 is the Soviet Union minus the
    # Baltic states, competing once under a neutral flag. Rolling it up with URS keeps
    # the bloc's decline readable as one series instead of two truncated ones.
    "EUN": ("dissolved", "URS", "Unified Team, 1992 only, twelve post Soviet republics. Rolls up to the Soviet Union."),

    # Germany. The IOC counts four German entities. This data carries three, because the
    # United Team of Germany of 1956 to 1964, IOC code EUA, is folded into GER upstream.
    "GDR": ("dissolved", "GER", "East Germany, 1968 to 1988. Reunified into Germany in 1990."),
    "FRG": ("dissolved", "GER", "West Germany, 1968 to 1988. Became the unified Germany in 1990."),
    "SAA": ("dissolved", "GER", "Saar, 1952 only. Joined West Germany in 1957."),
    "GER": ("active", "GER", "Germany. Note this code also carries the 1956 to 1964 United Team of Germany, which the IOC codes separately as EUA."),

    # Single clear successors.
    "SCG": ("dissolved", "SRB", "Serbia and Montenegro, 1996 to 2006. The IOC treats Serbia as the successor committee."),
    "BOH": ("dissolved", "CZE", "Bohemia, 1900 to 1912, then part of Austria Hungary. The territory is now the Czech Republic."),
    "CRT": ("dissolved", "GRE", "Crete, 1906 only. United with Greece in 1913."),
    "UAR": ("dissolved", "EGY", "United Arab Republic, 1960 only, the Egypt and Syria union. The IOC assigns the record to Egypt."),
    "MAL": ("dissolved", "MAS", "Malaya, 1956 and 1960. Became part of Malaysia in 1963."),
    "NBO": ("dissolved", "MAS", "North Borneo, 1956 only. Became part of Malaysia in 1963."),
    "NFL": ("dissolved", "CAN", "Newfoundland, 1904 only. Joined Canada in 1949."),
    "RHO": ("dissolved", "ZIM", "Rhodesia, 1960. Became Zimbabwe in 1980."),
    "VNM": ("dissolved", "VIE", "South Vietnam, 1952 to 1972. Absorbed into Vietnam in 1976."),
    "YAR": ("dissolved", "YEM", "North Yemen, 1984 and 1988. Merged into Yemen in 1990."),
    "YMD": ("dissolved", "YEM", "South Yemen, 1988 only. Merged into Yemen in 1990."),

    # Not countries. These must never appear in a medal table by country.
    "IOA": ("non_country", "IOA", "Individual Olympic Athletes, competing without a national committee."),
    "ROT": ("non_country", "ROT", "Refugee Olympic Athletes, 2016 only."),
    "UNK": ("non_country", "UNK", "Unknown, two rows in 1912 with no committee recorded."),

    # Active codes that still carry a caveat worth recording.
    "RUS": ("active", "RUS", "Russia. The 1900 to 1912 rows are the Russian Empire, a different polity from the modern federation, and this code spans both."),
    "SRB": ("active", "SRB", "Serbia. The 1912 rows are the Kingdom of Serbia."),
    "KUW": ("active", "KUW", "Kuwait. The committee was suspended for 2016, so its athletes appear that year under IOA."),
    "HKG": ("active", "HKG", "Hong Kong. Keeps its own committee after the 1997 handover, so it is never folded into China."),
    "TPE": ("active", "TPE", "Chinese Taipei, the committee representing Taiwan."),
}

# games -> host noc, as that code appears in this dataset.
HOSTS: dict[str, str] = {
    "1896 Summer": "GRE", "1900 Summer": "FRA", "1904 Summer": "USA",
    "1906 Summer": "GRE", "1908 Summer": "GBR", "1912 Summer": "SWE",
    "1920 Summer": "BEL", "1924 Summer": "FRA", "1924 Winter": "FRA",
    "1928 Summer": "NED", "1928 Winter": "SUI", "1932 Summer": "USA",
    "1932 Winter": "USA", "1936 Summer": "GER", "1936 Winter": "GER",
    "1948 Summer": "GBR", "1948 Winter": "SUI", "1952 Summer": "FIN",
    "1952 Winter": "NOR", "1956 Summer": "AUS", "1956 Winter": "ITA",
    "1960 Summer": "ITA", "1960 Winter": "USA", "1964 Summer": "JPN",
    "1964 Winter": "AUT", "1968 Summer": "MEX", "1968 Winter": "FRA",
    "1972 Summer": "FRG", "1972 Winter": "JPN", "1976 Summer": "CAN",
    "1976 Winter": "AUT", "1980 Summer": "URS", "1980 Winter": "USA",
    "1984 Summer": "USA", "1984 Winter": "YUG", "1988 Summer": "KOR",
    "1988 Winter": "CAN", "1992 Summer": "ESP", "1992 Winter": "FRA",
    "1994 Winter": "NOR", "1996 Summer": "USA", "1998 Winter": "JPN",
    "2000 Summer": "AUS", "2002 Winter": "USA", "2004 Summer": "GRE",
    "2006 Winter": "ITA", "2008 Summer": "CHN", "2010 Winter": "CAN",
    "2012 Summer": "GBR", "2014 Winter": "RUS", "2016 Summer": "BRA",
}

HOST_NOTES: dict[str, str] = {
    "1956 Summer": "Two host cities. Australian quarantine law kept the horses out, so the equestrian events ran in Stockholm five months earlier. Australia is the host of record.",
    "1972 Summer": "Munich was in West Germany, so the host code is FRG and not GER.",
    "1980 Winter": "Lake Placid, the same year Moscow hosted the Summer Games that the United States boycotted.",
    "1984 Winter": "Sarajevo, then Yugoslavia.",
    "1906 Summer": "The Intercalated Games, which the IOC does not recognise. Included here for completeness and excluded from headline tables.",
}


def main() -> int:
    df = pd.read_csv(RAW, usecols=["noc", "team", "games", "year", "season", "city"])
    REFERENCE.mkdir(exist_ok=True)

    # The team column is the best available name for a committee. For a handful of
    # sports it holds a boat or crew name, so take the most common value per code
    # after stripping the "-2" suffix the source appends to duplicate team entries.
    names = (
        df.assign(team=df["team"].str.replace(r"-\d+$", "", regex=True))
        .groupby("noc")["team"]
        .agg(lambda s: s.mode().iloc[0])
    )

    unmatched = sorted(set(OVERRIDES) - set(names.index))
    if unmatched:
        print(f"FAILED: overrides for codes not in the data: {unmatched}")
        return 1

    path = REFERENCE / "noc_country_map.csv"
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["noc", "entity_name", "status", "rollup_noc", "note"])
        for noc in sorted(names.index):
            status, rollup, note = OVERRIDES.get(noc, ("active", noc, ""))
            writer.writerow([noc, names[noc], status, rollup, note])
    print(f"wrote {path.relative_to(ROOT)}  rows={len(names)}")

    games = df[["games", "year", "season"]].drop_duplicates().sort_values(["year", "season"])
    missing = sorted(set(games["games"]) - set(HOSTS))
    if missing:
        print(f"FAILED: no host recorded for {missing}")
        return 1

    cities = df.groupby("games")["city"].agg(lambda s: ", ".join(sorted(s.unique())))
    path = REFERENCE / "host_nations.csv"
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["games", "year", "season", "city", "host_noc", "note"])
        for _, row in games.iterrows():
            writer.writerow([
                row["games"], row["year"], row["season"], cities[row["games"]],
                HOSTS[row["games"]], HOST_NOTES.get(row["games"], ""),
            ])
    print(f"wrote {path.relative_to(ROOT)}  rows={len(games)}")

    counts = {}
    for noc in names.index:
        status = OVERRIDES.get(noc, ("active", noc, ""))[0]
        counts[status] = counts.get(status, 0) + 1
    print(f"status counts: {counts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
