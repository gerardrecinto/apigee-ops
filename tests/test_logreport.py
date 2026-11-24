import re
from pathlib import Path

from apigee_ops.logreport import REQUIRED_FIELDS, parse, percentile, report

ROOT = Path(__file__).parent.parent
LOG = ROOT / "data" / "sample_gateway.log"
POLICY = ROOT / "proxies" / "orders-api" / "apiproxy" / "policies" / "ML-Splunk.xml"


def test_log_fields_match_the_policy_message():
    """If someone renames a field in ML-Splunk.xml, this fails before the report silently breaks."""
    message = re.search(r"<Message>(.*)</Message>", POLICY.read_text(), re.S).group(1)
    assert set(re.findall(r'"(\w+)":', message)) == set(REQUIRED_FIELDS)


def test_policy_message_renders_as_json_after_substitution():
    message = re.search(r"<Message>(.*)</Message>", POLICY.read_text(), re.S).group(1)
    sample = {"system.timestamp": "1794787200000", "apiproxy.name": "orders-api", "request.verb": "GET",
              "proxy.pathsuffix": "/orders/1", "response.status.code": "200", "log.latency_ms": "88"}
    rendered = re.sub(r"\{([\w.]+)\}", lambda m: sample[m.group(1)], message)
    events, skipped = parse([rendered])
    assert skipped == 0 and events[0]["status"] == 200


def test_bad_lines_are_counted_not_fatal():
    events, skipped = parse(["not json", '{"ts": 1}', "", '{"ts":1,"proxy":"p","verb":"GET","path":"/","status":200,"latency_ms":5}'])
    assert len(events) == 1 and skipped == 2


def test_percentile_is_nearest_rank():
    assert percentile([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 95) == 10
    assert percentile([1, 2, 3, 4], 50) == 2
    assert percentile([], 95) == 0


def test_sample_week_report():
    with open(LOG) as f:
        events, skipped = parse(f)
    rep = report(events, skipped)
    assert skipped == 2 and rep["weekly"]["requests"] == 1400
    assert list(rep["daily"]) == [f"2026-11-{d}" for d in range(16, 23)]
    assert sum(d["requests"] for d in rep["daily"].values()) == 1400
