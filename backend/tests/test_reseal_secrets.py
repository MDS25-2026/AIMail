"""After a rotation, values under an old key are sealed again under the primary; current ones are left alone."""

import base64
from uuid import UUID

import pytest

from app.core import sealed_box, token_crypt, vault
from app.core.config import get_settings
from scripts.reseal_secrets import reseal_token, reseal_vault

OLD = base64.b64encode(bytes(range(32))).decode()
NEW = base64.b64encode(bytes(range(32, 64))).decode()
OWNER = UUID("aaaaaaaa-0000-4000-8000-000000000001")


def _keys(monkeypatch, ring: str, legacy: str) -> None:
    for prefix in ("TOKEN_ENCRYPTION_KEY", "PII_VAULT_KEY"):
        monkeypatch.setenv(f"{prefix}S", ring)
        monkeypatch.setenv(prefix, legacy)
    get_settings.cache_clear()


@pytest.fixture
def rotated(monkeypatch, test_settings) -> tuple[bytes, bytes]:
    """A token and a vault sealed under the old single key, then a ring with a new primary."""
    _keys(monkeypatch, "", OLD)
    sealed_token = token_crypt.seal("1//refresh", str(OWNER))
    sealed_vault = vault.seal_vault({"[PERSON_1]": "Aisyah"}, OWNER, "gm-1")
    _keys(monkeypatch, f"new:{NEW}", OLD)
    return sealed_token, sealed_vault


def test_a_token_under_the_old_key_moves_to_the_primary(rotated):
    resealed = reseal_token(rotated[0], str(OWNER), "new")
    assert sealed_box.split_sealed(resealed)[0] == "new"
    assert token_crypt.unseal(resealed, str(OWNER)) == "1//refresh"
    assert reseal_token(resealed, str(OWNER), "new") is None


def test_a_vault_under_the_old_key_moves_to_the_primary(rotated):
    resealed = reseal_vault(rotated[1], OWNER, "gm-1", "new")
    assert sealed_box.split_sealed(resealed)[0] == "new"
    assert vault.open_vault(resealed, OWNER, "gm-1") == {"[PERSON_1]": "Aisyah"}
    assert reseal_vault(resealed, OWNER, "gm-1", "new") is None


def test_a_value_for_another_owner_is_refused_not_resealed(rotated):
    with pytest.raises(token_crypt.TokenDecryptError):
        reseal_token(rotated[0], "someone-else", "new")
