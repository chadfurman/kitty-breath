#language slang 2026
// A 4-7-8 breath of light around the mouse pointer, and a sigh on demand.
// Only plain background pixels change, so text never does. The first
// pipeline group copies kitty's frame into texture b, where later groups
// look up which pixels are plain background. Every const below can be set
// from breath.pipeline with `var <type> <NAME> = <value>`. Colors are linear RGB.

import kitty_custom_shader_types;

static const int MODE = 0;  // set per pipeline group: 0 copy frame, 2 sigh, 3 debug, 4 breath

static const int REGION_ANYWHERE = 0;  // light kitty's own background, anywhere in the window
static const int REGION_SIDEBAR = 1;   // light only SIDEBAR_COLOR, left of a DIVIDER_COLOR line (herdr)
static const int REGION = 0;
static const float3 SIDEBAR_COLOR = float3(0.004777, 0.005182, 0.008568);  // herdr's sidebar, #0f1017
static const float3 DIVIDER_COLOR = float3(0.672443, 0.603827, 1.0);       // herdr's divider, #d6ccff
static const float DIVIDER_TOLERANCE = 0.04;
static const float MAX_SIDEBAR_PX = 1200.0;
static const float KEY_TOLERANCE = 0.001;

static const float3 GLOW = float3(0.672443, 0.603827, 1.0);  // the sigh's color
static const float PEAK = 0.05;
static const float HORIZON_FLOOR = 0.35;

static const float INHALE_SECONDS = 4.0;
static const float HOLD_SECONDS = 7.0;
static const float EXHALE_SECONDS = 8.0;
static const uint BREATH_SECONDS = 19;  // inhale + hold + exhale

static const float FILL_LAG_SECONDS = 0.0;  // how far the filled area trails the rim
// Each layer is laid over the one below: fill, then inner light, then rim on top.
// Opacity is how far each layer moves the pixel toward its color.
static const float3 FILL_COLOR = float3(0.672443, 0.603827, 1.0);
static const float FILL_OPACITY = 0.03;
static const float3 INNER_COLOR = float3(0.672443, 0.603827, 1.0);
static const float INNER_OPACITY = 0.06;
static const float INNER_FALLOFF = 1.6;  // how fast the inner light fades from its center to its edge
static const float INNER_GROWN_LEVEL = 0.45;  // the inner light's strength once it reaches the fill's edge
static const float3 RIM_COLOR = float3(0.672443, 0.603827, 1.0);
static const float RIM_OPACITY = 0.12;
static const float RIM_LEADING_LEVEL = 0.2;  // the rim's strength while it leads outward
static const float RIM_PX = 2.0;  // rim thickness in screen pixels
static const float REST_REACH = 0.035;  // the breath never shrinks below this

static const float EDGE_SOFT_PX = 2.5;  // anti-aliasing on the hard edges
static const float MOUSE_RADIUS_PX = 80.0;
static const float DITHER = 1.0;  // fixed noise in 8-bit sRGB steps, hides banding near black

bool matches(KittyTextures t, float3 key) {
    return all(abs(t.b.Sample(t.pos).rgb - key) <= KEY_TOLERANCE);
}

// True for a plain background pixel of the region REGION picks.
bool lit_here(KittyTextures t, KittyCustomShaderData d) {
    return matches(t, REGION == REGION_SIDEBAR ? SIDEBAR_COLOR : d.background.rgb);
}

float ease(float x) {
    x = saturate(x);
    return x * x * x * (x * (x * 6.0 - 15.0) + 10.0);
}

float reach_at(float s) {
    if (s < INHALE_SECONDS) return ease(s / INHALE_SECONDS);
    s -= INHALE_SECONDS;
    if (s < HOLD_SECONDS) return 1.0;
    return 1.0 - ease((s - HOLD_SECONDS) / EXHALE_SECONDS);
}

// How far the breath reaches, REST_REACH to 1, as it was `lag` seconds ago.
float reach(KittyCustomShaderData d, float lag) {
    float period = float(BREATH_SECONDS);
    float r = reach_at(fmod(d.wrapped_time(BREATH_SECONDS) - lag + period, period));
    return lerp(REST_REACH, 1.0, r);
}

// The inner light counts out the hold: it grows from the center to the fill's
// edge over the hold, then shrinks with the fill.
float inner_radius(KittyCustomShaderData d, float fill_r) {
    float s = d.wrapped_time(BREATH_SECONDS) - INHALE_SECONDS;
    if (s < 0.0) return 0.0;
    return fill_r * saturate(s / HOLD_SECONDS);
}

