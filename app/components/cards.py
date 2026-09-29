"""
Reusable UI card components.

All components return HTML strings rendered via st.markdown(unsafe_allow_html=True).
Keeping HTML out of page files makes pages readable and components testable.
"""

from __future__ import annotations

from html import escape


def metric_card(
    label: str,
    value: str,
    sublabel: str = "",
    colour: str = "",
) -> str:
    """
    Render a metric card with the signature left-border accent.

    Args:
        label: Small uppercase label above the value.
        value: Large prominent number or text.
        sublabel: Optional small description below the value.
        colour: CSS class modifier: "green" | "amber" | "red" | "blue" | ""
    """
    cls = f"metric-card {colour}".strip()
    label, value, sublabel = escape(str(label)), escape(str(value)), escape(str(sublabel))
    sub = f'<div class="sublabel">{sublabel}</div>' if sublabel else ""
    return f"""
<div class="{cls}">
  <div class="label">{label}</div>
  <div class="value">{value}</div>
  {sub}
</div>
"""


def section_header(title: str, sub: bool = False) -> str:
    """Render a styled section header (`sub=True` for a smaller in-page heading)."""
    cls = "section-header sub" if sub else "section-header"
    return f'<div class="{cls}">{escape(title)}</div>'


def skill_pills(skills: list[str], variant: str = "") -> str:
    """
    Render a row of skill badge pills.

    Args:
        skills: List of skill names.
        variant: "matched" | "missing" | "" (default accent)
    """
    if not skills:
        return '<p style="color:var(--text-muted);font-size:0.85rem;">None identified.</p>'
    cls = f"skill-pill {variant}".strip()
    pills = "".join(f'<span class="{cls}">{escape(str(s))}</span>' for s in skills)
    return f'<div style="line-height:2">{pills}</div>'


def badge(text: str, variant: str = "") -> str:
    """
    Render a small pill badge.

    Args:
        text: Badge text (shown upper-case).
        variant: "high" | "medium" | "low" | "easy" | "hard" | "type" | "" (neutral)
    """
    cls = f"badge {variant}".strip()
    return f'<span class="{cls}">{escape(str(text).upper())}</span>'


def recommendation(text: str) -> str:
    """Render a single recommendation row with an accent rule."""
    return f'<div class="rec-row">{escape(text)}</div>'


_ICONS = {
    "upload":  '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="M17 8l-5-5-5 5"/><path d="M12 3v12"/>',
    "chart":   '<path d="M3 3v18h18"/><path d="M7 15l4-4 3 3 5-6"/>',
    "mic":     '<rect x="9" y="2" width="6" height="12" rx="3"/><path d="M5 10v1a7 7 0 0 0 14 0v-1"/><path d="M12 18v4"/>',
    "check":   '<path d="M20 6L9 17l-5-5"/>',
    "file":    '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/>',
    "target":  '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1"/>',
    "message": '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>',
    "layers":  '<path d="M12 2l10 5-10 5L2 7z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/>',
    "edit":    '<path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z"/>',
}


def icon(name: str, size: int = 20) -> str:
    """Inline SVG line icon (stroke follows the surrounding text colour)."""
    body = _ICONS.get(name, _ICONS["file"])
    return (
        f'<svg class="icon" width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" '
        f'stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" '
        f'aria-hidden="true">{body}</svg>'
    )


def empty_state(title: str, message: str = "", icon_name: str = "layers") -> str:
    """Render an empty-state placeholder."""
    msg = f'<div class="message">{escape(message)}</div>' if message else ""
    return f"""
<div class="empty-state">
  <div class="empty-icon">{icon(icon_name, 26)}</div>
  <div class="title">{escape(title)}</div>
  {msg}
</div>
"""


def page_header(title: str, subtitle: str = "", kicker: str = "") -> str:
    """Page title block: small kicker, large title, muted subtitle."""
    k = f'<div class="ph-kicker">{escape(kicker)}</div>' if kicker else ""
    s = f'<p class="ph-sub">{escape(subtitle)}</p>' if subtitle else ""
    return f'<div class="page-header">{k}<h1 class="ph-title">{escape(title)}</h1>{s}</div>'


def gauge(value: float, label: str, sublabel: str = "", colour: str = "accent",
          max_value: float = 100.0, display: str | None = None) -> str:
    """
    Circular progress gauge (SVG).

    Args:
        value: Current value.
        label: Caption under the ring.
        sublabel: Optional smaller caption.
        colour: "accent" | "green" | "amber" | "red" | "blue"
        max_value: Value that fills the ring.
        display: Text in the ring centre (defaults to the rounded percentage).
    """
    frac = max(0.0, min(1.0, (value / max_value) if max_value else 0.0))
    circ = 2 * 3.14159265 * 44
    text = display if display is not None else f"{value:.0f}%"
    sub = f'<div class="g-sub">{escape(sublabel)}</div>' if sublabel else ""
    return f"""
<div class="gauge {colour}">
  <svg viewBox="0 0 100 100" width="132" height="132" role="img" aria-label="{escape(label)} {escape(text)}">
    <circle class="g-track" cx="50" cy="50" r="44" fill="none" stroke-width="8"/>
    <circle class="g-arc" cx="50" cy="50" r="44" fill="none" stroke-width="8" stroke-linecap="round"
            stroke-dasharray="{frac * circ:.1f} {circ:.1f}" transform="rotate(-90 50 50)"/>
    <text x="50" y="56" text-anchor="middle" class="g-text">{escape(text)}</text>
  </svg>
  <div class="g-label">{escape(label)}</div>
  {sub}
</div>
"""


def bar_row(label: str, value: float, colour: str = "") -> str:
    """Labelled horizontal bar (0-100) with the value on the right."""
    v = max(0.0, min(100.0, value))
    if not colour:
        colour = "green" if v >= 75 else "blue" if v >= 55 else "amber" if v >= 35 else "red"
    return f"""
<div class="bar-row">
  <div class="bar-top"><span>{escape(label)}</span><strong>{v:.0f}%</strong></div>
  <div class="bar-track"><div class="bar-fill {colour}" style="width:{v:.0f}%"></div></div>
</div>
"""


def steps(items: list[tuple[str, str, str]]) -> str:
    """
    Numbered step strip.

    Args:
        items: (title, description, state) with state "done" | "current" | "todo".
    """
    cells = []
    for i, (title, desc, state) in enumerate(items, 1):
        mark = icon("check", 16) if state == "done" else str(i)
        cells.append(
            f'<div class="step {state}"><div class="step-num">{mark}</div>'
            f'<div><div class="step-title">{escape(title)}</div>'
            f'<div class="step-desc">{escape(desc)}</div></div></div>'
        )
    return f'<div class="steps">{"".join(cells)}</div>'


def hero(name: str, role: str, chips: list[str]) -> str:
    """Dashboard banner: candidate, target role, and small fact chips."""
    chip_html = "".join(f'<span class="hero-chip">{escape(c)}</span>' for c in chips)
    return f"""
<div class="hero">
  <div class="hero-eyebrow">Interview preparation</div>
  <div class="hero-title">{escape(name)}</div>
  <div class="hero-role">Target role &middot; <strong>{escape(role)}</strong></div>
  <div class="hero-chips">{chip_html}</div>
</div>
"""
