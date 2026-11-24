"""Import a proxy bundle into Apigee X and deploy the new revision.

Dry run is the default: it prints the calls it would make and sends nothing.
Pass --apply to send them. Authentication is a bearer token from `gcloud auth print-access-token`.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .bundle import package, sha256

BASE = "https://apigee.googleapis.com/v1"


@dataclass
class Call:
    method: str
    url: str
    body: bytes | None
    content_type: str


Transport = Callable[[Call, str], dict]


def import_call(org: str, api: str, bundle: bytes) -> Call:
    return Call("POST", f"{BASE}/organizations/{org}/apis?action=import&name={api}", bundle, "application/octet-stream")


def deploy_call(org: str, env: str, api: str, revision: str) -> Call:
    url = (f"{BASE}/organizations/{org}/environments/{env}/apis/{api}/revisions/{revision}/deployments"
           "?override=true&sequencedRollout=true")
    return Call("POST", url, None, "application/json")


def http_transport(call: Call, token: str) -> dict:
    req = urllib.request.Request(call.url, data=call.body or b"", method=call.method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Content-Type", call.content_type)
    with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310 (fixed https host)
        return json.loads(resp.read() or b"{}")


def run(org: str, env: str, api: str, proxy_dir: Path, apply: bool,
        token: str = "", transport: Transport = http_transport, out=sys.stdout) -> str | None:
    bundle = package(proxy_dir)
    print(f"bundle {api}: {len(bundle)} bytes sha256 {sha256(bundle)[:12]}", file=out)
    imp = import_call(org, api, bundle)
    if not apply:
        print(f"dry run: {imp.method} {imp.url}", file=out)
        print(f"dry run: {deploy_call(org, env, api, '<new revision>').url}", file=out)
        return None
    revision = str(transport(imp, token)["revision"])
    transport(deploy_call(org, env, api, revision), token)
    print(f"deployed {api} revision {revision} to {env}", file=out)
    return revision


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="apigee_ops.deploy")
    ap.add_argument("--org", required=True)
    ap.add_argument("--env", required=True)
    ap.add_argument("--proxy-dir", required=True, type=Path, help="directory that contains apiproxy/")
    ap.add_argument("--api", help="proxy name, defaults to the directory name")
    ap.add_argument("--apply", action="store_true", help="send the calls; without it nothing is sent")
    args = ap.parse_args(argv)
    token = ""
    if args.apply:
        token = subprocess.run(["gcloud", "auth", "print-access-token"], check=True,
                               capture_output=True, text=True).stdout.strip()
    run(args.org, args.env, args.api or args.proxy_dir.name, args.proxy_dir, args.apply, token)
    return 0


if __name__ == "__main__":
    sys.exit(main())
