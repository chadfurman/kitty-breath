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


class LocationTest(unittest.TestCase):
    def test_finds_files_next_to_itself(self):
        here = Path(palette.__file__).resolve().parent
        self.assertEqual(palette.HERE, here)
        self.assertEqual(palette.PALETTES, here / "palettes")
        self.assertEqual(palette.PIPELINE, here / "breath.pipeline")


if __name__ == "__main__":
    unittest.main()
