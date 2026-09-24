import hashlib
import hmac

from app.core.webhook_verify import verify_signature

SECRET = "test-webhook-secret"
BODY = b'{"action":"opened","repository":{"full_name":"atlas/api"}}'


def _sign(secret: str, body: bytes) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def test_valid_signature_is_accepted():
    sig = _sign(SECRET, BODY)
    assert verify_signature(SECRET, BODY, sig) is True


def test_tampered_body_is_rejected():
    sig = _sign(SECRET, BODY)
    tampered = BODY.replace(b"opened", b"closed")
    assert verify_signature(SECRET, tampered, sig) is False


def test_wrong_secret_is_rejected():
    sig = _sign("a-different-secret", BODY)
    assert verify_signature(SECRET, BODY, sig) is False


def test_missing_header_is_rejected():
    assert verify_signature(SECRET, BODY, None) is False
    assert verify_signature(SECRET, BODY, "") is False


def test_malformed_header_is_rejected():
    assert verify_signature(SECRET, BODY, "not-the-right-format") is False
    assert verify_signature(SECRET, BODY, "sha1=deadbeef") is False  # GitHub's older, weaker scheme - must not be accepted


def test_signature_for_different_secret_length_does_not_crash():
    # hmac.compare_digest requires equal-length inputs in some historical
    # implementations; verify a short, malformed hex value doesn't raise.
    assert verify_signature(SECRET, BODY, "sha256=ab") is False
