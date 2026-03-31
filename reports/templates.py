"""PDF report styling constants."""
from reportlab.lib.colors import HexColor

# Brand colors
PRIMARY = HexColor("#1e3a5f")       # Dark navy
SECONDARY = HexColor("#2563eb")     # Blue
ACCENT = HexColor("#22c55e")        # Green
DANGER = HexColor("#ef4444")        # Red
LIGHT_GRAY = HexColor("#f3f4f6")
MEDIUM_GRAY = HexColor("#9ca3af")
DARK_TEXT = HexColor("#1f2937")
WHITE = HexColor("#ffffff")

# Table styling
TABLE_HEADER_BG = PRIMARY
TABLE_HEADER_TEXT = WHITE
TABLE_ALT_ROW = HexColor("#f9fafb")
TABLE_BORDER = HexColor("#d1d5db")
