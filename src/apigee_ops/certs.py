"""TLS certificate checks and renewal into a secret store.

A secret holds one JSON document: {"cert": "<PEM chain, leaf first>", "key": "<PEM>"}.
renew() only writes a new version when the new bundle is safe to deploy.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from cryptography import x509
from cryptography.hazmat.primitives import serialization


class SecretStore(Protocol):
    def latest(self, name: str) -> bytes | None: ...
    def add_version(self, name: str, payload: bytes) -> None: ...


@dataclass
class BundleReport:
    days_left: int
    not_after: datetime
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def load_chain(pem: bytes) -> list[x509.Certificate]:
    chain = x509.load_pem_x509_certificates(pem)
    if not chain:
        raise ValueError("no certificate found in PEM")
    return chain


def _public_bytes(public_key) -> bytes:
    return public_key.public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
    )


def _hostnames(cert: x509.Certificate) -> set[str]:
    try:
        san = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName)
    except x509.ExtensionNotFound:
        return set()
    return {n.lower() for n in san.value.get_values_for_type(x509.DNSName)}


def _covers(patterns: set[str], host: str) -> bool:
    host = host.lower()
    for p in patterns:
        if p == host:
            return True
        # A wildcard covers exactly one label: *.example.com matches a.example.com, not a.b.example.com.
        if p.startswith("*.") and host.count(".") == p.count(".") and host.endswith(p[1:]):
            return True
    return False


def check_bundle(cert_pem: bytes, key_pem: bytes, hostnames: list[str],
                 now: datetime, warn_days: int = 30) -> BundleReport:
    chain = load_chain(cert_pem)
    leaf = chain[0]
    not_after = leaf.not_valid_after_utc
    days_left = (not_after - now).days
    report = BundleReport(days_left=days_left, not_after=not_after)

    if leaf.not_valid_before_utc > now:
        report.errors.append("certificate is not valid yet")
    if not_after <= now:
        report.errors.append("certificate is expired")
    elif days_left < warn_days:
        report.warnings.append(f"expires in {days_left} days")

    key = serialization.load_pem_private_key(key_pem, password=None)
    if _public_bytes(key.public_key()) != _public_bytes(leaf.public_key()):
        report.errors.append("private key does not match the certificate")

    names = _hostnames(leaf)
    for host in hostnames:
        if not _covers(names, host):
            report.errors.append(f"certificate does not cover {host}")

    for child, parent in zip(chain, chain[1:]):
        if child.issuer != parent.subject:
            report.errors.append("chain is out of order: expected leaf first, then its issuer")
            break
    return report


@dataclass
class RenewResult:
    action: str  # "written", "unchanged" or "rejected"
    reasons: list[str] = field(default_factory=list)


def renew(store: SecretStore, name: str, cert_pem: bytes, key_pem: bytes,
          hostnames: list[str], now: datetime, min_days: int = 30) -> RenewResult:
    report = check_bundle(cert_pem, key_pem, hostnames, now, warn_days=min_days)
    reasons = list(report.errors)
    if report.days_left < min_days and not report.errors:
        reasons.append(f"new certificate has only {report.days_left} days left, need {min_days}")

    payload = json.dumps({"cert": cert_pem.decode(), "key": key_pem.decode()}, sort_keys=True).encode()
    current = store.latest(name)
    if current is not None and not reasons:
        if current == payload:
            return RenewResult("unchanged")
        old = load_chain(json.loads(current)["cert"].encode())[0]
        new = load_chain(cert_pem)[0]
        if new.not_valid_after_utc <= old.not_valid_after_utc:
            reasons.append("new certificate does not expire later than the current one")

    if reasons:
        return RenewResult("rejected", reasons)
    store.add_version(name, payload)
    return RenewResult("written")


class GcpSecretStore:
    """Secret Manager backend. Needs the `gcp` extra and Application Default Credentials."""

    def __init__(self, project: str):
        from google.cloud import secretmanager  # imported late so tests need no GCP library

        self._client = secretmanager.SecretManagerServiceClient()
        self._project = project

    def latest(self, name: str) -> bytes | None:
        from google.api_core.exceptions import NotFound

        try:
            path = f"projects/{self._project}/secrets/{name}/versions/latest"
            return self._client.access_secret_version(request={"name": path}).payload.data
        except NotFound:
            return None

    def add_version(self, name: str, payload: bytes) -> None:
        parent = f"projects/{self._project}/secrets/{name}"
        self._client.add_secret_version(request={"parent": parent, "payload": {"data": payload}})


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="apigee_ops.certs")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for cmd in ("check", "renew"):
        p = sub.add_parser(cmd)
        p.add_argument("--cert", required=True, help="PEM file, leaf first")
        p.add_argument("--key", required=True, help="PEM private key")
        p.add_argument("--host", action="append", default=[], help="host name the cert must cover")
        p.add_argument("--warn-days", type=int, default=30)
        if cmd == "renew":
            p.add_argument("--project", required=True)
            p.add_argument("--secret", required=True)
    args = ap.parse_args(argv)

    cert_pem = open(args.cert, "rb").read()
    key_pem = open(args.key, "rb").read()
    now = datetime.now(timezone.utc)

    if args.cmd == "check":
        r = check_bundle(cert_pem, key_pem, args.host, now, args.warn_days)
        print(f"days left: {r.days_left}  not after: {r.not_after:%Y-%m-%d}")
        for m in r.errors:
            print(f"error: {m}")
        for m in r.warnings:
            print(f"warning: {m}")
        return 1 if r.errors else (2 if r.warnings else 0)

    res = renew(GcpSecretStore(args.project), args.secret, cert_pem, key_pem, args.host, now, args.warn_days)
    print(res.action)
    for m in res.reasons:
        print(f"reason: {m}")
    return 1 if res.action == "rejected" else 0


if __name__ == "__main__":
    sys.exit(main())
