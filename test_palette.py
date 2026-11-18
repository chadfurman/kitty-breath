import io
import signal
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

import palette

PIPELINE_TEXT = (
    "textures b\n"
    "# palette:start (written by palette.py; edit palettes/*.conf instead)\n"
    "# palette: a\n"
    "var float FILL_OPACITY = 0.1\n"
    "# palette:end\n"
    "startgroup\n"
    "    shaders breath\n"
    "endgroup\n"
)


class RenderVarsTest(unittest.TestCase):
    def test_turns_a_palette_into_linear_pipeline_vars(self):
        out = palette.render_vars("violet", "fill #ffffff 0.1\nrim #000000 0.5\n")
        self.assertEqual(out, [
            "# palette: violet",
            "var float3 FILL_COLOR = float3(1.000000, 1.000000, 1.000000)",
            "var float FILL_OPACITY = 0.1",
            "var float3 RIM_COLOR = float3(0.000000, 0.000000, 0.000000)",
            "var float RIM_OPACITY = 0.5",
        ])


class ReplaceBlockTest(unittest.TestCase):
    def test_replaces_lines_between_the_markers(self):
        text = "a\n# palette:start (x)\nold\n# palette:end\nb\n"
        self.assertEqual(palette.replace_block(text, ["new"]), "a\n# palette:start (x)\nnew\n# palette:end\nb\n")

    def test_reads_the_current_palette_name(self):
        self.assertEqual(palette.current_name("x\n# palette: dusk\ny\n"), "dusk")
        self.assertIsNone(palette.current_name("x\n"))


class NamesTest(unittest.TestCase):
    def test_lists_palettes_sorted_by_stem(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name in ("2-b.conf", "1-a.conf", "notes.txt", "3-c.conf"):
                (Path(tmp) / name).write_text("")
            self.assertEqual(palette.names(Path(tmp)), ["1-a", "2-b", "3-c"])

    def test_cycles_to_the_next_palette_and_wraps(self):
        all_names = ["a", "b", "c"]
        self.assertEqual(palette.next_name(all_names, "a"), "b")
        self.assertEqual(palette.next_name(all_names, "c"), "a")
        self.assertEqual(palette.next_name(all_names, "zzz"), "a")
        self.assertEqual(palette.next_name(all_names, None), "a")


class ReloadTest(unittest.TestCase):
    def test_reload_signals_kitty_pid(self):
        kill = mock.Mock()
        self.assertTrue(palette.reload_kitty({"KITTY_PID": "42"}, kill=kill))
        kill.assert_called_once_with(42, signal.SIGUSR1)

    def test_reload_without_kitty_pid_prints_how(self):
        kill = mock.Mock()
        for env in ({}, {"KITTY_PID": "abc"}, {"KITTY_PID": "0"}, {"KITTY_PID": "-5"}):
            self.assertFalse(palette.reload_kitty(env, kill=kill))
        kill.assert_not_called()
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict("os.environ", {}, clear=True):
            folder = make_clone(Path(tmp))
            out = run_main(folder, ["b"])
        self.assertIn("ctrl+shift+f5", out.stdout)
        self.assertIn("ctrl+cmd+,", out.stdout)


class MainTest(unittest.TestCase):
    def test_main_rewrites_only_the_palette_block(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict("os.environ", {}, clear=True):
            folder = make_clone(Path(tmp))
            out = run_main(folder, ["b"])
            text = (folder / "breath.pipeline").read_text()
        self.assertEqual(out.code, 0)
        self.assertIn("palette: b\n", out.stdout)
        expected = PIPELINE_TEXT.replace(
            "# palette: a\nvar float FILL_OPACITY = 0.1\n",
            "# palette: b\nvar float3 FILL_COLOR = float3(1.000000, 1.000000, 1.000000)\nvar float FILL_OPACITY = 0.2\n",
        )
        self.assertEqual(text, expected)

    def test_main_rejects_an_unknown_palette(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict("os.environ", {}, clear=True):
            folder = make_clone(Path(tmp))
            out = run_main(folder, ["nope"])
            text = (folder / "breath.pipeline").read_text()
        self.assertEqual(out.code, 1)
        self.assertEqual(text, PIPELINE_TEXT)
        self.assertIn("a, b", out.stderr)


class Result:
    def __init__(self, code, stdout, stderr):
        self.code, self.stdout, self.stderr = code, stdout, stderr


def make_clone(folder):
    (folder / "palettes").mkdir()
    (folder / "palettes" / "a.conf").write_text("fill #000000 0.1\n")
    (folder / "palettes" / "b.conf").write_text("fill #ffffff 0.2\n")
    (folder / "breath.pipeline").write_text(PIPELINE_TEXT)
    return folder


def run_main(folder, args):
    out, err = io.StringIO(), io.StringIO()
    with mock.patch.object(palette, "PALETTES", folder / "palettes"), \
            mock.patch.object(palette, "PIPELINE", folder / "breath.pipeline"), \
            redirect_stdout(out), redirect_stderr(err):
        code = palette.main(args)
    return Result(code, out.getvalue(), err.getvalue())


class LocationTest(unittest.TestCase):
    def test_finds_files_next_to_itself(self):
        here = Path(palette.__file__).resolve().parent
        self.assertEqual(palette.HERE, here)
        self.assertEqual(palette.PALETTES, here / "palettes")
        self.assertEqual(palette.PIPELINE, here / "breath.pipeline")


if __name__ == "__main__":
    unittest.main()
