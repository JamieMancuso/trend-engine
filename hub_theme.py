"""HUB-64 theme for the trend-engine Streamlit app.

One import restyles the whole app to match the phone hub (hub64.netlify.app):
true-black ground, Doto dot-matrix headings with a lemon glow, notched panels,
and the shared accent palette. Layout and behaviour are untouched — this is
paint only.

USAGE (top of every page, right after st.set_page_config):
    import hub_theme
    hub_theme.inject()

Colors are exported so renderers can stay in-palette:
    hub_theme.LEMON, hub_theme.LEAF, hub_theme.FLAG_COLORS, ...
"""

import streamlit as st

# ---- palette (mirrors the hub's CSS variables) ------------------------------
BG      = "#000002"   # true black ground
PANEL   = "#0a0c13"   # barely-lifted card
PANEL2  = "#10131d"   # hover / secondary fill
HAIR    = "#181d2a"   # hairline borders
INK     = "#eef4f8"   # primary text
DIM     = "#8592a8"   # secondary text
MUTED   = "#5c6678"   # tertiary text

LEMON   = "#f2d84b"   # primary accent (headings, active state)
LEAF    = "#8ec07c"   # positive / go
TEAL    = "#5fb3b3"   # links, neutral data
AMBER   = "#e8a84c"   # warning / watch
RED     = "#e06a52"   # negative
VIOLET  = "#b48ee0"   # extra categorical
PINK    = "#c792ea"   # extra categorical

GLOW_Y  = "0 0 10px rgba(242,216,75,.6)"
GLOW_G  = "0 0 8px rgba(142,192,124,.5)"

# Score-tier badges, re-cut in hub colors (same keys as the original).
FLAG_COLORS = {
    "thesis":    {"bg": "#201808", "fg": LEMON},
    "watchlist": {"bg": "#0c1a1a", "fg": TEAL},
    "longshot":  {"bg": "#0e1a10", "fg": LEAF},
    "skip":      {"bg": "#10131d", "fg": MUTED},
}

# Ordered palette for categorical charts (st.bar_chart color=..., etc.)
CHART_SERIES = [TEAL, LEAF, AMBER, VIOLET, RED, PINK, "#62c4c4", "#f0a86e"]

_CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Doto:wght@700;900&display=swap');

:root {{
  --hub-bg:{BG}; --hub-panel:{PANEL}; --hub-panel2:{PANEL2}; --hub-hair:{HAIR};
  --hub-ink:{INK}; --hub-dim:{DIM}; --hub-muted:{MUTED};
  --hub-lemon:{LEMON}; --hub-leaf:{LEAF}; --hub-teal:{TEAL};
  --hub-amber:{AMBER}; --hub-red:{RED};
  --hub-glow-y:{GLOW_Y};
}}

/* ---------- ground ---------- */
[data-testid="stAppViewContainer"], .stApp, [data-testid="stMain"] {{
  background:{BG} !important; color:{INK};
}}
[data-testid="stHeader"] {{ background:{BG} !important; border-bottom:1px solid {HAIR}; }}
[data-testid="stToolbar"] {{ right:8px; }}
[data-testid="stDecoration"] {{
  background:repeating-linear-gradient(90deg,{LEMON} 0 4px,transparent 4px 8px) !important;
  height:3px !important;
}}
[data-testid="stSidebar"], [data-testid="stSidebarContent"] {{
  background:{PANEL} !important; border-right:1px solid {HAIR};
}}

/* ---------- type ---------- */
h1, h2, h3, h4,
[data-testid="stMarkdownContainer"] h1,
[data-testid="stMarkdownContainer"] h2,
[data-testid="stMarkdownContainer"] h3 {{
  font-family:'Doto', ui-monospace, monospace !important;
  font-weight:900 !important;
  letter-spacing:.04em;
  color:{LEMON} !important;
  text-shadow:{GLOW_Y};
}}
h1 {{ font-size:2.05rem !important; }}
h2 {{ font-size:1.5rem !important; color:{INK} !important; text-shadow:none; }}
h3 {{ font-size:1.15rem !important; color:{DIM} !important; text-shadow:none;
     text-transform:uppercase; }}
