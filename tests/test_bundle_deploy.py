import io
import zipfile
from pathlib import Path

import pytest

from apigee_ops.bundle import package
from apigee_ops.deploy import deploy_call, import_call, run

PROXY = Path(__file__).parent.parent / "proxies" / "orders-api"


def test_package_is_reproducible():
    assert package(PROXY) == package(PROXY)


def test_package_layout():
    names = zipfile.ZipFile(io.BytesIO(package(PROXY))).namelist()
    assert names == sorted(names)
    assert "apiproxy/orders-api.xml" in names and "apiproxy/policies/ML-Splunk.xml" in names
    assert all(n.startswith("apiproxy/") for n in names)


def test_package_needs_an_apiproxy_folder(tmp_path):
    with pytest.raises(FileNotFoundError):
        package(tmp_path)


def test_urls():
    assert import_call("org1", "orders-api", b"x").url == \
        "https://apigee.googleapis.com/v1/organizations/org1/apis?action=import&name=orders-api"
    assert deploy_call("org1", "test", "orders-api", "7").url.startswith(
        "https://apigee.googleapis.com/v1/organizations/org1/environments/test/apis/orders-api/revisions/7/deployments?")


def test_dry_run_sends_nothing():
    calls = []
    out = io.StringIO()
    run("org1", "test", "orders-api", PROXY, apply=False, transport=lambda c, t: calls.append(c), out=out)
    assert calls == [] and "dry run" in out.getvalue()


def test_apply_imports_then_deploys_the_returned_revision():
    calls = []

    def fake(call, token):
        calls.append((call.url, token))
        return {"revision": "3"}

    assert run("org1", "prod", "orders-api", PROXY, apply=True, token="tok", transport=fake, out=io.StringIO()) == "3"
    assert "action=import" in calls[0][0] and "/revisions/3/deployments" in calls[1][0]
    assert all(t == "tok" for _, t in calls)
