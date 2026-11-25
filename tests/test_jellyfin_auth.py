import os
from pathlib import Path
import subprocess
import tempfile
import unittest


COMMAND = Path(__file__).resolve().parents[1] / "jellyfin_api"


class JellyfinAuthTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name)
        curl = self.folder / "curl"
        curl.write_text("""#!/bin/sh
set -eu
echo invoked >> "$FIXTURE_LOG"
case "$*" in *fixture-secret*) exit 41;; esac
test -z "${JELLYFIN_TOKEN:-}"
test "$1" = "-H"
test "$2" = "@-"
read -r header
if [ "${EXPECT_LOCAL_DEFAULT:-}" = 1 ]; then
  case "$header" in "X-MediaBrowser-Token: "?*) ;; *) exit 43 ;; esac
else
  test "$header" = "X-MediaBrowser-Token: fixture-secret"
fi
case "$*" in
  *Seasons*) echo '{"Items":[{"IndexNumber":1,"Id":"season"}]}' ;;
  *ParentId=season*) echo '{"Items":[{"IndexNumber":1,"Id":"episode"}]}' ;;
  *) exit 42 ;;
esac
""")
        curl.chmod(0o700)
        self.env = {**os.environ, "PATH": str(self.folder) + os.pathsep + os.environ["PATH"],
                    "FIXTURE_LOG": str(self.folder / "calls")}
        self.env.pop("JELLYFIN_TOKEN", None)

    def invoke(self, *args):
        return subprocess.run([str(COMMAND), "--series", "series", "--user", "user", "--end", "1",
                               "--url", "http://fixture.invalid", "--dry-run", *args],
                              env=self.env, capture_output=True, text=True)

    def test_missing_and_multiline_credentials_never_request(self):
        for value in ("", "bad\nheader"):
            self.env["JELLYFIN_TOKEN"] = value
            result = self.invoke()
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("JELLYFIN_TOKEN", result.stderr)
            self.assertFalse((self.folder / "calls").exists())

    def test_local_server_uses_its_default(self):
        self.env["EXPECT_LOCAL_DEFAULT"] = "1"
        result = self.invoke("--url", "http://imac.local:8096")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Would WATCH episode", result.stdout)

    def test_token_passed_privately_to_both_requests(self):
        for args in ([], ["--token", "fixture-secret"]):
            self.env["JELLYFIN_TOKEN"] = "unused" if args else "fixture-secret"
            result = self.invoke(*args)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Would WATCH episode", result.stdout)
            self.assertNotIn("fixture-secret", result.stdout + result.stderr)
        self.assertEqual((self.folder / "calls").read_text().splitlines(), ["invoked"] * 4)
