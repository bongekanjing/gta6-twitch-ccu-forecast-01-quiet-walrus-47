"""Forecast GTA VI launch-day Twitch viewers, hour by hour.

Approach: size-weighted median-ratio forecaster with a robust
size-trend correction.
  - The case gives hour 1's print p1 and a set of past big launches
    (comparables) with full hourly curves around their release day.
  - GTA VI unlocks at rolling midnight local time, like a console launch,
    so only rolling-midnight console-like launches are used as analogues:
    early-access-contaminated, free-to-play/weak, simultaneous-global
    (one worldwide unlock) and the target's own pre-release history are
    excluded. The filter is on the unlock description and tier, so the
    analogues share the launch shape, not just the size.
  - For each hour h, every eligible analogue contributes its log-ratio
    ln(viewers(h) / viewers(hour 1)). Analogues are weighted by how
    close their hour-1 size is to this case's p1 (Gaussian kernel in
    log size, bandwidth 0.7), so a huge launch is forecast mostly from
    huge launches and a small one mostly from small ones.
  - The forecast centre is the weighted median log-ratio, corrected for
    the strong size trend in the ratios: small launches ramp far more
    in the evening than big ones (evening log-ratio vs log hour-1 size
    has correlation about -0.9). The trend slope is the Theil-Sen
    estimator (median of pairwise slopes), a robust median-based slope,
    and the centre is shifted by slope * (log p1 - median analogue
    log size), clamped so no hour moves by more than 1.5 log units.
    The correction is ~0 in the morning (no trend there) and large in
    the evening, where the trend is real.
  - The spread is the weighted interquartile range of the log-ratios
    (converted to an SD scale), floored so the band stays honest, and
    widened when p1 sits outside the analogues' size range
    (extrapolation).
  - Quantiles are q_tau(h) = p1 * exp(centre_h + z_tau * s_h).
  - Fallbacks: if too few analogues survive the filter for an hour,
    relax the filter (any launch except the target's own history); if
    still too few, fall back to a widened persistence forecast.

Standard library only. Deterministic: no randomness, no time, no
network. Reads every *.in file in the input dir, writes one .out
per case.
"""

import json
import math
import os
import re
from pathlib import Path

INPUT_DIR = Path(os.environ.get("MAKEFUN_INPUT_DIR", "/input"))
OUTPUT_DIR = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))

LEVELS = [0.05, 0.25, 0.5, 0.75, 0.95]
Z = [-1.645, -0.674, 0.0, 0.674, 1.645]

# Gaussian kernel bandwidth (log units) for size weighting.
BANDWIDTH = 0.7
# Minimum analogues needed before relaxing the filter.
MIN_ANALOGUES = 3
# Minimum analogues needed to apply the trend correction.
MIN_TREND = 5
# Largest allowed trend correction (log units) in either direction.
MAX_CORRECTION = 1.5
# Spread floor (log units) and extrapolation widening.
SPREAD_FLOOR = 0.45
EXTRA_WIDE = 0.15
# Fallback persistence spread when no analogues exist at all.
FALLBACK_SIGMA = 0.35

_TIER_RE = re.compile(r"Tier:\s*([A-Za-z-]+)")
_SIMULT_RE = re.compile(r"single global unlock|simultaneous", re.IGNORECASE)


def round2(x):
    """Round to 2 decimals, half up (matches the kit's starter)."""
    scaled = x * 100.0
    whole = math.floor(scaled)
    if scaled - whole >= 0.5:
        whole += 1
    value = whole / 100.0
    return int(value) if float(value).is_integer() else value


def tier_of(comp):
    """Tier word from the unlock text, e.g. 'comparable'."""
    m = _TIER_RE.search(comp.get("unlock") or "")
    return m.group(1).lower() if m else ""


def is_simultaneous(comp):
    """True when the unlock is one worldwide moment, not rolling midnight."""
    return bool(_SIMULT_RE.search(comp.get("unlock") or ""))


def release_day_curve(comp):
    """Map hour (1..24) -> viewers on the comparable's release day.

    Returns None when the release day's hour 1 is missing or not positive.
    """
    hourly = comp.get("hourly") or []
    day_start = comp.get("day_start")
    if not day_start:
        return None
    start = None
    for i, pt in enumerate(hourly):
        if pt.get("from") == day_start:
            start = i
            break
    if start is None:
        return None
    curve = {}
    for h in range(1, 25):
        idx = start + h - 1
        if idx >= len(hourly):
            break
        v = hourly[idx].get("viewers")
        if isinstance(v, (int, float)) and v > 0:
            curve[h] = float(v)
    if 1 not in curve:
        return None
    return curve


def eligible(comp):
    """Rolling-midnight console-like launch, usable as an analogue."""
    t = tier_of(comp)
    if t in ("early-access-contaminated", "weak", "target-history"):
        return False
    if "grand theft auto vi" in (comp.get("name") or "").lower():
        return False
    if is_simultaneous(comp):
        return False
    return True


