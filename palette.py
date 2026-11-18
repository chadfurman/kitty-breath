#!/usr/bin/env python3
import os
import re
import signal
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PALETTES = HERE / "palettes"
PIPELINE = HERE / "breath.pipeline"


def to_linear(hex_color):
    channels = [int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    return [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]


def render_vars(name, palette_text):
    lines = [f"# palette: {name}"]
    for row in palette_text.split("\n"):
        if not row.strip():
            continue
        layer, color, opacity = row.split()
        rgb = ", ".join(f"{c:.6f}" for c in to_linear(color))
        lines += [f"var float3 {layer.upper()}_COLOR = float3({rgb})", f"var float {layer.upper()}_OPACITY = {opacity}"]
    return lines


def replace_block(text, lines):
    pattern = re.compile(r"(# palette:start[^\n]*\n).*?(# palette:end)", re.S)
    return pattern.sub(lambda m: m.group(1) + "".join(f"{line}\n" for line in lines) + m.group(2), text)


def has_block(text):
    return re.search(r"^# palette:start.*?^# palette:end", text, re.S | re.M) is not None


def current_name(text):
    match = re.search(r"^# palette: (\S+)$", text, re.M)
    return match.group(1) if match else None


def names(folder=PALETTES):
    return sorted(p.stem for p in folder.glob("*.conf"))


def next_name(all_names, current):
    if current not in all_names:
        return all_names[0]
    return all_names[(all_names.index(current) + 1) % len(all_names)]


def process_name(pid):
    try:
        out = subprocess.run(["ps", "-p", str(pid), "-o", "comm="], capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return ""
    return os.path.basename(out.stdout.strip())


def reload_kitty(env=os.environ, kill=None, parent=os.getppid, name_of=None):
    kill, name_of = kill or os.kill, name_of or process_name
    pid = env.get("KITTY_PID", "")
    candidates = [int(pid)] if pid.isdigit() and int(pid) > 0 else []
    for target in candidates + [parent()]:
        if name_of(target) != "kitty":
            continue
        try:
            kill(target, signal.SIGUSR1)
        except OSError:
            return False
        return True
    return False


def main(args):
    all_names = names(PALETTES)
    if args and args[0] not in all_names:
        print(f"unknown palette: {args[0]} (have: {', '.join(all_names)})", file=sys.stderr)
        return 1
    text = PIPELINE.read_text()
    if not has_block(text):
        print(f"{PIPELINE.name} has no # palette:start / # palette:end block to write into", file=sys.stderr)
        return 1
    name = args[0] if args else next_name(all_names, current_name(text))
    lines = render_vars(name, (PALETTES / f"{name}.conf").read_text())
    PIPELINE.write_text(replace_block(text, lines))
    print(f"palette: {name}")
    if not reload_kitty():
        print("Reload kitty's config to see it: ctrl+shift+f5, or ctrl+cmd+, on macOS.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
