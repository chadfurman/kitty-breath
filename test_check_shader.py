import os
import re
import tempfile
import unittest
from pathlib import Path

import check_shader
import palette

HERE = Path(__file__).resolve().parent
SHADER = (HERE / "breath.slang").read_text() if (HERE / "breath.slang").exists() else ""
OLD_NAMES = ["SKY" + "_KEY", "sky" + "-debug", "shaders " + "sky"]

SMALL_PIPELINE = """textures b
var float LAG = 1.2
# palette:start (written by palette.py)
# palette: x
var float3 TINT = float3(1, 0, 0)  # red
# palette:end

startgroup
    output_texture b
    shaders breath
endgroup

startgroup
    var int MODE = 4
    var float LAG = 0.5
    shaders breath
endgroup
"""


def tools():
    exe = check_shader.kitty_exe_path()
    return exe, check_shader.find_slangc(os.environ, exe)


class ParseGroupsTest(unittest.TestCase):
    def test_parses_one_var_set_per_group(self):
        groups = check_shader.parse_groups(SMALL_PIPELINE)
        self.assertEqual(groups, [
            {"LAG": ("float", "1.2"), "TINT": ("float3", "float3(1, 0, 0)")},
            {"LAG": ("float", "0.5"), "TINT": ("float3", "float3(1, 0, 0)"), "MODE": ("int", "4")},
        ])


class SubstituteTest(unittest.TestCase):
    def test_substitutes_a_static_const(self):
        source = "a\nstatic const int MODE = 0;  // modes\nstatic const float X = 1.0;\nb\n"
        out = check_shader.substitute(source, {"MODE": ("int", "4")})
        self.assertEqual(out, "a\nstatic const int MODE = 4;\nstatic const float X = 1.0;\nb\n")

    def test_substitute_rejects_a_var_with_no_const(self):
        with self.assertRaisesRegex(ValueError, "NOPE"):
            check_shader.substitute("static const int MODE = 0;\n", {"NOPE": ("int", "1")})


class ShippedFilesTest(unittest.TestCase):
    def test_every_pipeline_var_names_a_shader_const(self):
        consts = dict((name, kind) for kind, name in re.findall(r"^static const (\w+) (\w+)\s*=", SHADER, re.M))
        wanted = {}
        for group in check_shader.parse_groups((HERE / "breath.pipeline").read_text()):
            wanted.update(group)
        for name in palette.names(palette.PALETTES):
            text = (palette.PALETTES / f"{name}.conf").read_text()
            for line in palette.render_vars(name, text)[1:]:
                _, kind, var, _ = line.split(" ", 3)
                wanted[var] = (kind, "")
        self.assertTrue(wanted)
        for var, (kind, _) in wanted.items():
            self.assertEqual(consts.get(var), kind, var)

    def test_no_sky_names_left(self):
        for path in HERE.rglob("*"):
            if not path.is_file() or {".git", "__pycache__"} & set(path.relative_to(HERE).parts):
                continue
            text = path.read_text(errors="ignore")
            for old in OLD_NAMES:
                self.assertNotIn(old, text, f"{old} in {path.name}")

    def test_sidebar_walk_only_in_sidebar_mode(self):
        calls = [line for line in SHADER.splitlines() if "mouse_in_sidebar(" in line and not line.startswith("bool ")]
        self.assertTrue(calls)
        for line in calls:
            self.assertIn("REGION == REGION_SIDEBAR", line)


class FindSlangcTest(unittest.TestCase):
    def test_finds_slangc(self):
        with tempfile.TemporaryDirectory() as tmp:
            beside = Path(tmp) / "slangc"
            beside.write_text("")
            exe = str(Path(tmp) / "kitty")
            on_path = lambda name: "/usr/bin/slangc"
            nowhere = lambda name: None
            self.assertEqual(check_shader.find_slangc({"SLANGC": "/x/slangc"}, exe, on_path), "/x/slangc")
            self.assertEqual(check_shader.find_slangc({}, exe, on_path), str(beside))
            self.assertEqual(check_shader.find_slangc({}, None, on_path), "/usr/bin/slangc")
            self.assertIsNone(check_shader.find_slangc({}, None, nowhere))


class CompileTest(unittest.TestCase):
    def setUp(self):
        self.exe, self.slangc = tools()
        if not self.exe or not self.slangc:
            self.skipTest("kitty or its slangc was not found")
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self.tmp.name)
        check_shader.write_types(self.folder)

    def tearDown(self):
        self.tmp.cleanup()

    def test_shader_compiles_for_every_group(self):
        groups = check_shader.parse_groups((HERE / "breath.pipeline").read_text())
        variants = groups + [dict(groups[1], REGION=("int", "1"))]
        for i, var_set in enumerate(variants):
            ok, output = check_shader.compile_variant(
                check_shader.substitute(SHADER, var_set), self.slangc, self.folder, f"group{i}")
            self.assertTrue(ok, output)

    def test_compile_reports_a_broken_shader(self):
        broken = SHADER.replace("return color;", "return colour_missing;", 1)
        ok, output = check_shader.compile_variant(broken, self.slangc, self.folder, "broken")
        self.assertFalse(ok)
        self.assertIn("error[", output)


if __name__ == "__main__":
    unittest.main()
