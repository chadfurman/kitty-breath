# kitty-breath

A slow light that breathes around your mouse pointer in [kitty](https://sw.kovidgoyal.net/kitty/). It follows the 4-7-8 pattern: it grows for 4 seconds, holds for 7 while an inner light counts out the hold, and shrinks for 8. Only the plain background changes, so text never does. A key press can also send one soft sigh across the window.

## Quick start

You need kitty 0.50 or newer. The palette switcher also needs python3.

```sh
git clone https://github.com/chadfurman/kitty-breath ~/src/kitty-breath
```

Add this to your `kitty.conf`:

```conf
custom_shaders ~/src/kitty-breath/breath

# Optional: a sigh on F12, and the debug view on F11.
map f12 shader_event sigh
map f11 shader_event breath-debug
```

Then reload kitty's config (`ctrl+shift+f5`, or `ctrl+cmd+,` on macOS) and move the mouse over an empty part of the window.

The breath redraws every 33 ms while kitty is open, like any animated kitty shader.

## Palettes

Four palettes ship in `palettes/`: `1-lavender`, `2-violet` (the default), `3-dusk` and `4-indigo`.

```sh
python3 ~/src/kitty-breath/palette.py           # go to the next palette
python3 ~/src/kitty-breath/palette.py 3-dusk    # pick one by name
```

The switcher writes the palette into `breath.pipeline`. When it runs inside kitty, it also makes that kitty reload its config. Otherwise it tells you to reload. To switch from a key, map this action to a key you like:

```conf
map <your key> launch --type=background python3 ~/src/kitty-breath/palette.py
```

To add a palette, put a file in `palettes/` with one line per layer: `<layer> <#rrggbb> <opacity>`. The layers are `fill`, `inner` and `rim`. For example, `palettes/2-violet.conf`:

```
fill  #6e4ce6 0.04
inner #9b7bff 0.14
rim   #ddd2ff 0.18
```

## Settings

Every setting is a line in `breath.pipeline`, in kitty's form `var <type> <NAME> = <value>`. A line at the top of the file applies to every group. Colors are linear RGB, not hex. To convert a hex color:

```sh
cd ~/src/kitty-breath && python3 -c "import palette; print(palette.to_linear('#0f1017'))"
```

| Setting | Type | Default | What it does |
| --- | --- | --- | --- |
| `REGION` | int | `0` | `0` lights kitty's background around the mouse anywhere in the window. `1` lights only `SIDEBAR_COLOR`, and only while the mouse is left of a `DIVIDER_COLOR` line (see below). |
| `SIDEBAR_COLOR` | float3 | `float3(0.004777, 0.005182, 0.008568)` | The sidebar background in `REGION = 1` (`#0f1017`). |
| `DIVIDER_COLOR` | float3 | `float3(0.672443, 0.603827, 1.0)` | The divider line in `REGION = 1` (`#d6ccff`). |
| `DIVIDER_TOLERANCE` | float | `0.04` | How close a pixel must be to `DIVIDER_COLOR` to count as the divider. |
| `MAX_SIDEBAR_PX` | float | `1200.0` | How far from the left edge to look for the divider. |
| `KEY_TOLERANCE` | float | `0.001` | How close a pixel must be to the background color to light up. |
| `MOUSE_RADIUS_PX` | float | `80.0` | The size of the breath at its fullest. |
| `INHALE_SECONDS`, `HOLD_SECONDS`, `EXHALE_SECONDS` | float | `4.0`, `7.0`, `8.0` | The breath's timing. When you change them, also set `var uint BREATH_SECONDS` to their sum. |
| `FILL_LAG_SECONDS` | float | `1.2` | How far the fill trails the rim. |
| `FILL_COLOR`, `INNER_COLOR`, `RIM_COLOR` | float3 | from the palette | The three layers' colors. The palette switcher writes these. |
| `FILL_OPACITY`, `INNER_OPACITY`, `RIM_OPACITY` | float | from the palette | How strongly each layer tints the background. |
| `GLOW`, `PEAK` | float3, float | lavender, `0.05` | The sigh's color and strength. |

`breath.slang` lists a few more, with a short note on each.

## Sidebar mode for herdr

If you use the herdr terminal multiplexer, you can keep the breath to its sidebar. Uncomment this line in `breath.pipeline`:

```
var int REGION = 1
```

The defaults for `SIDEBAR_COLOR` and `DIVIDER_COLOR` match one herdr theme. If yours differs, convert your sidebar and divider colors to linear RGB and set both.

## Debug view

If nothing shows, turn on the debug view first (`shader_event breath-debug`, F11 in the Quick start). It paints green every pixel the breath may light. No green means the background does not match: a `background_opacity` below 1 can stop the match, and in sidebar mode check `SIDEBAR_COLOR`. Send the event again to turn it off.

## Update

```sh
git -C ~/src/kitty-breath pull --rebase --autostash
```

This keeps your palette and settings. If the pull stops on a conflict in `breath.pipeline`, reset the file, pull again, and pick your palette again:

```sh
git -C ~/src/kitty-breath checkout breath.pipeline
git -C ~/src/kitty-breath pull --rebase
python3 ~/src/kitty-breath/palette.py 2-violet
```

## Checks

```sh
cd ~/src/kitty-breath && python3 -m unittest
```

The tests cover the palette switcher and compile the shader with the `slangc` that ships inside kitty. If kitty is not on your `PATH` or in `/Applications`, set `SLANGC` to the path of its `slangc`. `python3 check_shader.py` runs only the compile.

## License

MIT. See [LICENSE](LICENSE). The shader imports kitty's GPLv3 shader types module at run time. This repo does not copy or ship it.