[data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] li,
[data-testid="stMarkdownContainer"] span {{ color:{INK}; }}
[data-testid="stMarkdownContainer"] a {{ color:{TEAL} !important; text-decoration:none; }}
[data-testid="stMarkdownContainer"] a:hover {{ text-decoration:underline; }}
[data-testid="stMarkdownContainer"] code {{
  background:{PANEL2}; color:{TEAL}; padding:1px 6px; border-radius:0;
}}
hr, [data-testid="stMarkdownContainer"] hr {{
  border:0 !important; height:2px !important;
  background:repeating-linear-gradient(90deg,{HAIR} 0 5px,transparent 5px 9px) !important;
}}

/* ---------- captions / small print ---------- */
[data-testid="stCaptionContainer"], .stCaption, small {{ color:{MUTED} !important; }}

/* ---------- widgets ---------- */
.stButton > button, .stDownloadButton > button,
[data-testid^="stBaseButton"], [data-testid="baseButton-secondary"] {{
  background:{PANEL} !important; color:{INK} !important;
  border:1px solid {HAIR} !important; border-radius:0 !important;
}}
.stButton > button:hover, .stDownloadButton > button:hover,
[data-testid^="stBaseButton"]:hover {{
  color:{LEMON} !important; border-color:#4a4420 !important; background:#14120a !important;
}}
/* the digest renders paper titles as buttons — keep them left-aligned and quiet */
[data-testid^="stBaseButton"] p {{ color:inherit !important; }}
label, [data-testid="stWidgetLabel"], [data-testid="stWidgetLabel"] p {{
  font-family:'Doto', ui-monospace, monospace !important; font-weight:900 !important;
  color:{DIM} !important; letter-spacing:.03em;
}}
[data-baseweb="select"] > div, [data-baseweb="input"] > div,
.stTextInput input, .stNumberInput input, .stTextArea textarea {{
  background:{PANEL} !important; border-color:{HAIR} !important;
  border-radius:0 !important; color:{INK} !important;
}}
[data-baseweb="popover"] li {{ background:{PANEL} !important; color:{INK} !important; }}
[data-baseweb="popover"] li:hover {{ background:{PANEL2} !important; }}
[data-baseweb="tag"] {{
  background:{PANEL2} !important; color:{TEAL} !important; border-radius:0 !important;
}}
/* sliders + toggles */
[data-testid="stSlider"] [data-baseweb="slider"] div[role="slider"] {{
  background:{LEMON} !important; box-shadow:{GLOW_Y};
}}
[data-testid="stCheckbox"] svg, [data-testid="stToggle"] svg {{ color:{LEMON}; }}

/* ---------- tabs ---------- */
.stTabs [data-baseweb="tab-list"] {{ gap:2px; border-bottom:1px solid {HAIR}; }}
.stTabs [data-baseweb="tab"] {{
  font-family:'Doto', ui-monospace, monospace !important; font-weight:900 !important;
  color:{MUTED} !important; background:transparent !important;
}}
.stTabs [aria-selected="true"] {{ color:{LEMON} !important; text-shadow:{GLOW_Y}; }}
.stTabs [data-baseweb="tab-highlight"] {{
  background:repeating-linear-gradient(90deg,{LEMON} 0 3px,transparent 3px 6px) !important;
  height:3px !important;
}}

