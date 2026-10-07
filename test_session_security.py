import concurrent.futures
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from session_security import load_session_secret


class SessionSecurityTests(unittest.TestCase):
    def test_configured_key_takes_precedence_without_creating_file(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {'SECRET_KEY': 'configured-test-key'}):
                self.assertEqual(load_session_secret(directory), 'configured-test-key')
            self.assertFalse((Path(directory) / '.session-secret').exists())

    def test_key_survives_reload_and_is_private(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {}, clear=True):
                first = load_session_secret(directory)
                self.assertEqual(load_session_secret(directory), first)
            self.assertEqual(len(first), 64)
            self.assertEqual((Path(directory) / '.session-secret').stat().st_mode & 0o777, 0o600)

    def test_concurrent_workers_share_one_key(self):
        with tempfile.TemporaryDirectory() as directory:
            environment = dict(os.environ)
            environment.pop('SECRET_KEY', None)
            command = [sys.executable, '-c',
                       'from session_security import load_session_secret; '
                       'import sys; print(load_session_secret(sys.argv[1]))', directory]
            with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
                keys = list(pool.map(lambda _: subprocess.check_output(
                    command, env=environment, text=True).strip(), range(16)))
            self.assertEqual(len(set(keys)), 1)


if __name__ == '__main__':
    unittest.main()
