#!/usr/bin/env python3
"""Prints two random values to paste into .env / your host's environment
variables. Run it once per deployment — don't reuse the same keys across
environments, and don't commit the output.

    python3 scripts/gen-keys.py
"""
import secrets
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cryptography.fernet import Fernet  # noqa: E402

if __name__ == "__main__":
    print(f"SECRET_KEY={secrets.token_urlsafe(48)}")
    print(f"TOKEN_ENCRYPTION_KEY={Fernet.generate_key().decode()}")
    print(f"GITHUB_WEBHOOK_SECRET={secrets.token_urlsafe(32)}")
