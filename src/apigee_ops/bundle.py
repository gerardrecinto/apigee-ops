"""Package an Apigee proxy directory into a deployable zip, byte-for-byte reproducible."""
from __future__ import annotations

import hashlib
import io
import zipfile
from pathlib import Path

_FIXED_TIME = (1980, 1, 1, 0, 0, 0)
_SKIP = {".gitkeep", ".DS_Store"}


def package(proxy_dir: Path) -> bytes:
    """proxy_dir contains apiproxy/. Same input always gives the same bytes, so a rebuild can be diffed."""
    root = Path(proxy_dir)
    if not (root / "apiproxy").is_dir():
        raise FileNotFoundError(f"{root}/apiproxy not found")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for path in sorted(p for p in (root / "apiproxy").rglob("*") if p.is_file() and p.name not in _SKIP):
            info = zipfile.ZipInfo(path.relative_to(root).as_posix(), _FIXED_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            z.writestr(info, path.read_bytes())
    return buf.getvalue()


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
