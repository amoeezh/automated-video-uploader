"""Procedural animated data-visualization clips for the facts-reel pipeline.

Two families of chart, both drawn from the validated dark-mode dataviz
reference palette (references/palette.md): single-fact "quick stat" templates
(one accent hue, sequential) and a "timeline race" template (fixed-order
categorical hues, since there the entities themselves are the subject).
Rendered with matplotlib (Agg backend, no display needed) straight to mp4 via
the ffmpeg animation writer, so unlike Blender there's no GPU/EGL dependency.
"""
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation

CHART_TYPES = ("hero_number", "compare_two", "line_trend", "meter_fill", "dumbbell_before_after")

BG = "#1a1a19"
ACCENT = "#3987e5"
ACCENT_DIM = "#184f95"
TEXT_PRIMARY = "#ffffff"
TEXT_SECONDARY = "#c3c2b7"
TEXT_MUTED = "#898781"
GRID = "#2c2c2a"
BASELINE = "#383835"

# Fixed-order categorical hues (dark-mode steps), for when the entities
# themselves are the subject (timeline race) rather than a single magnitude.
CATEGORICAL = ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#9085e9"]
MAX_RACE_ENTITIES = len(CATEGORICAL)

WIDTH_PX, HEIGHT_PX = 540, 960
DPI = 100
FIGSIZE = (WIDTH_PX / DPI, HEIGHT_PX / DPI)
FPS = 24


def validate_chart_spec(chart):
    """Coerces a possibly-malformed chart spec into something every renderer can use."""
    chart = dict(chart or {})
    chart_type = chart.get("chart_type")
    if chart_type not in CHART_TYPES:
        chart_type = "hero_number"

    def num(key, default=0.0):
        try:
            return float(chart.get(key))
        except (TypeError, ValueError):
            return default

    value_a = num("value_a", 0.0)
    value_b = chart.get("value_b")
    value_b = None if value_b in (None, "") else num("value_b", None)
    label_a = str(chart.get("label_a") or "")[:40]
    label_b = str(chart.get("label_b") or "")[:40] if chart.get("label_b") else ""
    unit = str(chart.get("unit") or "")[:8]

    needs_pair = chart_type in ("compare_two", "line_trend", "dumbbell_before_after")
    if needs_pair and value_b is None:
        chart_type = "hero_number"

    return {
        "chart_type": chart_type,
        "value_a": value_a,
        "value_b": value_b,
        "label_a": label_a,
        "label_b": label_b,
        "unit": unit,
    }


def _ease_out_cubic(t):
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


def _new_axes():
    fig = plt.figure(figsize=FIGSIZE, dpi=DPI)
    fig.patch.set_facecolor(BG)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_facecolor(BG)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    return fig, ax


def _fmt_num(v):
    if v == int(v):
        return f"{int(v):,}"
    return f"{v:,.1f}"


def _render(fig, ax, frame_count, draw_frame, out_path):
    def update(frame):
        t = frame / max(1, frame_count - 1)
        draw_frame(ax, _ease_out_cubic(t))
        return []

    anim = FuncAnimation(fig, update, frames=frame_count, blit=False)
    anim.save(out_path, writer="ffmpeg", fps=FPS, dpi=DPI,
               savefig_kwargs={"facecolor": BG})
    plt.close(fig)


def _clear_dynamic(ax):
    for artist in list(ax.texts) + list(ax.lines) + list(ax.patches):
        artist.remove()


def _hero_number(spec, frame_count, out_path):
    fig, ax = _new_axes()

    def draw(ax, t):
        _clear_dynamic(ax)
        value = spec["value_a"] * t
        ax.text(0.5, 0.68, _fmt_num(value) + spec["unit"], ha="center", va="center",
                 fontsize=68, color=TEXT_PRIMARY, fontweight="bold", family="sans-serif")
        ax.text(0.5, 0.53, spec["label_a"], ha="center", va="center",
                 fontsize=18, color=TEXT_SECONDARY, family="sans-serif", wrap=True)

    _render(fig, ax, frame_count, draw, out_path)


