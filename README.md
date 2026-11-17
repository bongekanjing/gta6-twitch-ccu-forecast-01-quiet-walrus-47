[![make.fun bounty](https://make.fun/badge/gta6-twitch-ccu-forecast-01.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01)

# GTA VI launch-day Twitch viewership forecaster

Forecasts how many people watch Grand Theft Auto VI live on Twitch in
each hour of its release day (2026-11-19 UTC), after the first hour, as
five quantiles per hour (5%, 25%, 50%, 75%, 95%). Entry for the
[make.fun bounty](https://make.fun/bounty/gta6-twitch-ccu-forecast-01).

## How it works

`main.py` (Python 3.13, standard library only, no network,
deterministic) reads every `*.in` case in the input directory and
writes one `.out` forecast per case.

- **Analogues:** the case's own past big launches (comparables) with
  full hourly curves around their release day. Only rolling-midnight,
  console-like launches count: GTA VI's own pre-release history,
  simultaneous-global unlocks, and early-access-contaminated / weak
  tiers are excluded.
- **Centre:** for each hour, the size-weighted median of the
  analogues' log-ratios ln(viewers(h) / viewers(hour 1)), with a
  Gaussian kernel in log hour-1 size — so a huge launch is forecast
  mostly from huge launches. The median is then corrected for the
  strong size trend in the ratios (small launches ramp far more in the
  evening than big ones, correlation ≈ −0.9) using a robust Theil–Sen
  slope, clamped to ±1.5 log units.
- **Spread:** the weighted interquartile range of the log-ratios,
  floored at 0.45 log units, widened when hour-1 size sits outside the
  analogues' range (GTA VI's hour 1 will likely be 1–3M, above the
  875k training max).
- **Quantiles:** q_τ(h) = p1 · exp(centre_h + z_τ · s_h).
- **Fallbacks:** too few analogues → relax the filter; none → widened
  persistence around hour 1.

## Validation

Local validation on the kit's practice cases (SullyGnome hourly
averages; Spider-Man 2 is unscorable — SullyGnome returns no data for
Oct 2023):

| case | this entry | house baseline (starter) |
|------|-----------|--------------------------|
| Marvel's Wolverine (h1 23,357) | 0.2753 | 0.7437 |
| God of War Ragnarök (h1 269,517) | 0.1966 | 0.2146 |
| mean | **0.2359** | 0.4792 |

Leave-one-out over the comparables: 0.2724 on large launches
(p1 ≥ 20,000) vs 0.3214 for the starter; 0.2469 on the 10 largest
launches vs 0.2626. Outputs are valid (23 rows, hours 2–24, five
non-decreasing quantiles each), ~0.1 s per case, and byte-identical
across runs.

## Run it

```sh
mkdir -p out
MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=out python3 main.py
```

Reads `$MAKEFUN_INPUT_DIR` (default `/input`), writes one
`<id>.out` per `<id>.in` to `$MAKEFUN_OUTPUT_DIR` (default `/output`).

## License

MIT — see [LICENSE](LICENSE).
