# Olympic Medal Trends: Plan

Status: planning complete, Phase 0 scaffold in place. Written 2026 09 14.

## Objective

Use 120 years of Olympic athlete records to answer four questions that the usual public
notebook on this dataset does not answer correctly:

1. How has participation changed, and in particular how has the share of women changed?
2. How concentrated are medals among a small set of countries, and when did that change?
3. Does hosting the Games measurably raise a country's medal share, and by how much?
4. Can next Games medal share be predicted better than simply repeating the last Games?

Question 3 is the centerpiece. Question 4 exists to force an honest baseline comparison.

## Dataset

One file. No account, no API key, no scraping.

<table>
<tr><td>Source</td><td>TidyTuesday archive, 2021 week 31, mirroring the Kaggle dataset "120 years of Olympic history: athletes and results" by Randi H Griffin</td></tr>
<tr><td>URL</td><td>https://raw.githubusercontent.com/rfordatascience/tidytuesday/master/data/2021/2021-07-27/olympics.csv</td></tr>
<tr><td>sha256</td><td>227cb326b8ff4e53819bfe1b6682687713eeb496391be572d74de588c7fa3e69</td></tr>
<tr><td>Size</td><td>35,911,926 bytes</td></tr>
<tr><td>Grain</td><td>one row per athlete per event entry</td></tr>
<tr><td>Rows</td><td>271,116</td></tr>
<tr><td>Coverage</td><td>1896 to 2016, 51 Games, 222,552 Summer rows and 48,564 Winter rows</td></tr>
<tr><td>Entities</td><td>135,571 unique athletes, 230 NOC codes, 66 sports, 765 events</td></tr>
<tr><td>Columns</td><td>id, name, sex, age, height, weight, team, noc, games, year, season, city, sport, event, medal</td></tr>
</table>

The Kaggle companion file `noc_regions.csv` is not mirrored publicly. We build the country
mapping ourselves instead, which is the better artifact because the decision rules end up
documented rather than inherited.

Attribution: the underlying records were scraped from sports reference dot com by Randi H
Griffin and published on Kaggle. This project uses the TidyTuesday mirror of that file.

## Defects we inherit and fix

Every item below was measured on the raw file before this plan was written.

### 1. Team medals are counted once per athlete

A team gold appears as one row per squad member. At athlete grain there are 39,783 medal
rows; collapsed to the true grain of (games, event, medal, noc) there are 18,905. Public
notebooks on this dataset routinely report the inflated figure and call it a medal table.

Fix: build `data/processed/medals.parquet` at the event grain, and state both numbers in
the README so the difference is visible rather than hidden.

### 2. The 1906 Intercalated Games are present

1,733 rows carry year 1906. The IOC does not recognise those Games. Fix: flag with an
`ioc_recognised` boolean, exclude from headline tables, and report the sensitivity.

### 3. Art Competitions are present

3,578 rows and 156 medals between 1912 and 1948. The IOC removed these from official
medal counts. Fix: same treatment as 1906, flagged rather than silently dropped.

### 4. Country identity is not stable across time

URS 5,685 rows, GDR 2,645, FRG 3,315, EUN 864, plus Czechoslovakia, Yugoslavia, Serbia and
Montenegro, and the mixed teams of the early Games. Any country trend line is meaningless
until this is resolved. Fix: hand written `data/raw/noc_country_map.csv` with one row per
NOC code, a modern country assignment, a successor rule, and a free text justification.
The default rule is continuity of the National Olympic Committee, not of the state, and
where the two disagree the analysis reports both.

### 5. Missingness concentrated in the early Games

Height missing in 22.2 percent of rows, weight in 23.2 percent, age in 3.5 percent, and
the missingness is not random across time. Fix: any body composition analysis reports
coverage per Games alongside the statistic, and no imputation happens without saying so.

## Phases

Each phase writes a machine readable `docs/phaseN_*.json`. The README is assembled from
those files at the end, and `scripts/verify_readme.py` asserts that every headline number
in the README appears in the JSON that produced it.

### Phase 0: scaffold

