import json
from pathlib import Path

from apigee_ops.capacity import analyze, parse_rows, to_markdown

DATA = Path(__file__).parent.parent / "data" / "sample_analytics.csv"
GOLDEN = Path(__file__).parent / "fixtures" / "capacity_golden.json"


def _rows(text):
    return parse_rows(text.strip().splitlines())


def test_matches_golden_result():
    with open(DATA, newline="") as f:
        result = analyze(parse_rows(f), 100)
    assert result == json.loads(GOLDEN.read_text())


def test_flat_traffic_has_no_estimate():
    rows = _rows("""timestamp,proxy,tps,p99_ms,error_rate
2026-11-01T10:00:00+00:00,a,10,100,0
2026-11-02T10:00:00+00:00,a,10,100,0
2026-11-03T10:00:00+00:00,a,10,100,0""")
    assert analyze(rows, 100)["days_to_threshold"] is None


def test_past_the_threshold_reports_zero():
    rows = _rows("""timestamp,proxy,tps,p99_ms,error_rate
2026-11-01T10:00:00+00:00,a,90,100,0
2026-11-02T10:00:00+00:00,a,91,100,0""")
    assert analyze(rows, 100)["days_to_threshold"] == 0.0


def test_total_is_summed_per_timestamp_not_per_proxy():
    rows = _rows("""timestamp,proxy,tps,p99_ms,error_rate
2026-11-01T10:00:00+00:00,a,30,100,0
2026-11-01T10:00:00+00:00,b,20,100,0
2026-11-01T11:00:00+00:00,a,10,100,0""")
    assert analyze(rows, 100)["peak_total_tps"] == 50


def test_markdown_names_the_time_to_threshold():
    with open(DATA, newline="") as f:
        assert "about 7.1 days" in to_markdown(analyze(parse_rows(f), 100))
