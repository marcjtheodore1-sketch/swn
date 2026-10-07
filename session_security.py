"""Keep Flask sessions valid across workers and application reloads."""

import fcntl
import os
from pathlib import Path
import secrets


def load_session_secret(instance_path):
    """Use the configured secret, or persist a private installation-specific key."""
    configured = os.environ.get('SECRET_KEY')
    if configured:
        return configured

    directory = Path(instance_path)
    directory.mkdir(parents=True, exist_ok=True)
    key_path = directory / '.session-secret'
    descriptor = os.open(key_path, os.O_CREAT | os.O_RDWR, 0o600)
    with os.fdopen(descriptor, 'r+') as key_file:
        # Workers can start together. Hold the lock until the new key is flushed.
        fcntl.flock(key_file, fcntl.LOCK_EX)
        key = key_file.read().strip()
        if not key:
            key = secrets.token_hex(32)
            key_file.write(key)
            key_file.flush()
            os.fsync(key_file.fileno())
        return key
