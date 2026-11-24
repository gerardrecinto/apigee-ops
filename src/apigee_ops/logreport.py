"""Daily and weekly report from the JSON lines the ML-Splunk policy writes.

Required fields are checked against the policy XML in tests, so the log format and
this parser cannot drift apart without a test failing.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone

REQUIRED_FIELDS = ("ts", "proxy", "verb", "path", "status", "latency_ms")


def parse(lines) -> tuple[list[dict], int]:
    """Returns (events, skipped). Bad lines are counted, not fatal: a gateway log always has a few."""
    events, skipped = [], 0
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            e = json.loads(line)
            if not all(k in e for k in REQUIRED_FIELDS):
                raise ValueError("missing field")
            e["ts"], e["status"], e["latency_ms"] = int(e["ts"]), int(e["status"]), int(e["latency_ms"])
        except (ValueError, TypeError):
            skipped += 1
            continue
        events.append(e)
    return events, skipped


def percentile(values: list[int], pct: float) -> int:
    """Nearest-rank percentile."""
    if not values:
        return 0
    s = sorted(values)
    return s[max(0, math.ceil(pct / 100 * len(s)) - 1)]


def _day(ts_ms: int) -> str:
    return datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d")


def summarize(events: list[dict]) -> dict:
    by_proxy: dict[str, list[dict]] = defaultdict(list)
    for e in events:
        by_proxy[e["proxy"]].append(e)
    total = len(events)
    errors5 = sum(1 for e in events if e["status"] >= 500)
    errors4 = sum(1 for e in events if 400 <= e["status"] < 500)
    return {
        "requests": total,
        "client_error_pct": round(100 * errors4 / total, 2) if total else 0.0,
        "server_error_pct": round(100 * errors5 / total, 2) if total else 0.0,
        "p95_ms": percentile([e["latency_ms"] for e in events], 95),
        "proxies": {
            p: {
                "requests": len(es),
                "server_error_pct": round(100 * sum(1 for e in es if e["status"] >= 500) / len(es), 2),
                "p95_ms": percentile([e["latency_ms"] for e in es], 95),
            }
            for p, es in sorted(by_proxy.items())
        },
        "top_paths": Counter(f"{e['verb']} {e['path']}" for e in events).most_common(5),
    }


def report(events: list[dict], skipped: int = 0) -> dict:
    days = defaultdict(list)
    for e in events:
        days[_day(e["ts"])].append(e)
    return {
        "skipped_lines": skipped,
        "weekly": summarize(events),
        "daily": {d: summarize(es) for d, es in sorted(days.items())},
    }


def to_markdown(rep: dict) -> str:
    w = rep["weekly"]
    out = [
        "# Gateway report",
        "",
        f"Period total: {w['requests']} requests, {w['client_error_pct']}% 4xx, "
        f"{w['server_error_pct']}% 5xx, p95 {w['p95_ms']} ms. Skipped log lines: {rep['skipped_lines']}.",
        "",
        "| Day | Requests | 4xx % | 5xx % | p95 ms |",
        "|---|---|---|---|---|",
    ]
    for d, s in rep["daily"].items():
        out.append(f"| {d} | {s['requests']} | {s['client_error_pct']} | {s['server_error_pct']} | {s['p95_ms']} |")
    out += ["", "| Proxy | Requests | 5xx % | p95 ms |", "|---|---|---|---|"]
    for p, s in w["proxies"].items():
        out.append(f"| {p} | {s['requests']} | {s['server_error_pct']} | {s['p95_ms']} |")
    out += ["", "Top paths:"] + [f"- {name}: {n}" for name, n in w["top_paths"]]
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="apigee_ops.logreport")
    ap.add_argument("logfile")
    args = ap.parse_args(argv)
    with open(args.logfile) as f:
        events, skipped = parse(f)
    sys.stdout.write(to_markdown(report(events, skipped)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
