import json

from apigee_ops.certs import check_bundle, renew
from conftest import NOW, key_pem, make_cert, pem

HOST = ["api.example.com"]


def test_valid_bundle_has_no_errors():
    cert, key = make_cert()
    r = check_bundle(pem(cert), key_pem(key), HOST, NOW)
    assert r.ok and r.days_left == 90 and not r.warnings


def test_expired_certificate_is_an_error():
    cert, key = make_cert(days=-2, start_offset=-90)
    assert "certificate is expired" in check_bundle(pem(cert), key_pem(key), HOST, NOW).errors


def test_expiring_soon_warns_but_is_not_an_error():
    cert, key = make_cert(days=10)
    r = check_bundle(pem(cert), key_pem(key), HOST, NOW, warn_days=30)
    assert r.ok and r.warnings == ["expires in 10 days"]


def test_key_mismatch_is_an_error():
    cert, _ = make_cert()
    _, other = make_cert()
    assert "private key does not match the certificate" in check_bundle(pem(cert), key_pem(other), HOST, NOW).errors


def test_missing_host_is_an_error():
    cert, key = make_cert(sans=("other.example.com",))
    assert "certificate does not cover api.example.com" in check_bundle(pem(cert), key_pem(key), HOST, NOW).errors


def test_wildcard_covers_one_label_only():
    cert, key = make_cert(sans=("*.example.com",))
    assert check_bundle(pem(cert), key_pem(key), ["api.example.com"], NOW).ok
    r = check_bundle(pem(cert), key_pem(key), ["a.b.example.com"], NOW)
    assert "certificate does not cover a.b.example.com" in r.errors


def test_chain_must_be_leaf_first():
    ca, ca_key = make_cert(cn="Test CA", sans=(), days=365, ca=True)
    leaf, key = make_cert(issuer_cert=ca, issuer_key=ca_key)
    assert check_bundle(pem(leaf, ca), key_pem(key), HOST, NOW).ok
    r = check_bundle(pem(ca, leaf), key_pem(key), HOST, NOW)
    assert any("out of order" in e for e in r.errors)


def test_first_write_creates_a_version(store):
    cert, key = make_cert()
    res = renew(store, "apigee-tls-test", pem(cert), key_pem(key), HOST, NOW)
    assert res.action == "written"
    assert set(json.loads(store.latest("apigee-tls-test"))) == {"cert", "key"}


def test_same_bundle_twice_adds_no_second_version(store):
    cert, key = make_cert()
    renew(store, "s", pem(cert), key_pem(key), HOST, NOW)
    assert renew(store, "s", pem(cert), key_pem(key), HOST, NOW).action == "unchanged"
    assert len(store.versions["s"]) == 1


def test_longer_lived_certificate_replaces_the_old_one(store):
    old, k1 = make_cert(days=40)
    new, k2 = make_cert(days=90)
    renew(store, "s", pem(old), key_pem(k1), HOST, NOW)
    assert renew(store, "s", pem(new), key_pem(k2), HOST, NOW).action == "written"
    assert len(store.versions["s"]) == 2


def test_older_certificate_never_replaces_a_newer_one(store):
    new, k1 = make_cert(days=90)
    old, k2 = make_cert(days=60)
    renew(store, "s", pem(new), key_pem(k1), HOST, NOW)
    res = renew(store, "s", pem(old), key_pem(k2), HOST, NOW)
    assert res.action == "rejected" and "does not expire later" in res.reasons[0]
    assert len(store.versions["s"]) == 1


def test_bad_bundle_is_rejected_and_nothing_is_written(store):
    cert, _ = make_cert()
    _, wrong_key = make_cert()
    res = renew(store, "s", pem(cert), key_pem(wrong_key), HOST, NOW)
    assert res.action == "rejected" and store.latest("s") is None


def test_short_lived_replacement_is_rejected(store):
    cert, key = make_cert(days=10)
    res = renew(store, "s", pem(cert), key_pem(key), HOST, NOW, min_days=30)
    assert res.action == "rejected"
