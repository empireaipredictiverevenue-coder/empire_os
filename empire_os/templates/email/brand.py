"""
Empire AI brand kit — single source of truth for visual identity.

Dark theme, neon green + cyan accents. Used across email templates,
landing pages, agent SOUL prompts, and any other surface.

Avenues: each business vertical gets its own accent variant of the
base palette. Add new avenue by appending to AVENUES — all templates
auto-pick up the new option.
"""

# ── Core palette ──────────────────────────────────────────
BG_DEEP        = "#050810"   # near-black page bg
BG_PANEL       = "#0c1320"   # card / section bg
BG_ELEVATED    = "#131c2e"   # input / hover bg
BORDER         = "#1f2a44"   # subtle separators
BORDER_STRONG  = "#2d3d63"   # emphasis borders

NEON_GREEN     = "#39ff88"   # primary accent — CTAs, highlights
NEON_GREEN_DIM = "#1fbf63"   # hover state, secondary
CYAN           = "#22e3ff"   # secondary accent — links, info
CYAN_DIM       = "#0fb8d4"   # hover

TEXT_PRIMARY   = "#e6f1ff"   # main copy
TEXT_SECONDARY = "#9bb0c9"   # supporting copy
TEXT_MUTED     = "#5a6c85"   # captions, footer

SUCCESS        = NEON_GREEN
WARNING        = "#ffd166"
DANGER         = "#ff5577"

# ── Type ───────────────────────────────────────────────────
FONT_STACK = (
    "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue',"
    " Arial, sans-serif"
)
FONT_MONO = (
    "'SF Mono', Menlo, Consolas, 'Liberation Mono', monospace"
)

# ── Identity strings ──────────────────────────────────────
COMPANY_NAME    = "Empire AI"
COMPANY_PARENT  = "Empire OS"
COMPANY_URL     = "https://empire-ai.co.uk"
SUPPORT_EMAIL   = "ops@empire-ai.co.uk"
UNSUB_BASE      = f"{COMPANY_URL}/unsub"

# ── Avenues (multi-vertical) ──────────────────────────────
# Each avenue: id, display name, tagline, accent override (optional),
# default subject prefix, primary CTA, target audience hint.
AVENUES: dict[str, dict] = {
    "leadgen": {
        "id":            "leadgen",
        "name":          "Empire OS — Lead Delivery",
        "tagline":       "Pay-per-delivered leads for top agencies.",
        "accent":        NEON_GREEN,        # primary brand color
        "accent2":       CYAN,
        "subject_prefix": "",
        "primary_cta":   "Send sample lead",
        "audience":      "B2B agency owners, lead buyers, contractors",
    },
    "paypercall": {
        "id":            "paypercall",
        "name":          "Empire OS — Pay-Per-Call",
        "tagline":       "Live transfers, settled on connect.",
        "accent":        NEON_GREEN,
        "accent2":       CYAN,
        "subject_prefix": "[PPC] ",
        "primary_cta":   "Get sample call",
        "audience":      "Call buyers, pay-per-call networks",
    },
    "saas": {
        "id":            "saas",
        "name":          "Empire OS — SaaS",
        "tagline":       "Operator-grade tools for vertical agencies.",
        "accent":        CYAN,
        "accent2":       NEON_GREEN,
        "subject_prefix": "",
        "primary_cta":   "Book a demo",
        "audience":      "Agency operators, SaaS buyers",
    },
    "loans": {
        "id":            "loans",
        "name":          "Empire AI Capital",
        "tagline":       "Working capital for vertical operators.",
        "accent":        NEON_GREEN,
        "accent2":       CYAN,
        "subject_prefix": "",
        "primary_cta":   "Check eligibility",
        "audience":      "SMB owners seeking working capital",
    },
    "default": {
        "id":            "default",
        "name":          COMPANY_NAME,
        "tagline":       "Empire AI — operator-grade infrastructure.",
        "accent":        NEON_GREEN,
        "accent2":       CYAN,
        "subject_prefix": "",
        "primary_cta":   "Reply to this email",
        "audience":      "general",
    },
}

DEFAULT_AVENUE = "leadgen"


def get_avenue(avenue_id: str | None) -> dict:
    """Resolve an avenue config by id, falling back to default."""
    return AVENUES.get(avenue_id or DEFAULT_AVENUE, AVENUES[DEFAULT_AVENUE])


def avenue_ids() -> list[str]:
    """All configured avenue ids in declaration order."""
    return list(AVENUES.keys())


def css_vars(avenue_id: str | None = None) -> str:
    """Inline :root CSS variables for an avenue. Drop into <style> blocks."""
    a = get_avenue(avenue_id)
    return f"""
    :root {{
      --bg-deep:       {BG_DEEP};
      --bg-panel:      {BG_PANEL};
      --bg-elevated:   {BG_ELEVATED};
      --border:        {BORDER};
      --border-strong: {BORDER_STRONG};
      --accent:        {a['accent']};
      --accent-dim:    {a['accent2']};
      --text-primary:  {TEXT_PRIMARY};
      --text-secondary:{TEXT_SECONDARY};
      --text-muted:    {TEXT_MUTED};
      --font-stack:    {FONT_STACK};
    }}
    """