/* ---------- panels: expanders, bordered containers, metrics ---------- */
[data-testid="stExpander"], [data-testid="stExpander"] details {{
  background:{PANEL}; border:1px solid {HAIR} !important; border-radius:0 !important;
}}
[data-testid="stExpander"] summary {{
  font-family:'Doto', ui-monospace, monospace !important; font-weight:900 !important;
  color:{DIM} !important;
}}
[data-testid="stExpander"] summary:hover {{ color:{LEMON} !important; }}
[data-testid="stMetric"] {{
  background:{PANEL}; border:1px solid {HAIR}; padding:12px 14px;
  clip-path:polygon(6px 0,calc(100% - 6px) 0,100% 6px,100% calc(100% - 6px),
    calc(100% - 6px) 100%,6px 100%,0 calc(100% - 6px),0 6px);
}}
[data-testid="stMetricLabel"], [data-testid="stMetricLabel"] p {{
  font-family:'Doto', ui-monospace, monospace !important; font-weight:900 !important;
  color:{MUTED} !important; text-transform:uppercase; letter-spacing:.06em;
}}
[data-testid="stMetricValue"] {{
  font-family:'Doto', ui-monospace, monospace !important; font-weight:700 !important;
  color:{LEAF} !important; text-shadow:{GLOW_G};
  /* Doto runs wide — shrink so multi-part values ("0T · 10W · 0L") don't truncate */
  font-size:clamp(1.1rem, 2.1vw, 1.7rem) !important;
}}
[data-testid="stMetricDelta"] {{ font-family:'Doto', ui-monospace, monospace !important; }}

/* ---------- alerts ---------- */
[data-testid="stAlert"] {{ border-radius:0 !important; border-left:3px solid {TEAL}; }}

/* ---------- tables / dataframes ---------- */
[data-testid="stDataFrame"], [data-testid="stTable"] {{
  border:1px solid {HAIR}; border-radius:0;
}}
[data-testid="stTable"] th {{
  font-family:'Doto', ui-monospace, monospace !important; font-weight:900 !important;
  color:{MUTED} !important; text-transform:uppercase;
}}

/* ---------- progress ---------- */
[data-testid="stProgress"] > div > div > div {{
  background:repeating-linear-gradient(90deg,{LEAF} 0 5px,transparent 5px 8px) !important;
}}

/* ---------- sidebar page nav ---------- */
[data-testid="stSidebarNav"] a {{
  font-family:'Doto', ui-monospace, monospace !important; font-weight:900 !important;
  border-radius:0 !important;
}}
[data-testid="stSidebarNav"] a span {{ color:{DIM} !important; }}
[data-testid="stSidebarNav"] a:hover {{ background:{PANEL2} !important; }}
[data-testid="stSidebarNav"] li a[aria-current="page"],
[data-testid="stSidebarNav"] a[aria-current="page"] {{
  background:#14120a !important; border-left:3px solid {LEMON} !important;
}}
[data-testid="stSidebarNav"] a[aria-current="page"] span {{
  color:{LEMON} !important; text-shadow:{GLOW_Y};
}}

/* ---------- multiselect tags (tone down the default primary fill) ---------- */
[data-baseweb="tag"], span[data-baseweb="tag"],
[data-testid="stMultiSelectTagsContainer"] span[role="group"] > span {{
  background:{PANEL2} !important; border:1px solid {HAIR} !important;
  border-radius:0 !important; color:{TEAL} !important;
}}
[data-testid="stMultiSelectTagsContainer"] span[role="group"] > span span {{
  color:{TEAL} !important;
}}
[data-baseweb="tag"] span, [data-baseweb="tag"] div {{ color:{TEAL} !important; }}
[data-testid="stMultiSelectTagsContainer"] svg, [data-baseweb="tag"] svg {{ fill:{DIM} !important; }}

/* ---------- phone ---------- */
@media (max-width:700px) {{
  .block-container {{ padding:0.8rem 0.7rem 3rem !important; }}
  h1 {{ font-size:1.5rem !important; }}
  h2 {{ font-size:1.15rem !important; }}
  [data-testid="stMetricValue"] {{ font-size:1.5rem !important; }}
}}
</style>
"""


def inject():
    """Paint the current page in the HUB-64 theme. Call once, after set_page_config."""
    st.markdown(_CSS, unsafe_allow_html=True)


def badge(text, fg=LEMON, bg=PANEL2):
    """Small pixel-ish inline badge, for use inside st.markdown(unsafe_allow_html=True)."""
    return (f'<span style="font-family:Doto,monospace;font-weight:900;font-size:11px;'
            f'padding:2px 7px;background:{bg};color:{fg};letter-spacing:.04em">{text}</span>')
