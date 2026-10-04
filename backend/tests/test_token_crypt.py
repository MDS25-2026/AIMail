"""Gmail refresh tokens are stored encrypted, bound to their owner, and readable by the listener.

AES-256-GCM with the user's id as associated data: a token copied onto another user's row will not
decrypt. The same sealed vector is checked here and in the listener's Go tests, so both languages
agree on the format.
"""

import base64
import json
from pathlib import Path

import pytest

from app.core import token_crypt
from app.core.config import get_settings

VECTOR = json.loads((Path(__file__).resolve().parents[2] / "listener/testdata/token_vector.json").read_text())


@pytest.fixture(autouse=True)
def _key(monkeypatch, test_settings):
    monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", VECTOR["key"])
    get_settings.cache_clear()


def test_a_token_round_trips_for_its_owner():
    sealed = token_crypt.seal("1//refresh-token", "user-a")
    assert b"1//refresh-token" not in sealed
    assert token_crypt.unseal(sealed, "user-a") == "1//refresh-token"


def test_sealing_twice_gives_different_ciphertext():
    assert token_crypt.seal("same", "user-a") != token_crypt.seal("same", "user-a")


def test_a_token_moved_to_another_user_does_not_decrypt():
    sealed = token_crypt.seal("1//refresh-token", "user-a")
    with pytest.raises(token_crypt.TokenDecryptError):
        token_crypt.unseal(sealed, "user-b")


def test_a_tampered_token_does_not_decrypt():
    sealed = bytearray(token_crypt.seal("1//refresh-token", "user-a"))
    sealed[-1] ^= 0x01
    with pytest.raises(token_crypt.TokenDecryptError):
        token_crypt.unseal(bytes(sealed), "user-a")


@pytest.mark.parametrize("key", ["", "c2hvcnQ=", "not base64!!"])
def test_a_missing_or_malformed_key_refuses_to_run(monkeypatch, key):
    monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", key)
    get_settings.cache_clear()
    with pytest.raises(token_crypt.TokenKeyError):
        token_crypt.seal("x", "user-a")


def test_the_shared_vector_decrypts_so_the_listener_and_backend_agree():
    sealed = base64.b64decode(VECTOR["sealed"])
    assert token_crypt.unseal(sealed, VECTOR["user_id"]) == VECTOR["plaintext"]
