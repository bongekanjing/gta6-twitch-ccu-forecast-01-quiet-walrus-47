[![make.fun · gta6-twitch-ccu-forecast-01](https://make.fun/badge/gta6-twitch-ccu-forecast-01.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![rank](https://make.fun/badge/gta6-twitch-ccu-forecast-01/bongekanjing/gta6-twitch-ccu-forecast-01-quiet-walrus-47/rank.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![reward](https://make.fun/badge/gta6-twitch-ccu-forecast-01/bongekanjing/gta6-twitch-ccu-forecast-01-quiet-walrus-47/reward.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)

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
  slope, shrunk by 0.55 and clamped to ±1.5 log units.
- **Why the slope is shrunk:** the kernel weighting already pulls the
  weighted median part-way toward the target's size, so it absorbs
  some of the size dependence. Applying the full Theil–Sen slope on top
  double-counts it and overshoots the evening ramp for large launches.
  A shrinkage of 0.55 removes the overlap; it was chosen on
  leave-one-out over the comparables, never on the practice answers.
- **Band shape:** a normal band around the corrected centre is blended
  70/30 with the empirical quantiles of the same corrected ratios, so
  the observed skew and tail weight are not flattened away by assuming
  normality. The blend is uniform across levels and robust because the
  underlying ratios are already size-corrected.
- **Spread:** the weighted interquartile range of the log-ratios,
  floored at 0.45 log units, widened when hour-1 size sits outside the
  analogues' range (GTA VI's hour 1 will likely be 1–3M, above the
  875k training max).
- **Quantiles:** q_τ(h) = p1 · exp(centre_h + z_τ · s_h), with the
  empirical blend as above.
- **Fallbacks:** too few analogues → relax the filter; none → widened
  persistence around hour 1.

## Validation

Local validation on the kit's practice cases (SullyGnome hourly
averages; Spider-Man 2 is unscorable — SullyGnome returns no data for
Oct 2023):

| case | this entry | house baseline (starter) |
|------|-----------|--------------------------|
| Marvel's Wolverine (h1 23,357) | 0.2931 | 0.7437 |
| God of War Ragnarök (h1 269,517) | 0.1584 | 0.2146 |
| mean | **0.2258** | 0.4792 |

Leave-one-out over the 37 comparables that have a release-day curve
(each comparable is the pseudo-case, the rest are its analogues):

| set | this entry | starter |
|-----|-----------|---------|
| all 37 | 0.4620 | 0.9297 |
| median | 0.3060 | 0.3248 |
| p1 ≥ 20,000 (n=27) | 0.2628 | 0.3214 |
| 10 largest by hour-1 | **0.2306** | 0.2626 |

The 10-largest set is the regime closest to the final: GTA VI's hour 1
will likely be 1–3M. Outputs are valid (23 rows, hours 2–24, five
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
