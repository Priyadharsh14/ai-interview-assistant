"""
Reusable UI card components.

All components return HTML strings rendered via st.markdown(unsafe_allow_html=True).
Keeping HTML out of page files makes pages readable and components testable.
"""

from __future__ import annotations


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
    sub = f'<div class="sublabel">{sublabel}</div>' if sublabel else ""
    return f"""
<div class="{cls}">
  <div class="label">{label}</div>
  <div class="value">{value}</div>
  {sub}
</div>
"""


def section_header(title: str) -> str:
    """Render a styled section header."""
    return f'<div class="section-header">{title}</div>'


def skill_pills(skills: list[str], variant: str = "") -> str:
    """
    Render a row of skill badge pills.

    Args:
        skills: List of skill names.
        variant: "matched" | "missing" | "" (default indigo)
    """
    if not skills:
        return '<p style="color:var(--text-muted);font-size:0.85rem;">None identified.</p>'
    cls = f"skill-pill {variant}".strip()
    pills = "".join(f'<span class="{cls}">{s}</span>' for s in skills)
    return f'<div style="line-height:2">{pills}</div>'


def score_ring(score: float, max_score: float = 100.0) -> str:
    """Render a circular score ring."""
    display = f"{score:.0f}" if max_score == 100 else f"{score:.1f}"
    return f'<div class="score-ring">{display}</div>'


def priority_badge(priority: str) -> str:
    """Render a coloured priority badge."""
    colours = {"high": "red", "medium": "amber", "low": "blue"}
    colour = colours.get(priority.lower(), "")
    style_map = {
        "red": "background:rgba(239,68,68,.15);color:#ef4444;border:1px solid rgba(239,68,68,.3)",
        "amber": "background:rgba(245,158,11,.15);color:#f59e0b;border:1px solid rgba(245,158,11,.3)",
        "blue": "background:rgba(59,130,246,.15);color:#3b82f6;border:1px solid rgba(59,130,246,.3)",
    }
    style = style_map.get(colour, "")
    return (
        f'<span style="border-radius:999px;padding:.15rem .6rem;'
        f'font-size:.72rem;font-weight:600;{style}">'
        f'{priority.upper()}</span>'
    )


def chat_bubble(role: str, content: str, sources: list[str] | None = None) -> str:
    """
    Render a chat message bubble.

    Args:
        role: "user" | "assistant"
        content: Message text.
        sources: Optional source file names cited.
    """
    if role == "user":
        bg = "rgba(99,102,241,0.12)"
        border = "rgba(99,102,241,0.3)"
        label = "You"
    else:
        bg = "rgba(19,25,41,0.85)"
        border = "rgba(255,255,255,0.06)"
        label = "🎯 Assistant"

    src_html = ""
    if sources:
        src_list = ", ".join(sources)
        src_html = (
            f'<div style="margin-top:.5rem;font-size:.72rem;'
            f'color:var(--text-muted)">📎 Sources: {src_list}</div>'
        )

    return f"""
<div style="background:{bg};border:1px solid {border};border-radius:10px;
     padding:.9rem 1.1rem;margin-bottom:.5rem">
  <div style="font-size:.72rem;color:var(--text-muted);
       margin-bottom:.35rem;font-weight:600">{label}</div>
  <div style="color:var(--text-primary);font-size:.9rem;
       line-height:1.6">{content}</div>
  {src_html}
</div>
"""


def empty_state(icon: str, title: str, message: str) -> str:
    """Render an empty-state placeholder."""
    return f"""
<div style="text-align:center;padding:3rem 2rem;
     color:var(--text-muted)">
  <div style="font-size:2.5rem;margin-bottom:.75rem">{icon}</div>
  <div style="font-size:1rem;font-weight:600;
       color:var(--text-secondary);margin-bottom:.4rem">{title}</div>
  <div style="font-size:.85rem">{message}</div>
</div>
"""
