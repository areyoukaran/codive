import os

os.environ.setdefault("TOKEN_ENCRYPTION_KEY", "dGVzdC1lbmNyeXB0aW9uLWtleS1mb3ItcHl0ZXN0LSE=")

from app.core.config import get_settings  # noqa: E402
from app.core.security import decrypt_secret, encrypt_secret, generate_fernet_key  # noqa: E402

get_settings.cache_clear()


def test_round_trip():
    plaintext = "ghu_ABCDEF1234567890fakeGitHubToken"
    ciphertext = encrypt_secret(plaintext)
    assert ciphertext != plaintext
    assert decrypt_secret(ciphertext) == plaintext


def test_ciphertext_does_not_contain_plaintext():
    plaintext = "ghu_supersecrettoken"
    ciphertext = encrypt_secret(plaintext)
    assert plaintext not in ciphertext


def test_tampered_ciphertext_fails_to_decrypt():
    ciphertext = encrypt_secret("a-token")
    tampered = ciphertext[:-4] + ("A" if ciphertext[-4] != "A" else "B") + ciphertext[-3:]
    assert decrypt_secret(tampered) is None


def test_generate_fernet_key_is_usable():
    key = generate_fernet_key()
    os.environ["TOKEN_ENCRYPTION_KEY"] = key
    get_settings.cache_clear()
    ciphertext = encrypt_secret("round trip with a freshly generated key")
    assert decrypt_secret(ciphertext) == "round trip with a freshly generated key"
    # restore for any later test in the same process
    os.environ["TOKEN_ENCRYPTION_KEY"] = "dGVzdC1lbmNyeXB0aW9uLWtleS1mb3ItcHl0ZXN0LSE="
    get_settings.cache_clear()
