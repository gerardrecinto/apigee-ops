from datetime import datetime, timedelta, timezone

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

NOW = datetime(2026, 11, 24, 12, 0, tzinfo=timezone.utc)


def _key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def key_pem(key) -> bytes:
    return key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                             serialization.NoEncryption())


def make_cert(cn="api.example.com", sans=("api.example.com",), days=90, start_offset=-1,
              key=None, issuer_cert=None, issuer_key=None, ca=False):
    key = key or _key()
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, cn)])
    issuer = issuer_cert.subject if issuer_cert else subject
    signer = issuer_key or key
    not_before = NOW + timedelta(days=start_offset)
    b = (x509.CertificateBuilder().subject_name(subject).issuer_name(issuer)
         .public_key(key.public_key()).serial_number(x509.random_serial_number())
         .not_valid_before(not_before).not_valid_after(NOW + timedelta(days=days))
         .add_extension(x509.BasicConstraints(ca=ca, path_length=None), critical=True))
    if sans:
        b = b.add_extension(x509.SubjectAlternativeName([x509.DNSName(s) for s in sans]), critical=False)
    return b.sign(signer, hashes.SHA256()), key


def pem(*certs) -> bytes:
    return b"".join(c.public_bytes(serialization.Encoding.PEM) for c in certs)


class MemoryStore:
    def __init__(self):
        self.versions: dict[str, list[bytes]] = {}

    def latest(self, name):
        v = self.versions.get(name)
        return v[-1] if v else None

    def add_version(self, name, payload):
        self.versions.setdefault(name, []).append(payload)


@pytest.fixture
def store():
    return MemoryStore()