Folder layout, Python 3.12 virtual environment, `requirements.txt` plus a `pip freeze`
lock, `scripts/download_data.py` which is idempotent and verifies the checksum, `data/`
excluded from git, `scripts/check_prose.py` and `scripts/verify_readme.py` and
`scripts/push.sh` copied from `fraud-email-classification`.

### Phase 1: clean and map

Apply the five fixes above. Outputs: `data/processed/athletes.parquet` at athlete grain,
`data/processed/medals.parquet` at event grain, `data/raw/noc_country_map.csv`.
Writes `docs/phase1_cleaning.json` with every row count before and after each fix.
Tests in `tests/` assert the grain of each output and that no medal is double counted.

### Phase 2: participation trends

Athletes per Games, countries per Games, sports and events per Games, and the female share
of athletes over time. The headline series measured on the raw file: female share of Summer
athletes is 1.7 percent in 1900, 7.2 percent in 1936, 25.1 percent in 1976, 36.3 percent in
1996, and 45.5 percent in 2016. Summer and Winter are reported separately throughout,
because the two calendars diverge after 1992.
Figures: participation growth, female share over time, events per Games.

### Phase 3: medal concentration

Top 5 share of medals per Games and a Herfindahl Hirschman Index per Games, computed on the
event grain table. Expected structure: the Cold War bloc era, the 1980 and 1984 boycotts,
and the post 1992 fragmentation as the Soviet successor states enter separately. These are
treated as structural breaks to be located in the data, not as anecdotes to illustrate.
Figures: concentration over time with the boycott years annotated.

### Phase 4: host advantage

For each host country, compare its medal share in the Games it hosted against its own mean
share across the two preceding and two following Games. This gives one estimate per hosting
event and a distribution across all of them. Report the median lift, the spread, and the
cases that go the wrong way. Separate Summer from Winter. Discuss what this design cannot
rule out, namely that countries bid to host when they are already on an upswing.
Figures: per host lift, ordered, with the pooled estimate marked.

### Phase 5: forecast with an honest baseline

Target: a country's share of medals at a given Games. Panel of country by Games.
Split by time, train through 2008, test on 2012 and 2016. Nothing from the test period
touches fitting.

<table>
<tr><td>Baseline</td><td>persistence, meaning the previous Games share carries forward unchanged</td></tr>
<tr><td>Features</td><td>lagged medal shares, athletes sent, events contested, breadth of sports entered, host flag, Games index</td></tr>
<tr><td>Models</td><td>ridge regression, then gradient boosting</td></tr>
<tr><td>Metric</td><td>mean absolute error on medal share, reported next to the baseline in the same sentence</td></tr>
</table>

Rule: if the model does not beat persistence, the README says so in the headline, and the
project reports that as the finding. A holdout ledger appends a configuration fingerprint
on every test set evaluation, and a test asserts the count of distinct configurations, so
the "scored once" claim is checkable rather than merely stated.

### Phase 6: write up

README written last, from measured numbers only, never placeholders. WALKTHROUGH covers the
reasoning and the dead ends. Figures are tracked in git, not ignored, because the README
embeds them and an untracked image renders as a broken link on GitHub.
`scripts/check_prose.py` enforces zero dash characters in the prose of both documents.

## Out of scope

* Medals per capita or per unit of GDP. That needs a second data source and a second set of
  join defects. If it happens it is a follow up project.
* Anything after 2016. The file ends there.
* Individual athlete career analysis. Interesting, but it is a different project.

## Environment

<table>
<tr><td>Python</td><td>/opt/homebrew/opt/python@3.12/bin/python3.12, version 3.12.14</td></tr>
<tr><td>Virtual environment</td><td>.venv in the project root</td></tr>
<tr><td>Packages</td><td>pandas, numpy, pyarrow, matplotlib, seaborn, scikit learn, jupyter, pytest</td></tr>
<tr><td>Remote</td><td>GitHub under `matthewpeters-extended`. The gh CLI is not installed on this laptop, so the empty repository is created in the browser and the remote is added by hand.</td></tr>
</table>
