"""Shared formatting and utility functions."""

import streamlit as st


def fmt_currency(value):
    """Format a number as USD currency."""
    if value is None:
        return "$0.00"
    return f"${value:,.2f}"


def fmt_pct(value):
    """Format a number as percentage."""
    if value is None:
        return "0.0%"
    return f"{value:.1f}%"


def calc_margin(cost, charge):
    """Calculate profit margin percentage."""
    if charge == 0:
        return 0.0
    return ((charge - cost) / charge) * 100


@st.cache_data(ttl=30)
def _get_sidebar_stats():
    """Fetch aggregated sidebar stats via a single SQL query instead of loading all rows."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from db.database import query

    row = query("""
        SELECT
            COUNT(*)                                             AS total_count,
            SUM(CASE WHEN status = 'Ongoing' THEN 1 ELSE 0 END) AS active_count,
            COALESCE(SUM(total_profit), 0)                       AS total_profit,
            COALESCE(SUM(grand_total_charge), 0)                 AS total_charge,
            COALESCE(SUM(grand_total_cost), 0)                   AS total_cost
        FROM v_project_profit
    """, fetchone=True)
    if not row or row["total_count"] == 0:
        return None
    row["margin"] = calc_margin(row["total_cost"], row["total_charge"])
    return row


def sidebar_quick_stats():
    """Show quick stats in the sidebar across all pages."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from db.database import query

    st.sidebar.markdown("### Quick Stats")

    stats = _get_sidebar_stats()

    if stats:
        st.sidebar.metric("Active Projects", stats["active_count"])
        st.sidebar.metric("Running Profit", f"${stats['total_profit']:,.0f}")
        st.sidebar.metric("Margin", f"{stats['margin']:.1f}%")
    else:
        st.sidebar.caption("No projects yet")