def _compare_two(spec, frame_count, out_path):
    fig, ax = _new_axes()
    max_v = max(spec["value_a"], spec["value_b"], 1e-9)
    bar_x = [0.32, 0.68]
    labels = [spec["label_a"], spec["label_b"]]
    values = [spec["value_a"], spec["value_b"]]

    def draw(ax, t):
        _clear_dynamic(ax)
        top = 0.90
        base = 0.40
        for x, val, lab in zip(bar_x, values, labels):
            h = (val / max_v) * (top - base) * t
            ax.plot([x, x], [base, base + h], color=ACCENT, linewidth=34,
                     solid_capstyle="round")
            ax.text(x, base + h + 0.05, _fmt_num(val * t) + spec["unit"], ha="center",
                     va="bottom", fontsize=20, color=TEXT_PRIMARY, fontweight="bold")
            ax.text(x, base - 0.06, lab, ha="center", va="top", fontsize=15,
                     color=TEXT_SECONDARY)
        ax.plot([0.15, 0.85], [base, base], color=BASELINE, linewidth=2)

    _render(fig, ax, frame_count, draw, out_path)


def _line_trend(spec, frame_count, out_path):
    fig, ax = _new_axes()
    x0, x1 = 0.18, 0.82
    y0, y1 = 0.45, 0.80
    lo = min(spec["value_a"], spec["value_b"])
    hi = max(spec["value_a"], spec["value_b"], lo + 1e-9)

    def y_for(v):
        return y0 + (v - lo) / (hi - lo) * (y1 - y0)

    def draw(ax, t):
        _clear_dynamic(ax)
        ax.plot([0.1, 0.9], [0.35, 0.35], color=GRID, linewidth=1)
        cx = x0 + (x1 - x0) * t
        start_y = y_for(spec["value_a"])
        end_y = y_for(spec["value_b"])
        cy = start_y + (end_y - start_y) * t
        ax.plot([x0, cx], [start_y, cy], color=ACCENT, linewidth=6, solid_capstyle="round")
        ax.plot([x0], [start_y], marker="o", markersize=9, color=TEXT_MUTED)
        ax.plot([cx], [cy], marker="o", markersize=11, color=ACCENT)
        ax.text(x0, start_y - 0.07, f"{spec['label_a']}\n{_fmt_num(spec['value_a'])}{spec['unit']}",
                 ha="left", va="top", fontsize=14, color=TEXT_SECONDARY)
        if t > 0.85:
            ax.text(cx, cy + 0.09, f"{spec['label_b']}\n{_fmt_num(spec['value_b'])}{spec['unit']}",
                     ha="right", va="bottom", fontsize=15, color=TEXT_PRIMARY, fontweight="bold")

    _render(fig, ax, frame_count, draw, out_path)


def _meter_fill(spec, frame_count, out_path):
    fig, ax = _new_axes()
    pct = max(0.0, min(100.0, spec["value_a"]))

    def draw(ax, t):
        _clear_dynamic(ax)
        y = 0.62
        ax.plot([0.15, 0.85], [y, y], color=BASELINE, linewidth=22, solid_capstyle="round")
        fill_x = 0.15 + (0.85 - 0.15) * (pct / 100.0) * t
        if fill_x > 0.16:
            ax.plot([0.15, fill_x], [y, y], color=ACCENT, linewidth=22, solid_capstyle="round")
        ax.text(0.5, 0.78, f"{_fmt_num(pct * t)}%", ha="center", va="bottom",
                 fontsize=58, color=TEXT_PRIMARY, fontweight="bold")
        ax.text(0.5, 0.50, spec["label_a"], ha="center", va="top", fontsize=17,
                 color=TEXT_SECONDARY)

    _render(fig, ax, frame_count, draw, out_path)


def _dumbbell(spec, frame_count, out_path):
    fig, ax = _new_axes()
    y = 0.65
    x0, x1 = 0.25, 0.75

    def draw(ax, t):
        _clear_dynamic(ax)
        cx = x0 + (x1 - x0) * t
        ax.plot([x0, cx], [y, y], color=TEXT_MUTED, linewidth=3, solid_capstyle="round")
        ax.plot([x0], [y], marker="o", markersize=16, color=TEXT_MUTED)
        ax.text(x0, y - 0.10, f"{spec['label_a']}\n{_fmt_num(spec['value_a'])}{spec['unit']}",
                 ha="center", va="top", fontsize=14, color=TEXT_SECONDARY)
        if t > 0.1:
            ax.plot([cx], [y], marker="o", markersize=18, color=ACCENT)
        if t > 0.85:
            ax.text(x1, y + 0.10, f"{spec['label_b']}\n{_fmt_num(spec['value_b'])}{spec['unit']}",
                     ha="center", va="bottom", fontsize=15, color=TEXT_PRIMARY, fontweight="bold")

    _render(fig, ax, frame_count, draw, out_path)


