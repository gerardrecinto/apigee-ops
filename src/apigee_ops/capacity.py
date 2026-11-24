"""Capacity planning from analytics-style rows.

Input rows: timestamp (ISO 8601), proxy, tps (requests per second), p99_ms, error_rate.
Output: peak TPS per proxy, headroom against the instance capacity you give it, and a
straight-line estimate of the days until total peak TPS reaches the planning threshold.
"""
from __future__ import annotations

import argparse
import csv
import sys
from collections import defaultdict
from datetime import datetime


def parse_rows(lines) -> list[dict]:
    rows = []
    for r in csv.DictReader(lines):
        rows.append({
            "ts": datetime.fromisoformat(r["timestamp"].replace("Z", "+00:00")),
            "proxy": r["proxy"],
            "tps": float(r["tps"]),
            "p99_ms": float(r["p99_ms"]),
            "error_rate": float(r["error_rate"]),
        })
    return rows


def _fit(points: list[tuple[int, float]]) -> tuple[float, float]:
    """Least squares line y = a + b*x. Returns (a, b)."""
    n = len(points)
    if n < 2:
        return (points[0][1] if points else 0.0, 0.0)
    sx = sum(x for x, _ in points)
    sy = sum(y for _, y in points)
    sxx = sum(x * x for x, _ in points)
    sxy = sum(x * y for x, y in points)
    den = n * sxx - sx * sx
    if den == 0:
        return (sy / n, 0.0)
    b = (n * sxy - sx * sy) / den
    return ((sy - b * sx) / n, b)


def analyze(rows: list[dict], capacity_tps: float, threshold: float = 0.8) -> dict:
    if not rows:
        raise ValueError("no rows to analyze")
    peak_by_proxy: dict[str, float] = defaultdict(float)
    total_at: dict[datetime, float] = defaultdict(float)
    p99_by_proxy: dict[str, float] = defaultdict(float)
    for r in rows:
        peak_by_proxy[r["proxy"]] = max(peak_by_proxy[r["proxy"]], r["tps"])
        p99_by_proxy[r["proxy"]] = max(p99_by_proxy[r["proxy"]], r["p99_ms"])
        total_at[r["ts"]] += r["tps"]

    daily_peak: dict[str, float] = {}
    for ts, tps in total_at.items():
        day = ts.strftime("%Y-%m-%d")
        daily_peak[day] = max(daily_peak.get(day, 0.0), tps)
    days = sorted(daily_peak)
    first = datetime.strptime(days[0], "%Y-%m-%d")
    points = [((datetime.strptime(d, "%Y-%m-%d") - first).days, daily_peak[d]) for d in days]
    a, slope = _fit(points)
    last_x = points[-1][0]
    current = a + slope * last_x

    limit = capacity_tps * threshold
    days_to_threshold = None
    if current >= limit:
        days_to_threshold = 0.0
    elif slope > 0:
        days_to_threshold = round((limit - current) / slope, 1)

    peak_total = max(daily_peak.values())
    return {
        "capacity_tps": capacity_tps,
        "threshold": threshold,
        "peak_total_tps": round(peak_total, 2),
        "headroom_pct": round((1 - peak_total / capacity_tps) * 100, 1),
        "growth_tps_per_day": round(slope, 3),
        "days_to_threshold": days_to_threshold,
        "proxies": {
            p: {"peak_tps": round(peak_by_proxy[p], 2), "worst_p99_ms": round(p99_by_proxy[p], 1)}
            for p in sorted(peak_by_proxy)
        },
    }


def to_markdown(result: dict) -> str:
    d = result["days_to_threshold"]
    when = "not growing" if d is None else ("already past it" if d == 0 else f"about {d} days")
    lines = [
        "# Capacity report",
        "",
        f"- Instance capacity: {result['capacity_tps']} TPS (planning threshold {int(result['threshold'] * 100)}%)",
        f"- Peak total: {result['peak_total_tps']} TPS, headroom {result['headroom_pct']}%",
        f"- Growth: {result['growth_tps_per_day']} TPS per day",
        f"- Time to threshold: {when}",
        "",
        "| Proxy | Peak TPS | Worst p99 (ms) |",
        "|---|---|---|",
    ]
    for p, v in result["proxies"].items():
        lines.append(f"| {p} | {v['peak_tps']} | {v['worst_p99_ms']} |")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="apigee_ops.capacity")
    ap.add_argument("csv")
    ap.add_argument("--capacity-tps", type=float, required=True)
    ap.add_argument("--threshold", type=float, default=0.8)
    args = ap.parse_args(argv)
    with open(args.csv, newline="") as f:
        result = analyze(parse_rows(f), args.capacity_tps, args.threshold)
    sys.stdout.write(to_markdown(result))
    d = result["days_to_threshold"]
    return 1 if d is not None and d < 30 else 0


if __name__ == "__main__":
    sys.exit(main())
