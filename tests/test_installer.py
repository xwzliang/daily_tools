import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


class InstallerTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        self.repo = root / "daily tools"
        self.repo.mkdir()
        self.target = root / "personal bin"
        self.installer = self.repo / "install.sh"
        shutil.copy2(Path(__file__).resolve().parents[1] / "install.sh", self.installer)
        (self.repo / "my utility").write_text("fixture")
        (self.repo / "second").write_text("second")
        (self.repo / "README.md").write_text("readme")
        (self.repo / "test_fixture.py").touch()
        (self.repo / "application").mkdir()

    def invoke(self, *args):
        return subprocess.run([str(self.installer), "--target", str(self.target), *args],
                              capture_output=True, text=True)

    def test_preview_then_install_and_repeat(self):
        preview = self.invoke("--dry-run")
        self.assertEqual(preview.returncode, 0, preview.stderr)
        self.assertFalse(self.target.exists())
        self.assertIn("my utility", preview.stdout)
        self.target.mkdir()
        orphan = self.target / "another project's broken link"
        orphan.symlink_to("missing")
        self.assertEqual(self.invoke().returncode, 0)
        self.assertEqual(self.invoke().returncode, 0)
        self.assertEqual(os.readlink(orphan), "missing")
        self.assertTrue((self.target / "my utility").samefile(self.repo / "my utility"))
        self.assertEqual(sorted(p.name for p in self.target.iterdir()), [orphan.name, "my utility", "second"])

    def test_preflight_preserves_conflicts_and_other_names(self):
        for kind in ("file", "directory", "symlink"):
            with self.subTest(kind=kind):
                self.target.mkdir(exist_ok=True)
                item = self.target / "second"
                if kind == "file":
                    item.write_text("personal")
                elif kind == "directory":
                    item.mkdir()
                else:
                    item.symlink_to("other target")
                result = self.invoke()
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(str(item), result.stderr)
                self.assertFalse((self.target / "my utility").exists())
                if kind == "directory":
                    self.assertEqual(list(item.iterdir()), [])
                    item.rmdir()
                else:
                    if kind == "file":
                        self.assertEqual(item.read_text(), "personal")
                    else:
                        self.assertEqual(os.readlink(item), "other target")
                    item.unlink()
