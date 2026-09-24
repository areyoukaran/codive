"""
GitHub signs every webhook body with HMAC-SHA256 and sends it as
`X-Hub-Signature-256: sha256=<hex>`. This is the whole check, kept in its
own module with zero framework imports (hashlib/hmac are stdlib) so it can
be unit tested directly with a genuine and a tampered payload, with
nothing installed but Python itself.
"""
from __future__ import annotations

import hashlib
import hmac


def verify_signature(secret: str, payload: bytes, signature_header: str | None) -> bool:
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    provided = signature_header[len("sha256="):]
    # hmac.compare_digest, not `==`: a plain string comparison leaks timing
    # information about how many leading bytes matched, which is exactly
    # the side channel a signature check exists to close.
    return hmac.compare_digest(expected, provided)
