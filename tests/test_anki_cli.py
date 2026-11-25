from contextlib import redirect_stderr, redirect_stdout
from io import BytesIO, StringIO
import json
from pathlib import Path
import runpy
import unittest
from unittest.mock import patch
from urllib.error import URLError


main = runpy.run_path(str(Path(__file__).resolve().parents[1] / "anki_cli"))["main"]


class AnkiCLITests(unittest.TestCase):
    def run_cli(self, args, response=None, error=None):
        out, err = StringIO(), StringIO()
        with patch("urllib.request.urlopen", return_value=BytesIO(json.dumps(response).encode()),
                   side_effect=error) as transport, redirect_stderr(err), redirect_stdout(out):
            rc = main(args)
        self.assertGreater(transport.call_args.kwargs["timeout"], 0)
        req = transport.call_args.args[0]
        return rc, out.getvalue(), err.getvalue(), json.loads(req.data)

    def test_default_and_values_with_equals(self):
        response = {"error": None, "result": ["中文"]}
        rc, out, _, body = self.run_cli([], response)
        self.assertEqual((rc, out.strip(), body["action"]), (0, "['中文']", "deckNames"))
        rc, _, _, body = self.run_cli(["findNotes", "query=front:a=b", "cards=1  2"], response)
        self.assertEqual(rc, 0)
        self.assertEqual(body["params"], {"query": "front:a=b", "cards": ["1", "2"]})

    def test_errors_are_actionable(self):
        for response, error, expected in [
            ({"error": "deck unavailable", "result": None}, None, "deck unavailable"),
            ([], None, "invalid response"),
            (None, URLError("offline fixture"), "offline fixture"),
        ]:
            with self.subTest(expected=expected):
                rc, out, err, _ = self.run_cli([], response, error)
                self.assertEqual((rc, out), (1, ""))
                self.assertIn(expected, err)
                self.assertNotIn("Traceback", err)