def weighted_median(pairs):
    """Weighted median of (value, weight) pairs."""
    ordered = sorted(pairs, key=lambda p: p[0])
    total = sum(w for _, w in ordered)
    if total <= 0:
        return ordered[len(ordered) // 2][0]
    acc = 0.0
    for value, w in ordered:
        acc += w
        if acc >= total / 2.0:
            return value
    return ordered[-1][0]


def weighted_iqr(pairs):
    """Weighted interquartile range of (value, weight) pairs."""
    ordered = sorted(pairs, key=lambda p: p[0])
    total = sum(w for _, w in ordered)
    if total <= 0 or len(ordered) < 2:
        return 0.0

    def quantile_at(frac):
        acc = 0.0
        target = total * frac
        for value, w in ordered:
            acc += w
            if acc >= target:
                return value
        return ordered[-1][0]

    return max(0.0, quantile_at(0.75) - quantile_at(0.25))


def theil_sen_slope(xs, ys):
    """Robust slope of y on x: the median of all pairwise slopes.

    Returns 0.0 when fewer than two distinct x values exist. Unlike a
    least-squares slope, a few extreme launches cannot drag it.
    """
    slopes = []
    n = len(xs)
    for i in range(n):
        for j in range(i + 1, n):
            dx = xs[j] - xs[i]
            if dx != 0.0:
                slopes.append((ys[j] - ys[i]) / dx)
    if not slopes:
        return 0.0
    slopes.sort()
    m = len(slopes)
    if m % 2 == 1:
        return slopes[m // 2]
    return 0.5 * (slopes[m // 2 - 1] + slopes[m // 2])


def forecast_case(case):
    if case.get("levels") != LEVELS:
        raise ValueError("levels are not %s" % (LEVELS,))
    known = case.get("known") or []
    first = next((k for k in known if k.get("hour") == 1), None)
    if first is None:
        # No hour-1 print: use the last whole-hour history point, else 1.
        hist = case.get("history_hourly") or []
        p1 = float(hist[-1]["viewers"]) if hist else 1.0
    else:
        p1 = float(first.get("viewers") or 1)
    p1 = max(1.0, p1)
    log_p1 = math.log(p1)

    # Build each analogue's release-day curve once, with its filter flag.
    analogues = []
    for comp in case.get("comparables") or []:
        curve = release_day_curve(comp)
        if curve is None:
            continue
        analogues.append({
            "curve": curve,
            "strict": eligible(comp),
            "log_v1": math.log(curve[1]),
        })
    if analogues:
        lo = min(a["log_v1"] for a in analogues)
        hi = max(a["log_v1"] for a in analogues)
    else:
        lo = hi = log_p1
    extrapolating = log_p1 < lo or log_p1 > hi

    rows = []
    for row in case.get("forecast") or []:
        h = int(row["hour"])
        # Triples (log-ratio, log hour-1 size, weight) for this hour.
        triples = []
        for a in analogues:
            if not a["strict"]:
                continue
            curve = a["curve"]
            if h in curve:
                lr = math.log(curve[h] / curve[1])
                w = math.exp(-0.5 * ((a["log_v1"] - log_p1) / BANDWIDTH) ** 2)
                triples.append((lr, a["log_v1"], w))
        if len(triples) < MIN_ANALOGUES:
            # Relax: any launch except the target's own history.
            triples = []
            for a in analogues:
                curve = a["curve"]
                if h in curve:
                    lr = math.log(curve[h] / curve[1])
                    w = math.exp(-0.5 * ((a["log_v1"] - log_p1) / BANDWIDTH) ** 2)
                    triples.append((lr, a["log_v1"], w))
        if len(triples) >= MIN_ANALOGUES:
            pairs = [(lr, w) for lr, _, w in triples]
            med = weighted_median(pairs)
            iqr = weighted_iqr(pairs)
            spread = max(SPREAD_FLOOR, iqr / 1.349)
            if extrapolating:
                spread += EXTRA_WIDE
            centre = med
            if len(triples) >= MIN_TREND:
                # Robust size-trend correction (Theil-Sen slope).
                xs = [lv for _, lv, _ in triples]
                ys = [lr for lr, _, _ in triples]
                slope = theil_sen_slope(xs, ys)
                med_log_v1 = weighted_median([(lv, w) for _, lv, w in triples])
                correction = slope * (log_p1 - med_log_v1)
                if correction > MAX_CORRECTION:
                    correction = MAX_CORRECTION
                elif correction < -MAX_CORRECTION:
                    correction = -MAX_CORRECTION
                centre = med + correction
        else:
            # No usable analogues: widened persistence around hour 1.
            centre = 0.0
            spread = FALLBACK_SIGMA * math.sqrt(max(1, h - 1))
        base = p1 * math.exp(centre)
        qs = []
        for z in Z:
            q = base * math.exp(z * spread)
            q = min(max(q, 1.0), 1e9)
            qs.append(round2(q))
        # Keep quantiles non-decreasing after rounding.
        for i in range(1, len(qs)):
            if qs[i] < qs[i - 1]:
                qs[i] = qs[i - 1]
        rows.append({"hour": h, "q": qs})
    return {"hours": rows}


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for path in sorted(INPUT_DIR.glob("*.in")):
        case = json.loads(path.read_text(encoding="utf-8"))
        forecast = forecast_case(case)
        out = OUTPUT_DIR / ("%s.out" % path.stem)
        out.write_text(json.dumps(forecast, separators=(",", ":")) + "\n",
                       encoding="utf-8")


if __name__ == "__main__":
    main()