float inside(float dist, float r, float units_per_px) {
    float soft = EDGE_SOFT_PX * units_per_px;
    return r > 0.0 ? 1.0 - smoothstep(r - soft, r + soft * 0.5, dist) : 0.0;
}

// The three layers at `rel` from the center (length 1 = full size), each 0 to 1:
// x the fill, y the inner light, z the rim.
float3 layers(float2 rel, float ring_r, float fill_r, float units_per_px, KittyCustomShaderData d) {
    float dist = length(rel);
    float inner_r = inner_radius(d, fill_r);
    float glow = pow(saturate(1.0 - dist / max(inner_r, 0.0001)), INNER_FALLOFF);
    float grown = saturate(inner_r / max(fill_r, 0.0001));
    float inner = glow * lerp(1.0, INNER_GROWN_LEVEL, grown);
    float rim = ring_r > 0.0 ? 1.0 - smoothstep(0.0, RIM_PX * units_per_px, abs(dist - ring_r)) : 0.0;
    rim *= lerp(RIM_LEADING_LEVEL, 1.0, smoothstep(0.0, 0.08, fill_r - ring_r));
    return float3(inside(dist, fill_r, units_per_px), inner, rim);
}

float3 to_srgb(float3 c) {
    float3 high = 1.055 * pow(max(c, 0.0), 1.0 / 2.4) - 0.055;
    return lerp(high, c * 12.92, step(c, 0.0031308));
}

float3 to_linear(float3 c) {
    float3 high = pow((max(c, 0.0) + 0.055) / 1.055, 2.4);
    return lerp(high, c / 12.92, step(c, 0.04045));
}

float noise(float2 pixel) {
    return frac(sin(dot(pixel, float2(12.9898, 78.233))) * 43758.5453);
}

float4 dithered(float3 c, float alpha, KittyTextures t, KittyCustomShaderData d) {
    float3 lit = to_srgb(c);
    float2 pixel = floor(t.pos * float2(d.viewport_size_pixels));
    lit += (noise(pixel) - 0.5) * DITHER / 255.0;
    return float4(to_linear(saturate(lit)), alpha);
}

float4 paint(float4 color, float3 l, KittyTextures t, KittyCustomShaderData d) {
    float3 c = lerp(color.rgb, FILL_COLOR, FILL_OPACITY * l.x);
    c = lerp(c, INNER_COLOR, INNER_OPACITY * l.y);
    c = lerp(c, RIM_COLOR, RIM_OPACITY * l.z);
    return dithered(c, color.a, t, d);
}

// True when the mouse is left of the sidebar's divider on its row.
bool mouse_in_sidebar(KittyTextures t, KittyCustomShaderData d) {
    float px = 1.0 / float(d.viewport_size_pixels.x);
    for (float x = 0.5 * px; x < MAX_SIDEBAR_PX * px; x += px) {
        if (x >= d.mouse_pos.x) return true;
        if (all(abs(t.b.Sample(float2(x, d.mouse_pos.y)).rgb - DIVIDER_COLOR) <= DIVIDER_TOLERANCE)) return false;
    }
    return false;
}

float4 mouse_breath(float4 color, KittyTextures t, KittyCustomShaderData d) {
    float2 m = d.mouse_pos.xy;
    if (d.mouse_pointer_hidden > 0.5 || any(m < 0.0) || any(m > 1.0)) return color;
    if (!lit_here(t, d)) return color;
    float2 rel = (t.pos - m) * float2(d.viewport_size_pixels) / MOUSE_RADIUS_PX;
    if (length(rel) > 1.1) return color;
    if (REGION == REGION_SIDEBAR && !mouse_in_sidebar(t, d)) return color;
    float ring_r = reach(d, 0.0);
    float fill_r = reach(d, FILL_LAG_SECONDS);
    return paint(color, layers(rel, ring_r, fill_r, 1.0 / MOUSE_RADIUS_PX, d), t, d);
}

public float4
fragment_main(float4 color, KittyTextures t, KittyCustomShaderData d) {
    if (MODE == 0) return color;
    if (MODE == 4) return mouse_breath(color, t, d);
    if (!lit_here(t, d)) return color;
    if (MODE == 3) return float4(0.0, 0.6, 0.3, color.a);
    float horizon = lerp(1.0, HORIZON_FLOOR, smoothstep(0.0, 1.0, t.pos.y));
    return dithered(lerp(color.rgb, GLOW, PEAK * horizon * t.animation_progress), color.a, t, d);
}
