# Sources

## Primary data

<table>
<tr><td>File</td><td><code>data/raw/olympics.csv</code></td></tr>
<tr><td>URL</td><td>https://raw.githubusercontent.com/rfordatascience/tidytuesday/master/data/2021/2021-07-27/olympics.csv</td></tr>
<tr><td>sha256</td><td><code>227cb326b8ff4e53819bfe1b6682687713eeb496391be572d74de588c7fa3e69</code></td></tr>
<tr><td>Bytes</td><td>35,911,926</td></tr>
<tr><td>Retrieved</td><td>2026 09 14</td></tr>
<tr><td>Licence</td><td>the Kaggle original is published under CC0 by its author</td></tr>
</table>

### Provenance chain

1. Records scraped from `sports-reference.com` by Randi H Griffin.
2. Published on Kaggle as "120 years of Olympic history: athletes and results",
   `https://www.kaggle.com/datasets/heesoo37/120-years-of-olympic-history-athletes-and-results`.
3. Mirrored by the TidyTuesday project for its 2021 week 31 edition,
   `https://github.com/rfordatascience/tidytuesday/tree/master/data/2021/2021-07-27`.

The Kaggle page requires an account. The TidyTuesday mirror does not, and it is byte for
byte the same table, which is why the mirror is the source of record here. Credit for the
data belongs to Randi H Griffin.

### Schema

<table>
<tr><td><code>id</code></td><td>athlete identifier, stable across Games</td></tr>
<tr><td><code>name</code></td><td>athlete name</td></tr>
<tr><td><code>sex</code></td><td>M or F</td></tr>
<tr><td><code>age</code></td><td>years, 3.5 percent missing</td></tr>
<tr><td><code>height</code></td><td>centimetres, 22.2 percent missing</td></tr>
<tr><td><code>weight</code></td><td>kilograms, 23.2 percent missing</td></tr>
<tr><td><code>team</code></td><td>team name as entered, not a clean country field</td></tr>
<tr><td><code>noc</code></td><td>three letter National Olympic Committee code, 230 distinct values</td></tr>
<tr><td><code>games</code></td><td>year and season, 51 distinct values</td></tr>
<tr><td><code>year</code></td><td>1896 to 2016</td></tr>
<tr><td><code>season</code></td><td>Summer or Winter</td></tr>
<tr><td><code>city</code></td><td>host city</td></tr>
<tr><td><code>sport</code></td><td>66 distinct values</td></tr>
<tr><td><code>event</code></td><td>765 distinct values</td></tr>
<tr><td><code>medal</code></td><td>Gold, Silver, Bronze, or NA</td></tr>
</table>

## Data we build ourselves

<table>
<tr><td><code>reference/noc_country_map.csv</code></td><td>NOC code to modern country, with a successor rule and a written justification per row. The Kaggle companion file <code>noc_regions.csv</code> is not mirrored publicly, so this is built by hand in Phase 1. Lives in <code>reference/</code> and not under <code>data/</code>, because <code>data/</code> is git ignored and these decisions have to travel with the repository.</td></tr>
<tr><td><code>reference/host_nations.csv</code></td><td>Games to host NOC, derived from the <code>city</code> column and checked by hand. Needed for the host advantage analysis in Phase 4.</td></tr>
</table>

## Not used

* Population and GDP series. Medals per capita is a natural extension but needs a second
  source and a second set of join defects. Out of scope, noted in `PLAN.md`.
