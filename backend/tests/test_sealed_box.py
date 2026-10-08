"""Key rotation: format 2 names the key a value was sealed with, so a keyring can hold old and new.

The keyring vectors are shared with the listener: each side seals under two key ids and "legacy",
copies in its format 1 vectors, and both sides must open both files.
"""

import base64
import json
import os
from pathlib import Path
from uuid import UUID

import pytest

from app.core import sealed_box, token_crypt, vault
from app.core.config import get_settings

TESTDATA = Path(__file__).resolve().parents[2] / "listener" / "testdata"
VECTOR_FILES = ["keyring_vector_go.json", "keyring_vector_python.json"]
# Test-only keys, the same as the listener's keyring_vector_test.go: bytes 0x20..0x3f and 0x40..0x5f.
K1 = base64.b64encode(bytes(range(0x20, 0x40))).decode()
K2 = base64.b64encode(bytes(range(0x40, 0x60))).decode()
SETTINGS = sealed_box.KeySettings(ring="RING", legacy="LEGACY")
OWNER = "aaaaaaaa-0000-4000-8000-000000000001"


def _use_keys(monkeypatch, ring: str, token_legacy: str, vault_legacy: str) -> None:
    monkeypatch.setenv("TOKEN_ENCRYPTION_KEYS", ring)
    monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", token_legacy)
    monkeypatch.setenv("PII_VAULT_KEYS", ring)
    monkeypatch.setenv("PII_VAULT_KEY", vault_legacy)
    get_settings.cache_clear()


def test_the_first_ring_entry_is_primary_and_the_old_key_is_legacy():
    keyring = sealed_box.parse_keyring(f"k2:{K2},k1:{K1}", K1, SETTINGS)
    assert keyring.primary == "k2"
    assert set(keyring.keys) == {"k2", "k1", "legacy"}


def test_the_old_key_alone_is_the_legacy_primary():
    assert sealed_box.parse_keyring("", K1, SETTINGS).primary == "legacy"


@pytest.mark.parametrize(("ring", "legacy"), [
    ("", ""),
    ("", "c2hvcnQ="),
    ("", "not base64!!"),
    (K1, ""),
    (f":{K1}", ""),
    (f"k1:{K1},k1:{K2}", ""),
    ("k" * 256 + f":{K1}", ""),
    (f"legacy:{K1}", K2),
])
def test_a_bad_keyring_is_refused_without_echoing_a_key(ring, legacy):
    with pytest.raises(sealed_box.SealKeyError) as raised:
        sealed_box.parse_keyring(ring, legacy, SETTINGS)
    assert K1 not in str(raised.value) and K2 not in str(raised.value)


def test_a_new_seal_is_format_2_under_the_primary_key():
    keyring = sealed_box.parse_keyring(f"k2:{K2},k1:{K1}", "", SETTINGS)
    sealed = sealed_box.seal(b"secret", b"aad", keyring)
    assert sealed[0] == sealed_box.FORMAT_V2 and sealed_box.split_sealed(sealed)[0] == "k2"
    assert sealed_box.unseal(sealed, b"aad", keyring) == b"secret"


def test_a_value_under_a_key_the_ring_no_longer_holds_does_not_open():
    sealed = sealed_box.seal(b"secret", b"aad", sealed_box.parse_keyring(f"k2:{K2}", "", SETTINGS))
    with pytest.raises(sealed_box.SealOpenError, match="k2"):
        sealed_box.unseal(sealed, b"aad", sealed_box.parse_keyring(f"k1:{K1}", "", SETTINGS))


@pytest.mark.parametrize("sealed", [b"", b"\x03" + bytes(40), b"\x02\x00" + bytes(40), b"\x02\x09k1"])
def test_a_malformed_header_is_refused(sealed):
    with pytest.raises(sealed_box.SealOpenError):
        sealed_box.split_sealed(sealed)


@pytest.mark.parametrize("name", VECTOR_FILES)
def test_both_languages_keyring_vectors_open(monkeypatch, test_settings, name):
    vector = json.loads((TESTDATA / name).read_text())
    _use_keys(monkeypatch, vector["ring"], vector["token_legacy"], vector["vault_legacy"])
    for case in vector["tokens"]:
        sealed = base64.b64decode(case["sealed"])
        assert (sealed[0], sealed_box.split_sealed(sealed)[0]) == (case["format"], case["kid"])
        assert token_crypt.unseal(sealed, case["user_id"]) == case["plaintext"]
    for case in vector["vaults"]:
        sealed = base64.b64decode(case["sealed"])
        assert (sealed[0], sealed_box.split_sealed(sealed)[0]) == (case["format"], case["kid"])
        assert vault.open_vault(sealed, UUID(case["owner"]), case["gmail_message_id"]) == case["details"]


def _token_case(monkeypatch, ring: str, legacy: str, kid: str) -> dict:
    _use_keys(monkeypatch, ring, legacy, "")
    plaintext = f"1//test-refresh-token-under-{kid}"
    sealed = token_crypt.seal(plaintext, OWNER)
    return {"kid": kid, "format": 2, "user_id": OWNER, "plaintext": plaintext,
            "sealed": base64.b64encode(sealed).decode()}


def _vault_case(monkeypatch, details: dict[str, str]) -> dict:
    _use_keys(monkeypatch, f"k1:{K1}", "", "")
    sealed = vault.seal_vault(details, UUID(OWNER), "gm-keyring")
    return {"kid": "k1", "format": 2, "owner": OWNER, "gmail_message_id": "gm-keyring", "details": details,
            "sealed": base64.b64encode(sealed).decode()}


@pytest.mark.skipif(not os.getenv("WRITE_KEYRING_VECTOR"), reason="set WRITE_KEYRING_VECTOR=1 to regenerate")
def test_write_python_keyring_vector(monkeypatch, test_settings):
    token = json.loads((TESTDATA / "token_vector.json").read_text())
    old_vault = json.loads((TESTDATA / "vault_vector_python.json").read_text())
    ring = f"k2:{K2},k1:{K1}"
    vector = {
        "_comment": "Test-only keys, sealed by the backend's Python; never used for real data.",
        "ring": ring, "token_legacy": token["key"], "vault_legacy": old_vault["key"],
        "tokens": [
            {"kid": "legacy", "format": 1, "user_id": token["user_id"], "plaintext": token["plaintext"],
             "sealed": token["sealed"]},
            _token_case(monkeypatch, ring, "", "k2"),
            _token_case(monkeypatch, f"k1:{K1}", "", "k1"),
            _token_case(monkeypatch, "", token["key"], "legacy"),
        ],
        "vaults": [
            {"kid": "legacy", "format": 1, "owner": old_vault["owner"], "gmail_message_id": old_vault["gmail_message_id"],
             "details": old_vault["details"], "sealed": old_vault["sealed"]},
            _vault_case(monkeypatch, old_vault["details"]),
        ],
    }
    (TESTDATA / "keyring_vector_python.json").write_text(json.dumps(vector, indent=2, ensure_ascii=False) + "\n")
