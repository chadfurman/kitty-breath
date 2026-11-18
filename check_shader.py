#!/usr/bin/env python3
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
MAC_KITTY = "/Applications/kitty.app/Contents/MacOS/kitty"
VAR = re.compile(r"^\s*var\s+(\w+)\s+(\w+)\s*=?\s*(.*?)\s*$")
TYPES = "from kitty.constants import read_kitty_resource; import sys; sys.stdout.buffer.write(read_kitty_resource('shaders/custom/types.slang'))"


def strip_comment(line):
    return re.split(r"\s#", line, maxsplit=1)[0]


def parse_groups(pipeline_text):
    top, groups, current = {}, [], None
    for raw in pipeline_text.splitlines():
        line = strip_comment(raw).strip()
        if not line or line.startswith("#"):
            continue
        if line == "startgroup":
            current = {}
        elif line == "endgroup":
            groups.append({**top, **current})
            current = None
        elif match := VAR.match(line):
            kind, name, value = match.groups()
            (top if current is None else current)[name] = (kind, value)
    return groups


def substitute(source, var_set):
    for name, (kind, value) in var_set.items():
        pattern = re.compile(rf"^static const \w+ {name}\s*=.*$", re.M)
        if not pattern.search(source):
            raise ValueError(f"no static const named {name} in the shader")
        source = pattern.sub(lambda _: f"static const {kind} {name} = {value};", source)
    return source


def find_slangc(env, kitty_exe, which=shutil.which):
    if env.get("SLANGC"):
        return env["SLANGC"]
    if kitty_exe:
        beside = Path(kitty_exe).parent / "slangc"
        if beside.exists():
            return str(beside)
    return which("slangc")


def run_kitty(kitty, code):
    try:
        return subprocess.run([kitty, "+runpy", code], capture_output=True, timeout=30, check=True).stdout
    except (OSError, subprocess.SubprocessError):
        return None


def kitty_exe_path():
    for kitty in (shutil.which("kitty"), MAC_KITTY):
        out = kitty and run_kitty(kitty, "from kitty.constants import kitty_exe; print(kitty_exe())")
        if out:
            return out.decode().strip()
    return None


def write_types(folder, kitty_exe=None):
    kitty = kitty_exe or kitty_exe_path()
    data = kitty and run_kitty(kitty, TYPES)
    if not data:
        raise RuntimeError("could not read kitty's shader types module; is kitty 0.50 or newer installed?")
    (Path(folder) / "kitty_custom_shader_types.slang").write_bytes(data)


def compile_variant(source, slangc, folder, label):
    path = Path(folder) / f"{label}.slang"
    path.write_text(source)
    result = subprocess.run([slangc, str(path), "-I", str(folder), "-o", f"{path}-module"],
                            capture_output=True, text=True, timeout=60)
    output = result.stdout + result.stderr
    return result.returncode == 0 and "error[" not in output, output


def main():
    kitty_exe = kitty_exe_path()
    slangc = find_slangc(os.environ, kitty_exe)
    if not kitty_exe or not slangc:
        print("Needs kitty 0.50+ (on PATH or in /Applications) and its slangc, or set SLANGC.", file=sys.stderr)
        return 1
    source = (HERE / "breath.slang").read_text()
    groups = parse_groups((HERE / "breath.pipeline").read_text())
    failed = 0
    with tempfile.TemporaryDirectory() as tmp:
        write_types(tmp, kitty_exe)
        for i, var_set in enumerate(groups, 1):
            ok, output = compile_variant(substitute(source, var_set), slangc, tmp, f"group{i}")
            print(f"group {i}: {'ok' if ok else 'FAILED'}")
            if not ok:
                failed += 1
                print(output, file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
