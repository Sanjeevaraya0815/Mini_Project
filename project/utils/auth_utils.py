import hashlib
import hmac
import os


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    hashed = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 120000)
    return f"{salt.hex()}${hashed.hex()}"


def verify_password(password: str, stored_value: str) -> bool:
    try:
        salt_hex, hash_hex = stored_value.split("$")
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(hash_hex)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 120000)
        return hmac.compare_digest(expected, actual)
    except (ValueError, TypeError):
        return False