_RENDERERS = {
    "hero_number": _hero_number,
    "compare_two": _compare_two,
    "line_trend": _line_trend,
    "meter_fill": _meter_fill,
    "dumbbell_before_after": _dumbbell,
}


def render_chart_clip(chart, duration, out_path):
    spec = validate_chart_spec(chart)
    frame_count = max(2, int(duration * FPS))
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    _RENDERERS[spec["chart_type"]](spec, frame_count, out_path)
    return out_path


def validate_timeline_spec(raw):
    """Coerces a possibly-malformed timeline-race spec into something renderable."""
    raw = dict(raw or {})
    entities = [str(e)[:22] for e in (raw.get("entities") or [])][:MAX_RACE_ENTITIES]
    n = len(entities)

    checkpoints = []
    for cp in raw.get("checkpoints") or []:
        try:
            year = int(cp["year"])
            values = [max(0.0, float(v)) for v in cp["values"]][:n]
        except (KeyError, TypeError, ValueError, IndexError):
            continue
        if len(values) < n:
            values = values + [0.0] * (n - len(values))
        checkpoints.append({"year": year, "values": values})
    checkpoints.sort(key=lambda c: c["year"])

    try:
        start_year = int(raw.get("start_year", checkpoints[0]["year"] if checkpoints else 1500))
        end_year = int(raw.get("end_year", checkpoints[-1]["year"] if checkpoints else 2026))
    except (TypeError, ValueError):
        start_year, end_year = 1500, 2026
    if end_year <= start_year:
        end_year = start_year + 1

    valid = n >= 2 and len(checkpoints) >= 2
    return {
        "valid": valid,
        "chart_title": str(raw.get("chart_title") or "")[:60],
        "unit": str(raw.get("unit") or "")[:12],
        "start_year": start_year,
        "end_year": end_year,
        "entities": entities,
        "checkpoints": checkpoints,
    }


def _interpolate_values(checkpoints, year, n):
    if year <= checkpoints[0]["year"]:
        return checkpoints[0]["values"]
    if year >= checkpoints[-1]["year"]:
        return checkpoints[-1]["values"]
    for i in range(len(checkpoints) - 1):
        a, b = checkpoints[i], checkpoints[i + 1]
        if a["year"] <= year <= b["year"]:
            span = max(1e-9, b["year"] - a["year"])
            frac = (year - a["year"]) / span
            return [a["values"][j] + (b["values"][j] - a["values"][j]) * frac for j in range(n)]
    return checkpoints[-1]["values"]


def _smoothstep(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def render_timeline_race_clip(spec, duration, out_path):
    entities = spec["entities"]
    n = len(entities)
    checkpoints = spec["checkpoints"]
    start_year, end_year = spec["start_year"], spec["end_year"]
    global_max = max((v for cp in checkpoints for v in cp["values"]), default=1.0) or 1.0
    colors = CATEGORICAL[:n]

    fig = plt.figure(figsize=FIGSIZE, dpi=DPI)
    fig.patch.set_facecolor(BG)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_facecolor(BG)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    top, bottom = 0.68, 0.34
    row_h = (top - bottom) / n
    bar_x0, bar_x1 = 0.34, 0.85

    frame_count = max(2, int(duration * FPS))

    def draw(_ax, t):
        _clear_dynamic(ax)
        year = start_year + (end_year - start_year) * _smoothstep(t)
        values = _interpolate_values(checkpoints, year, n)
        ranked = sorted(range(n), key=lambda i: values[i], reverse=True)

        ax.text(0.5, 0.93, spec["chart_title"], ha="center", va="top",
                 fontsize=15, color=TEXT_SECONDARY)
        ax.text(0.5, 0.85, f"{int(year)}", ha="center", va="top",
                 fontsize=40, color=TEXT_PRIMARY, fontweight="bold")

        for row, idx in enumerate(ranked):
            y = top - (row + 0.5) * row_h
            w = (values[idx] / global_max) * (bar_x1 - bar_x0)
            ax.plot([bar_x0, bar_x0 + w], [y, y], color=colors[idx], linewidth=20,
                     solid_capstyle="round")
            ax.text(bar_x0 - 0.03, y, entities[idx], ha="right", va="center",
                     fontsize=12, color=TEXT_PRIMARY)
            ax.text(bar_x0 + w + 0.03, y, f"{_fmt_num(values[idx])}{spec['unit']}",
                     ha="left", va="center", fontsize=11, color=TEXT_SECONDARY)

    _render(fig, ax, frame_count, draw, out_path)
    return out_path
