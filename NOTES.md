# GTA VI Twitch CCU forecaster — @quiet-walrus-47

Forecast GTA VI's launch-day Twitch viewers hour by hour (hours 2–24),
as five quantiles per hour. Entry for make.fun bounty
`gta6-twitch-ccu-forecast-01` ($250, 20 places), submitted by the
new account @quiet-walrus-47 (wallet
`4KxteSB6SX7gJ62BDmgVgTBS2ZaYSodoMESYB8ukWUpi`).

## Approach

Size-weighted median-ratio forecaster with a robust size-trend
correction. `main.py` (Python 3.13, standard library only, no network,
deterministic) reads every `*.in` file in the input dir and writes one
`.out` per case.

- Analogues are the case's own rolling-midnight comparables: GTA VI's
  own pre-release history is excluded by name guard, simultaneous-global
  (one worldwide unlock) launches are excluded, and
  early-access-contaminated / weak tiers are excluded. 20 of 38
  comparables are strict-eligible in the practice cases.
- For each hour h, every eligible analogue contributes its log-ratio
  ln(viewers(h) / viewers(hour 1)), weighted by a Gaussian kernel in
  log hour-1 size (bandwidth 0.7), so a huge launch is forecast mostly
  from huge launches and a small one mostly from small ones.
- Centre = weighted median log-ratio, corrected for the strong size
  trend in the ratios: small launches ramp far more in the evening than
  big ones (evening log-ratio vs log hour-1 size, correlation about
  -0.9). The slope is the Theil–Sen estimator (median of pairwise
  slopes, robust to extreme launches), and the centre shifts by
  slope × (log p1 − median analogue log size), clamped to ±1.5 log
  units. The correction is ~0 in the morning (no trend there) and
  large in the evening. The trend prediction nails the practice
  evenings: for Wolverine (p1 23,357) it predicts evening log-ratios
  1.70/2.10/2.13 at h17/19/21 vs truth 1.75/2.02/2.21, while the plain
  median gives 0.94/1.22/1.16.
- Spread = weighted interquartile range of the log-ratios (÷1.349),
  floored at 0.45 log units, +0.15 when hour-1 size sits outside the
  analogues' range (extrapolation — GTA VI's hour 1 will likely be
  1–3M, above the 875k training max).
- Quantiles: q_τ(h) = p1 · exp(centre_h + z_τ · s_h).
- Fallbacks: <3 analogues for an hour → relax the filter (any launch
  except the target's own history); none → widened persistence.

This is an independent implementation. It shares no code with any other
entry for this bounty.

## Validation (local, on the VM)

Practice answers are SullyGnome hourly averages for the release days
(p03 Spider-Man 2 is unscorable — SullyGnome returns all-null for Oct
2023; p01 RDR2 answers were not retrievable — SullyGnome returns HTTP
403 from this VM).

Direct practice pinball loss (log scale, lower is better):

| case | this entry | starter (house baseline) |
|------|-----------|--------------------------|
| p00 Wolverine (h1 23,357) | 0.2753 | 0.7437 |
| p02 GoW Ragnarök (h1 269,517) | 0.1966 | 0.2146 |
| mean (p00+p02) | **0.2359** | 0.4792 |

Leave-one-out over the comparables (each eligible comparable as a
pseudo-case, the rest as analogues):

| set | this entry | starter |
|-----|-----------|---------|
| all 37 with a curve | 0.4865 | 0.9297 |
| large, p1 ≥ 20,000 (n=27) | 0.2724 | 0.3214 |
| largest 10 by hour-1 size | **0.2469** | 0.2626 |

The largest-10 LOO is the regime closest to the final (GTA VI's hour
1 will likely be 1–3M). The plain weighted-median version (v1) scored
0.2541 there; the trend correction (v2, this entry) improves it to
0.2469 and improves p00 from 0.3127 to 0.2753.

Output checks (all pass): 23 rows, hours 2–24, five quantiles each,
finite, >0, ≤1e9, non-decreasing, ~1.5 KB per file (limit 65,536),
~0.1 s per case (limit 8 s), byte-identical across two runs
(deterministic), standard library only.

Final-case risk: GTA VI hour 1 could print 1–3M (training max 875k);
the model clamps and widens the spread on extrapolation, and the
trend correction pulls the evening centre down for a huge hour 1
(big launches ramp less). Worst large-launch LOO case is a launch
with an extreme evening ramp.

## Files

- `main.py` — the entrypoint (single file, Python stdlib only).
- `README.md` — this entry, how it works, how to run it.
- `NOTES.md` — this file (approach, validation, decisions).
- `LICENSE` — MIT.
- `.makefun/owner.json` — `{"wallet": "4KxteSB6SX7gJ62BDmgVgTBS2ZaYSodoMESYB8ukWUpi"}`,
  naming the @quiet-walrus-47 wallet (wallet-only account, no GitHub
  login), so the repo passes the repo_owner check.

## Work log

- 2026-11-17: previous builder session wrote the v1 weighted-median
  forecaster (main.py), validate.py (LOO + direct practice scorer),
  sweep.py (parameter sweep), and SullyGnome probe scripts; outputs
  in out/ and out2/ verified byte-identical (deterministic).
- 2026-11-17: continued in this session. Diagnosed p00 (Wolverine):
  the plain median underpredicts the evening ramp (truth/p1 log-ratio
  1.75 at h17 vs median 0.94) because evening log-ratios fall steeply
  with launch size (corr −0.93). Added the Theil–Sen size-trend
  correction (v2). Re-validated: direct p00 0.2753, p02 0.1966;
  LOO large 0.2724, largest-10 0.2469; outputs valid and
  deterministic; synthetic p1=2M case sane (0.005 s, 23 rows).
- Repo files (main.py, README.md, NOTES.md, LICENSE,
  .makefun/owner.json) synced to the sandbox for GitHub push + submit
  under @quiet-walrus-47.
