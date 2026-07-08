"""
Global CSS theme — dark glassmorphism design system.

Single source of truth for all colours, typography, and card styles.
Injected once at app startup via st.markdown(get_global_css(), unsafe_allow_html=True).
"""

from __future__ import annotations


def get_global_css() -> str:
    """Return the full CSS string for the application theme."""
    return """
<style>
/* ================================================================
   DESIGN TOKENS
   Palette: deep navy background, electric indigo accent,
   slate glass surfaces, crisp white text hierarchy.
   Signature: the metric cards use a left-border accent line
   (not a gradient header) — structural, not decorative.
================================================================ */
:root {
    --bg-base:        #0b0f1a;
    --bg-surface:     #131929;
    --bg-card:        rgba(19, 25, 41, 0.85);
    --bg-hover:       rgba(99, 102, 241, 0.08);

    --accent:         #6366f1;
    --accent-soft:    rgba(99, 102, 241, 0.18);
    --accent-glow:    rgba(99, 102, 241, 0.35);

    --green:          #22c55e;
    --amber:          #f59e0b;
    --red:            #ef4444;
    --blue:           #3b82f6;

    --text-primary:   #f1f5f9;
    --text-secondary: #94a3b8;
    --text-muted:     #475569;

    --border:         rgba(99, 102, 241, 0.15);
    --border-soft:    rgba(255, 255, 255, 0.06);

    --radius-card:    14px;
    --radius-sm:      8px;
    --shadow-card:    0 4px 24px rgba(0,0,0,0.4);
}

/* ── Global reset ─────────────────────────────────────────── */
.stApp {
    background: var(--bg-base) !important;
    color: var(--text-primary) !important;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}

/* Hide Streamlit chrome */
#MainMenu, footer, header { visibility: hidden; }
.block-container { padding-top: 1.5rem !important; }

/* ── Sidebar ──────────────────────────────────────────────── */
[data-testid="stSidebar"] {
    background: var(--bg-surface) !important;
    border-right: 1px solid var(--border-soft) !important;
}
[data-testid="stSidebar"] .stMarkdown p {
    color: var(--text-secondary) !important;
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin: 1.2rem 0 0.4rem;
}

/* ── Buttons ──────────────────────────────────────────────── */
.stButton > button {
    background: var(--accent) !important;
    color: #fff !important;
    border: none !important;
    border-radius: var(--radius-sm) !important;
    padding: 0.5rem 1.2rem !important;
    font-weight: 600 !important;
    letter-spacing: 0.01em !important;
    transition: opacity 0.15s ease !important;
}
.stButton > button:hover { opacity: 0.88 !important; }
.stButton > button[kind="secondary"] {
    background: transparent !important;
    border: 1px solid var(--border) !important;
    color: var(--text-secondary) !important;
}

/* ── File uploader ────────────────────────────────────────── */
[data-testid="stFileUploader"] {
    background: var(--bg-card) !important;
    border: 1.5px dashed var(--border) !important;
    border-radius: var(--radius-card) !important;
    padding: 1.5rem !important;
}

/* ── Chat message bubbles ─────────────────────────────────── */
[data-testid="stChatMessage"] {
    background: var(--bg-card) !important;
    border-radius: var(--radius-sm) !important;
    border: 1px solid var(--border-soft) !important;
    padding: 1rem !important;
    margin-bottom: 0.5rem !important;
}

/* ── Input fields ─────────────────────────────────────────── */
.stTextInput > div > div > input,
.stTextArea > div > div > textarea {
    background: var(--bg-surface) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--radius-sm) !important;
    color: var(--text-primary) !important;
}

/* ── Tabs ─────────────────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] {
    background: transparent !important;
    border-bottom: 1px solid var(--border-soft) !important;
    gap: 0.25rem !important;
}
.stTabs [data-baseweb="tab"] {
    background: transparent !important;
    color: var(--text-secondary) !important;
    border-radius: var(--radius-sm) var(--radius-sm) 0 0 !important;
    padding: 0.5rem 1rem !important;
}
.stTabs [aria-selected="true"] {
    background: var(--accent-soft) !important;
    color: var(--text-primary) !important;
    border-bottom: 2px solid var(--accent) !important;
}

/* ── Metric cards (signature: left accent border) ─────────── */
.metric-card {
    background: var(--bg-card);
    border: 1px solid var(--border-soft);
    border-left: 3px solid var(--accent);
    border-radius: var(--radius-card);
    padding: 1.25rem 1.5rem;
    box-shadow: var(--shadow-card);
    backdrop-filter: blur(12px);
}
.metric-card .label {
    color: var(--text-secondary);
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: 0.4rem;
}
.metric-card .value {
    color: var(--text-primary);
    font-size: 2rem;
    font-weight: 700;
    line-height: 1;
}
.metric-card .sublabel {
    color: var(--text-muted);
    font-size: 0.78rem;
    margin-top: 0.3rem;
}

/* Colour variants */
.metric-card.green  { border-left-color: var(--green); }
.metric-card.amber  { border-left-color: var(--amber); }
.metric-card.red    { border-left-color: var(--red);   }
.metric-card.blue   { border-left-color: var(--blue);  }

/* ── Section headers ──────────────────────────────────────── */
.section-header {
    color: var(--text-primary);
    font-size: 1.1rem;
    font-weight: 600;
    letter-spacing: -0.01em;
    padding-bottom: 0.5rem;
    border-bottom: 1px solid var(--border-soft);
    margin-bottom: 1rem;
}

/* ── Skill pill badges ────────────────────────────────────── */
.skill-pill {
    display: inline-block;
    background: var(--accent-soft);
    color: var(--accent);
    border: 1px solid var(--accent-glow);
    border-radius: 999px;
    padding: 0.2rem 0.75rem;
    font-size: 0.78rem;
    font-weight: 500;
    margin: 0.15rem;
}
.skill-pill.missing {
    background: rgba(239, 68, 68, 0.12);
    color: var(--red);
    border-color: rgba(239, 68, 68, 0.3);
}
.skill-pill.matched {
    background: rgba(34, 197, 94, 0.12);
    color: var(--green);
    border-color: rgba(34, 197, 94, 0.3);
}

/* ── Score ring ───────────────────────────────────────────── */
.score-ring {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    width: 110px;
    height: 110px;
    border-radius: 50%;
    border: 3px solid var(--accent);
    background: var(--accent-soft);
    font-size: 1.8rem;
    font-weight: 800;
    color: var(--text-primary);
}

/* ── Progress bar ─────────────────────────────────────────── */
.stProgress > div > div {
    background: var(--accent) !important;
    border-radius: 999px !important;
}
.stProgress > div {
    background: var(--bg-surface) !important;
    border-radius: 999px !important;
    height: 6px !important;
}

/* ── Dividers ─────────────────────────────────────────────── */
hr { border-color: var(--border-soft) !important; }

/* ── Expander ─────────────────────────────────────────────── */
.streamlit-expanderHeader {
    background: var(--bg-card) !important;
    border-radius: var(--radius-sm) !important;
    color: var(--text-primary) !important;
}
</style>
"""
