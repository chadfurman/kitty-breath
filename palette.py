#!/usr/bin/env python3
import re
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


def current_name(text):
    match = re.search(r"^# palette: (\S+)$", text, re.M)
    return match.group(1) if match else None
