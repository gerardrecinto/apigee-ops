"""Writes the synthetic sample files in this folder. Fixed seed, so the output never changes.
Run: python data/make_sample_data.py
"""
import csv
import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

here = Path(__file__).parent
rng = random.Random(7)

# 28 days of hourly analytics for two proxies. orders-api grows about 0.9 TPS per day.
start = datetime(2026, 10, 26, tzinfo=timezone.utc)
with open(here / "sample_analytics.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["timestamp", "proxy", "tps", "p99_ms", "error_rate"])
    for h in range(28 * 24):
        ts = start + timedelta(hours=h)
        day = h // 24
        daily_curve = 0.35 + 0.65 * max(0.0, 1 - abs(ts.hour - 14) / 8)
        orders = (40 + 0.9 * day) * daily_curve + rng.uniform(-2, 2)
        token = (6 + 0.1 * day) * daily_curve + rng.uniform(-0.5, 0.5)
        w.writerow([ts.isoformat(), "orders-api", round(orders, 2), round(rng.uniform(120, 260), 1), round(rng.uniform(0.001, 0.01), 4)])
        w.writerow([ts.isoformat(), "oauth-token", round(token, 2), round(rng.uniform(60, 140), 1), round(rng.uniform(0.0, 0.005), 4)])

# One week of gateway log lines in the ML-Splunk format, plus two damaged lines.
base = int(datetime(2026, 11, 16, tzinfo=timezone.utc).timestamp() * 1000)
with open(here / "sample_gateway.log", "w") as f:
    for i in range(1400):
        proxy = "orders-api" if rng.random() < 0.85 else "oauth-token"
        verb, path = ("GET", f"/orders/{rng.randint(1000, 1040)}") if proxy == "orders-api" else ("POST", "/token")
        roll = rng.random()
        status = 200 if roll < 0.93 else (401 if roll < 0.97 else (404 if roll < 0.99 else 503))
        f.write(json.dumps({"ts": base + i * 430_000, "proxy": proxy, "verb": verb, "path": path,
                            "status": status, "latency_ms": int(rng.lognormvariate(5.0, 0.5))}) + "\n")
    f.write("this line is not json\n")
    f.write('{"ts": 1, "proxy": "orders-api"}\n')
