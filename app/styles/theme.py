"""
Global CSS theme — light, editorial design system.

Single source of truth for all colours, typography, and component styles.
Injected once at app startup via st.markdown(get_global_css(), unsafe_allow_html=True).
Streamlit's own base colours are set to match in .streamlit/config.toml.
"""

from __future__ import annotations


def get_global_css() -> str:
    """Return the full CSS string for the application theme."""
    return """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

/* ================================================================
   DESIGN TOKENS
   Palette: warm-white canvas, white surfaces with hairline borders,
   deep-ink text, one confident blue accent. Status colours are used
   only for meaning (good / caution / problem), never decoration.
   Signature: metric cards carry a coloured left rule that encodes
   status - structural, not decorative.
   Text contrast on white: primary 17:1, secondary 7.6:1, muted 4.8:1.
================================================================ */
:root {
    --bg-base:        #f6f7f9;
    --bg-surface:     #ffffff;
    --bg-card:        #ffffff;
    --bg-hover:       #f0f3fa;

    --accent:         #2b59e6;
    --accent-strong:  #1f45c0;
    --accent-soft:    #e9effd;
    --accent-glow:    #c3d2fa;

    --green:          #15803d;
    --green-soft:     #e7f5ec;
    --amber:          #b45309;
    --amber-soft:     #fdf1de;
    --red:            #b91c1c;
    --red-soft:       #fdeaea;
    --blue:           #1d4ed8;
    --blue-soft:      #e6eefe;

    --text-primary:   #0f172a;
    --text-secondary: #475569;
    --text-muted:     #64748b;

    --border:         #d9dee7;
    --border-soft:    #e8ebf0;

    --radius-card:    12px;
    --radius-sm:      8px;
    --shadow-card:    0 1px 2px rgba(15, 23, 42, 0.05), 0 2px 8px rgba(15, 23, 42, 0.04);
    --shadow-lift:    0 2px 4px rgba(15, 23, 42, 0.06), 0 8px 20px rgba(15, 23, 42, 0.07);
}

/* ── Global ───────────────────────────────────────────────── */
.stApp {
    background: var(--bg-base) !important;
    color: var(--text-primary) !important;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    -webkit-font-smoothing: antialiased;
}
h1, h2, h3, h4 { color: var(--text-primary) !important; letter-spacing: -0.015em; }
p, li, label, .stMarkdown { color: var(--text-primary); }
[data-testid="stCaptionContainer"], .stCaption { color: var(--text-muted) !important; }
a { color: var(--accent); }

/* Hide Streamlit chrome, but keep the header itself so the sidebar
   expand/collapse control stays reachable. */
#MainMenu, footer, [data-testid="stToolbar"], [data-testid="stDecoration"],
[data-testid="stStatusWidget"] { visibility: hidden; }
header[data-testid="stHeader"] { background: transparent !important; }
.block-container {
    padding-top: 1.75rem !important;
    padding-bottom: 3rem !important;
    max-width: 1180px;
}

/* ── Keyboard focus (visible on every interactive element) ─── */
button:focus-visible, a:focus-visible, input:focus-visible,
textarea:focus-visible, [role="tab"]:focus-visible,
[data-baseweb="select"]:focus-within {
    outline: 2px solid var(--accent) !important;
    outline-offset: 2px !important;
}
@media (prefers-reduced-motion: reduce) {
    * { transition: none !important; animation: none !important; }
}

/* ── Sidebar ──────────────────────────────────────────────── */
[data-testid="stSidebar"] {
    background: var(--bg-surface) !important;
    border-right: 1px solid var(--border-soft) !important;
}
[data-testid="stSidebar"] .block-container,
[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] { padding-top: 1.25rem !important; }

.brand { display: flex; align-items: center; gap: .65rem; margin: 0 0 .15rem; }
.brand-mark {
    width: 30px; height: 30px; border-radius: 8px;
    background: var(--accent); color: #fff;
    display: flex; align-items: center; justify-content: center;
    font-weight: 800; font-size: .95rem; letter-spacing: -0.02em;
}
.brand-name { font-size: 1.05rem; font-weight: 700; color: var(--text-primary); letter-spacing: -0.01em; }
.brand-sub  { font-size: .72rem; color: var(--text-muted); margin: .1rem 0 1.25rem 2.3rem; }

.nav-label {
    color: var(--text-muted); font-size: .68rem; font-weight: 600;
    text-transform: uppercase; letter-spacing: .1em; margin: 1.25rem 0 .4rem;
}

.status-box {
    border-radius: var(--radius-sm); padding: .65rem .8rem;
    font-size: .78rem; line-height: 1.45; border: 1px solid;
    margin-bottom: .25rem;
}
.status-box .k { font-weight: 600; display: block; }
.status-box.ready   { background: var(--green-soft); border-color: #bfe3cc; color: var(--green); }
.status-box.pending { background: var(--amber-soft); border-color: #f2d9ae; color: var(--amber); }

.sidebar-foot { color: var(--text-muted); font-size: .68rem; line-height: 1.6; margin-top: 2rem; }

/* ── Buttons ──────────────────────────────────────────────── */
.stButton > button {
    background: var(--accent) !important;
    color: #fff !important;
    border: 1px solid var(--accent) !important;
    border-radius: var(--radius-sm) !important;
    padding: 0.5rem 1.15rem !important;
    font-weight: 600 !important;
    font-size: .9rem !important;
    box-shadow: var(--shadow-card);
    transition: background .15s ease, border-color .15s ease, box-shadow .15s ease !important;
}
.stButton > button:hover {
    background: var(--accent-strong) !important;
    border-color: var(--accent-strong) !important;
    box-shadow: var(--shadow-lift);
}
.stButton > button:disabled {
    background: #e6e9ef !important; border-color: #e6e9ef !important;
    color: #8792a5 !important; box-shadow: none; cursor: not-allowed !important;
}
.stButton > button[kind="secondary"],
.stButton > button[data-testid="stBaseButton-secondary"] {
    background: var(--bg-surface) !important;
    border: 1px solid var(--border) !important;
    color: var(--text-primary) !important;
    box-shadow: none;
}
.stButton > button[kind="secondary"]:hover,
.stButton > button[data-testid="stBaseButton-secondary"]:hover {
    background: var(--bg-hover) !important;
    border-color: var(--accent-glow) !important;
}

/* Sidebar navigation: quiet rows, active row = tinted with accent rule */
[data-testid="stSidebar"] .stButton > button {
    justify-content: flex-start !important;
    text-align: left !important;
    font-weight: 500 !important;
    background: transparent !important;
    border: 1px solid transparent !important;
    border-left: 3px solid transparent !important;
    color: var(--text-secondary) !important;
    box-shadow: none !important;
    border-radius: var(--radius-sm) !important;
}
[data-testid="stSidebar"] .stButton > button > div,
[data-testid="stSidebar"] .stButton > button [data-testid="stMarkdownContainer"],
[data-testid="stSidebar"] .stButton > button p {
    width: 100%;
    justify-content: flex-start !important;
    text-align: left !important;
}
[data-testid="stSidebar"] .stButton > button:hover {
    background: var(--bg-hover) !important;
    color: var(--text-primary) !important;
}
[data-testid="stSidebar"] .stButton > button[data-testid="stBaseButton-primary"],
[data-testid="stSidebar"] .stButton > button[kind="primary"] {
    background: var(--accent-soft) !important;
    color: var(--accent-strong) !important;
    border-left: 3px solid var(--accent) !important;
    font-weight: 600 !important;
}

/* ── Inputs ───────────────────────────────────────────────── */
[data-testid="stFileUploader"] section,
[data-testid="stFileUploaderDropzone"] {
    background: var(--bg-surface) !important;
    border: 1.5px dashed var(--border) !important;
    border-radius: var(--radius-card) !important;
    color: var(--text-secondary) !important;
}
[data-testid="stFileUploader"] { padding: 0 !important; background: transparent !important; }
[data-testid="stFileUploaderDropzone"]:hover { border-color: var(--accent) !important; background: var(--accent-soft) !important; }

.stTextInput input, .stTextArea textarea,
[data-baseweb="select"] > div, [data-baseweb="input"] {
    background: var(--bg-surface) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--radius-sm) !important;
    color: var(--text-primary) !important;
}
.stTextInput input::placeholder, .stTextArea textarea::placeholder { color: var(--text-muted) !important; }
.stTextArea textarea:focus, .stTextInput input:focus { border-color: var(--accent) !important; }

/* ── Chat ─────────────────────────────────────────────────── */
[data-testid="stChatMessage"] {
    background: var(--bg-surface) !important;
    border: 1px solid var(--border-soft) !important;
    border-radius: var(--radius-card) !important;
    padding: 1rem 1.15rem !important;
    margin-bottom: .6rem !important;
    box-shadow: var(--shadow-card);
}
[data-testid="stChatInput"] { background: var(--bg-surface) !important; border-radius: var(--radius-card) !important; }

/* ── Tabs ─────────────────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] {
    background: transparent !important;
    border-bottom: 1px solid var(--border) !important;
    gap: .25rem !important;
}
.stTabs [data-baseweb="tab"] {
    background: transparent !important;
    color: var(--text-secondary) !important;
    padding: .55rem 1rem !important;
    font-weight: 500;
}
.stTabs [aria-selected="true"] { color: var(--accent-strong) !important; font-weight: 600; }
.stTabs [data-baseweb="tab-highlight"] { background: var(--accent) !important; }

/* ── Alerts, expanders, progress ──────────────────────────── */
[data-testid="stAlert"] { border-radius: var(--radius-sm) !important; border: 1px solid var(--border-soft) !important; }
[data-testid="stExpander"] {
    background: var(--bg-surface); border: 1px solid var(--border-soft) !important;
    border-radius: var(--radius-sm) !important; box-shadow: var(--shadow-card);
}
[data-testid="stExpander"] summary { color: var(--text-primary) !important; font-weight: 500; }
.stProgress > div > div > div { background: var(--accent) !important; border-radius: 999px !important; }
.stProgress > div > div { background: #e6e9ef !important; border-radius: 999px !important; }
hr { border-color: var(--border-soft) !important; }

/* ── Metric cards (signature: status-coloured left rule) ──── */
.metric-card {
    background: var(--bg-card);
    border: 1px solid var(--border-soft);
    border-left: 4px solid var(--accent);
    border-radius: var(--radius-card);
    padding: 1.15rem 1.35rem;
    box-shadow: var(--shadow-card);
    height: 100%;
    min-height: 122px;
    transition: box-shadow .15s ease, transform .15s ease;
}
.metric-card:hover { box-shadow: var(--shadow-lift); transform: translateY(-1px); }
.metric-card .label {
    color: var(--text-muted); font-size: .7rem; font-weight: 600;
    text-transform: uppercase; letter-spacing: .09em; margin-bottom: .5rem;
}
.metric-card .value {
    color: var(--text-primary); font-size: 2.1rem; font-weight: 700;
    line-height: 1; letter-spacing: -0.03em;
}
.metric-card .sublabel { color: var(--text-secondary); font-size: .8rem; margin-top: .4rem; }
.metric-card.green { border-left-color: var(--green); }
.metric-card.amber { border-left-color: var(--amber); }
.metric-card.red   { border-left-color: var(--red);   }
.metric-card.blue  { border-left-color: var(--blue);  }

/* ── Section headers ──────────────────────────────────────── */
.section-header {
    color: var(--text-primary); font-size: 1.35rem; font-weight: 700;
    letter-spacing: -0.02em; padding-bottom: .65rem;
    border-bottom: 1px solid var(--border); margin: .25rem 0 1.25rem;
}
.section-header.sub { font-size: 1.02rem; font-weight: 600; border-bottom-color: var(--border-soft); margin-top: 1.5rem; }

/* ── Pills and badges ─────────────────────────────────────── */
.skill-pill {
    display: inline-block; background: var(--accent-soft); color: var(--accent-strong);
    border: 1px solid var(--accent-glow); border-radius: 999px;
    padding: .2rem .75rem; font-size: .78rem; font-weight: 500; margin: .15rem;
}
.skill-pill.missing { background: var(--red-soft); color: var(--red); border-color: #f3c3c3; }
.skill-pill.matched { background: var(--green-soft); color: var(--green); border-color: #bfe3cc; }

.badge {
    display: inline-block; border-radius: 999px; padding: .15rem .65rem;
    font-size: .72rem; font-weight: 700; letter-spacing: .03em;
    border: 1px solid var(--border); background: var(--bg-hover); color: var(--text-secondary);
}
.badge.high, .badge.hard    { background: var(--red-soft);   color: var(--red);   border-color: #f3c3c3; }
.badge.medium               { background: var(--amber-soft); color: var(--amber); border-color: #f2d9ae; }
.badge.low, .badge.easy     { background: var(--green-soft); color: var(--green); border-color: #bfe3cc; }
.badge.type                 { background: var(--accent-soft); color: var(--accent-strong); border-color: var(--accent-glow); }

/* ── Content blocks ───────────────────────────────────────── */
.panel {
    background: var(--bg-card); border: 1px solid var(--border-soft);
    border-radius: var(--radius-card); padding: 1.25rem 1.4rem; box-shadow: var(--shadow-card);
}
.panel .q { font-size: 1.08rem; font-weight: 500; line-height: 1.6; color: var(--text-primary); margin: .75rem 0 0; }
.rec-row {
    background: var(--bg-card); border: 1px solid var(--border-soft);
    border-left: 3px solid var(--accent); border-radius: var(--radius-sm);
    padding: .7rem 1rem; margin-bottom: .5rem; color: var(--text-primary); font-size: .9rem; line-height: 1.5;
}
.score-inline { font-size: 1.5rem; font-weight: 700; letter-spacing: -0.02em; }
.score-inline.good { color: var(--green); }
.score-inline.ok   { color: var(--amber); }
.score-inline.poor { color: var(--red); }

.hero-name { font-size: 1.9rem; font-weight: 800; letter-spacing: -0.03em; margin: 0 0 .15rem; color: var(--text-primary); }
.hero-sub  { color: var(--text-secondary); font-size: 1rem; margin: 0 0 1.25rem; }
.hero-sub strong { color: var(--text-primary); }

/* ── Empty state ──────────────────────────────────────────── */
.empty-state {
    text-align: center; padding: 3.5rem 2rem; max-width: 520px; margin: 2rem auto;
    border: 1px dashed var(--border); border-radius: var(--radius-card); background: var(--bg-surface);
}
.empty-state .title { font-size: 1.15rem; font-weight: 700; color: var(--text-primary); margin-bottom: .4rem; }
.empty-state .message { font-size: .95rem; color: var(--text-secondary); line-height: 1.55; }
.empty-icon {
    width: 56px; height: 56px; margin: 0 auto 1rem; border-radius: 16px;
    background: var(--accent-soft); color: var(--accent);
    display: flex; align-items: center; justify-content: center;
}

/* ── Icons ────────────────────────────────────────────────── */
svg.icon { display: block; flex-shrink: 0; }

/* ── Page header ──────────────────────────────────────────── */
.page-header { margin: 0 0 1.5rem; }
.ph-kicker {
    color: var(--accent); font-size: .72rem; font-weight: 700;
    text-transform: uppercase; letter-spacing: .14em; margin-bottom: .35rem;
}
h1.ph-title {
    font-size: 2rem !important; font-weight: 800 !important; letter-spacing: -0.035em !important;
    margin: 0 !important; padding: 0 !important; line-height: 1.15 !important;
}
.ph-sub { color: var(--text-secondary); font-size: 1rem; margin: .5rem 0 0; max-width: 60ch; line-height: 1.55; }

/* ── Hero banner ──────────────────────────────────────────── */
.hero {
    position: relative; overflow: hidden; color: #fff;
    border-radius: 18px; padding: 1.9rem 2.1rem; margin-bottom: 1.25rem;
    background:
        radial-gradient(600px 220px at 100% 0%, rgba(255,255,255,.20), transparent 60%),
        radial-gradient(420px 260px at 0% 120%, rgba(255,255,255,.10), transparent 60%),
        linear-gradient(135deg, #1a37a8 0%, #2b59e6 55%, #4d7cff 100%);
    box-shadow: 0 10px 30px rgba(43, 89, 230, .28);
}
.hero::after {
    content: ""; position: absolute; right: -40px; bottom: -70px; width: 240px; height: 240px;
    border-radius: 50%; border: 36px solid rgba(255,255,255,.08);
}
.hero-eyebrow { font-size: .72rem; font-weight: 700; letter-spacing: .16em; text-transform: uppercase; opacity: .8; }
.hero-title { font-size: 2.25rem; font-weight: 800; letter-spacing: -0.035em; line-height: 1.15; margin: .35rem 0 .2rem; color: #fff; }
.hero-role { font-size: 1.02rem; opacity: .92; }
.hero-role strong { font-weight: 700; }
.hero-chips { margin-top: 1rem; display: flex; flex-wrap: wrap; gap: .5rem; position: relative; z-index: 1; }
.hero-chip {
    background: rgba(255,255,255,.16); border: 1px solid rgba(255,255,255,.28);
    border-radius: 999px; padding: .25rem .8rem; font-size: .78rem; font-weight: 500;
}

/* ── Gauge ────────────────────────────────────────────────── */
.gauge {
    display: flex; flex-direction: column; align-items: center; text-align: center;
    background: var(--bg-card); border: 1px solid var(--border-soft);
    border-radius: var(--radius-card); box-shadow: var(--shadow-card); padding: 1.25rem 1rem 1.1rem;
    height: 100%;
}
.gauge .g-track { stroke: #e8ecf3; }
.gauge .g-arc { stroke: var(--accent); }
.gauge.green .g-arc { stroke: var(--green); }
.gauge.amber .g-arc { stroke: #d97706; }
.gauge.red   .g-arc { stroke: var(--red); }
.gauge.blue  .g-arc { stroke: var(--blue); }
.gauge .g-text { font-size: 22px; font-weight: 800; fill: var(--text-primary); letter-spacing: -0.5px; }
.gauge .g-label { font-size: .78rem; font-weight: 600; text-transform: uppercase; letter-spacing: .09em; color: var(--text-muted); margin-top: .35rem; }
.gauge .g-sub { font-size: .85rem; color: var(--text-secondary); margin-top: .15rem; }

/* ── Bars ─────────────────────────────────────────────────── */
.bar-row { margin-bottom: .95rem; }
.bar-top { display: flex; justify-content: space-between; font-size: .86rem; margin-bottom: .35rem; color: var(--text-secondary); }
.bar-top strong { color: var(--text-primary); font-weight: 700; }
.bar-track { height: 8px; border-radius: 999px; background: #e8ecf3; overflow: hidden; }
.bar-fill { height: 100%; border-radius: 999px; background: var(--accent); }
.bar-fill.green { background: var(--green); }
.bar-fill.blue  { background: var(--blue); }
.bar-fill.amber { background: #d97706; }
.bar-fill.red   { background: var(--red); }

/* ── Steps ────────────────────────────────────────────────── */
.steps { display: grid; grid-template-columns: repeat(3, 1fr); gap: .75rem; margin-bottom: 1.5rem; }
.step {
    display: flex; gap: .8rem; align-items: flex-start; padding: 1rem 1.1rem;
    background: var(--bg-card); border: 1px solid var(--border-soft);
    border-radius: var(--radius-card); box-shadow: var(--shadow-card);
}
.step-num {
    width: 28px; height: 28px; border-radius: 50%; flex-shrink: 0;
    display: flex; align-items: center; justify-content: center;
    font-size: .8rem; font-weight: 700;
    background: #eef1f6; color: var(--text-secondary);
}
.step.current { border-color: var(--accent-glow); background: var(--accent-soft); }
.step.current .step-num { background: var(--accent); color: #fff; }
.step.done .step-num { background: var(--green); color: #fff; }
.step-title { font-weight: 700; font-size: .92rem; color: var(--text-primary); }
.step-desc  { font-size: .8rem; color: var(--text-secondary); margin-top: .1rem; line-height: 1.4; }

/* ── Card polish ──────────────────────────────────────────── */
.panel.pad-lg { padding: 1.5rem 1.75rem; }
.card-title { font-size: .95rem; font-weight: 700; color: var(--text-primary); margin: 0 0 .85rem; }
.card-note  { font-size: .85rem; color: var(--text-secondary); margin: 0 0 .9rem; line-height: 1.5; }
.rec-row { transition: transform .12s ease, box-shadow .12s ease; }
.rec-row:hover { transform: translateX(2px); box-shadow: var(--shadow-card); }

.stApp {
    background:
        radial-gradient(900px 380px at 85% -10%, rgba(43, 89, 230, .07), transparent 70%),
        var(--bg-base) !important;
}
@keyframes rise { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: none; } }
.metric-card, .gauge, .panel, .step, .hero, .page-header { animation: rise .35s ease both; }

/* ── Small screens ────────────────────────────────────────── */
@media (max-width: 768px) {
    .block-container { padding: 1rem .75rem 2rem !important; }
    .metric-card { padding: 1rem; }
    .metric-card .value { font-size: 1.6rem; }
    .hero { padding: 1.4rem 1.25rem; }
    .hero-title { font-size: 1.7rem; }
    .steps { grid-template-columns: 1fr; }
    h1.ph-title { font-size: 1.6rem !important; }
    .hero-name { font-size: 1.5rem; }
    [data-testid="stHorizontalBlock"] { flex-wrap: wrap; gap: .75rem !important; }
    [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] { min-width: 100% !important; }
}
</style>
"""
