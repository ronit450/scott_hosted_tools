"""Professional PDF report generator using ReportLab."""
from io import BytesIO
from datetime import datetime
from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable, Image,
)

LOGO_PATH = Path(__file__).parent.parent / "assets" / "logo.jpeg"

from reports.templates import (
    PRIMARY, SECONDARY, LIGHT_GRAY, DARK_TEXT, WHITE,
    TABLE_HEADER_BG, TABLE_HEADER_TEXT, TABLE_ALT_ROW, TABLE_BORDER,
)


def _get_styles():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        "ReportTitle", parent=styles["Heading1"],
        fontSize=22, textColor=WHITE, spaceAfter=4,
        fontName="Helvetica-Bold",
    ))
    styles.add(ParagraphStyle(
        "SubInfo", parent=styles["Normal"],
        fontSize=10, textColor=WHITE, spaceAfter=2,
        fontName="Helvetica",
    ))
    styles.add(ParagraphStyle(
        "SectionHeader", parent=styles["Heading2"],
        fontSize=14, textColor=PRIMARY, spaceBefore=16, spaceAfter=8,
        fontName="Helvetica-Bold",
    ))
    styles.add(ParagraphStyle(
        "BodyText2", parent=styles["Normal"],
        fontSize=10, textColor=DARK_TEXT, spaceAfter=4,
        fontName="Helvetica",
    ))
    styles.add(ParagraphStyle(
        "SmallRight", parent=styles["Normal"],
        fontSize=8, textColor=DARK_TEXT, alignment=TA_RIGHT,
    ))
    return styles


def _fmt(val):
    """Format currency."""
    if val is None:
        return "$0.00"
    return f"${val:,.2f}"


def _build_header_table(project, styles):
    """Build the colored header section as a table with logo."""
    title = project.get("report_title", "Report")
    pws = project.get("pws_number", "")
    status = project.get("status", "")

    # Build text column
    text_parts = [
        Paragraph("Stone Harp Analytics Report", styles["ReportTitle"]),
        Paragraph(f"PWS: {pws}  |  {title}", styles["SubInfo"]),
        Paragraph(f"Status: {status}", styles["SubInfo"]),
    ]

    # Try to include logo
    if LOGO_PATH.exists():
        logo = Image(str(LOGO_PATH), width=0.9 * inch, height=0.9 * inch)
        header_data = [[logo, text_parts]]
        header_table = Table(header_data, colWidths=[1.1 * inch, 6.4 * inch])
        header_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), PRIMARY),
            ("TOPPADDING", (0, 0), (-1, -1), 12),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
            ("LEFTPADDING", (0, 0), (-1, -1), 12),
            ("RIGHTPADDING", (0, 0), (-1, -1), 12),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
    else:
        header_data = [
            [Paragraph("Stone Harp Analytics Report", styles["ReportTitle"])],
            [Paragraph(f"PWS: {pws}  |  {title}", styles["SubInfo"])],
            [Paragraph(f"Status: {status}", styles["SubInfo"])],
        ]
        header_table = Table(header_data, colWidths=[7.5 * inch])
        header_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), PRIMARY),
            ("TOPPADDING", (0, 0), (-1, 0), 16),
            ("BOTTOMPADDING", (0, -1), (-1, -1), 12),
            ("LEFTPADDING", (0, 0), (-1, -1), 16),
            ("RIGHTPADDING", (0, 0), (-1, -1), 16),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
    return header_table


def _build_metadata(project, styles):
    """Build project metadata section."""
    elements = []
    elements.append(Spacer(1, 12))
    elements.append(Paragraph("Project Details", styles["SectionHeader"]))

    start = project.get("start_date", "N/A") or "N/A"
    end = project.get("end_date", "N/A") or "N/A"
    days = project.get("days", "N/A") or "N/A"
    notes = project.get("notes", "") or ""

    meta_data = [
        ["Start Date", str(start), "End Date", str(end)],
        ["Days", str(days), "Status", project.get("status", "N/A")],
    ]
    if notes:
        meta_data.append(["Notes", notes, "", ""])

    meta_table = Table(meta_data, colWidths=[1.2 * inch, 2.5 * inch, 1.2 * inch, 2.5 * inch])
    meta_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("TEXTCOLOR", (0, 0), (-1, -1), DARK_TEXT),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BACKGROUND", (0, 0), (-1, -1), LIGHT_GRAY),
        ("BOX", (0, 0), (-1, -1), 0.5, TABLE_BORDER),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, TABLE_BORDER),
        ("SPAN", (1, -1), (3, -1)) if notes else ("SPAN", (0, 0), (0, 0)),
    ]))
    elements.append(meta_table)
    return elements


def _build_labor_table(labor_entries, styles, include_financials=True):
    """Build personnel table."""
    elements = []
    elements.append(Spacer(1, 8))
    elements.append(Paragraph("Personnel", styles["SectionHeader"]))

    if not labor_entries:
        elements.append(Paragraph("No personnel assigned.", styles["BodyText2"]))
        return elements

    if include_financials:
        headers = ["Role", "Person", "Hours", "Cost Rate", "Bid Rate", "Cost", "Charge"]
    else:
        headers = ["Role", "Person", "Hours"]
    data = [headers]

    total_hours = 0
    total_cost = 0
    total_charge = 0

    for entry in labor_entries:
        hours = entry.get("hours", 0)
        emp_rate = entry.get("employee_rate", 0)
        bid_rate = entry.get("bid_rate", 0)
        cost = emp_rate * hours
        charge = bid_rate * hours
        total_hours += hours
        total_cost += cost
        total_charge += charge

        if include_financials:
            data.append([
                entry.get("job_title", entry.get("role", "")),
                entry.get("person_name", "") or "",
                f"{hours:.1f}",
                _fmt(emp_rate),
                _fmt(bid_rate),
                _fmt(cost),
                _fmt(charge),
            ])
        else:
            data.append([
                entry.get("job_title", entry.get("role", "")),
                entry.get("person_name", "") or "",
                f"{hours:.1f}",
            ])

    # Totals row
    if include_financials:
        data.append(["TOTAL", "", f"{total_hours:.1f}", "", "", _fmt(total_cost), _fmt(total_charge)])
        col_widths = [1.8 * inch, 1.0 * inch, 0.6 * inch, 0.85 * inch, 0.85 * inch, 0.95 * inch, 0.95 * inch]
    else:
        data.append(["TOTAL", "", f"{total_hours:.1f}"])
        col_widths = [3.0 * inch, 2.5 * inch, 1.5 * inch]
    table = Table(data, colWidths=col_widths)

    style_cmds = [
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BACKGROUND", (0, 0), (-1, 0), TABLE_HEADER_BG),
        ("TEXTCOLOR", (0, 0), (-1, 0), TABLE_HEADER_TEXT),
        ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOX", (0, 0), (-1, -1), 0.5, TABLE_BORDER),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, TABLE_BORDER),
        # Totals row
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("BACKGROUND", (0, -1), (-1, -1), LIGHT_GRAY),
        ("LINEABOVE", (0, -1), (-1, -1), 1, PRIMARY),
    ]

    # Alternating row colors
    for i in range(1, len(data) - 1):
        if i % 2 == 0:
            style_cmds.append(("BACKGROUND", (0, i), (-1, i), TABLE_ALT_ROW))

    table.setStyle(TableStyle(style_cmds))
    elements.append(table)
    return elements


def _build_imagery_table(imagery_orders, styles, include_financials=True):
    """Build imagery orders table."""
    elements = []
    elements.append(Spacer(1, 8))
    elements.append(Paragraph("Imagery Orders", styles["SectionHeader"]))

    if not imagery_orders:
        elements.append(Paragraph("No imagery orders.", styles["BodyText2"]))
        return elements

    if include_financials:
        headers = ["Provider", "Product", "Date", "Status", "AOI", "Cost", "Charge"]
    else:
        headers = ["Provider", "Product", "Date", "Status", "AOI"]
    data = [headers]

    total_cost = 0
    total_charge = 0

    for order in imagery_orders:
        cost = order.get("cost", 0)
        charge = order.get("charge", 0)
        total_cost += cost
        total_charge += charge

        row = [
            order.get("provider", ""),
            order.get("product", "")[:30],
            order.get("order_date", "") or "",
            order.get("order_status", "Requested"),
            order.get("aoi", "") or "",
        ]
        if include_financials:
            row.extend([_fmt(cost), _fmt(charge)])
        data.append(row)

    if include_financials:
        data.append(["TOTAL", "", "", "", "", _fmt(total_cost), _fmt(total_charge)])
        col_widths = [1.1 * inch, 1.8 * inch, 0.8 * inch, 0.7 * inch, 0.8 * inch, 0.85 * inch, 0.85 * inch]
    else:
        col_widths = [1.4 * inch, 2.5 * inch, 1.0 * inch, 0.9 * inch, 1.2 * inch]
    table = Table(data, colWidths=col_widths)

    style_cmds = [
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BACKGROUND", (0, 0), (-1, 0), TABLE_HEADER_BG),
        ("TEXTCOLOR", (0, 0), (-1, 0), TABLE_HEADER_TEXT),
        ("ALIGN", (-2, 0), (-1, -1), "RIGHT"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOX", (0, 0), (-1, -1), 0.5, TABLE_BORDER),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, TABLE_BORDER),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("BACKGROUND", (0, -1), (-1, -1), LIGHT_GRAY),
        ("LINEABOVE", (0, -1), (-1, -1), 1, PRIMARY),
    ]

    for i in range(1, len(data) - 1):
        if i % 2 == 0:
            style_cmds.append(("BACKGROUND", (0, i), (-1, i), TABLE_ALT_ROW))

    table.setStyle(TableStyle(style_cmds))
    elements.append(table)
    return elements


def _build_financial_summary(labor_entries, imagery_orders, styles):
    """Build financial summary box."""
    elements = []
    elements.append(Spacer(1, 8))
    elements.append(Paragraph("Financial Summary", styles["SectionHeader"]))

    labor_cost = sum(e.get("employee_rate", 0) * e.get("hours", 0) for e in labor_entries)
    labor_charge = sum(e.get("bid_rate", 0) * e.get("hours", 0) for e in labor_entries)
    img_cost = sum(o.get("cost", 0) for o in imagery_orders)
    img_charge = sum(o.get("charge", 0) for o in imagery_orders)
    grand_cost = labor_cost + img_cost
    grand_charge = labor_charge + img_charge
    profit = grand_charge - grand_cost
    margin = (profit / grand_charge * 100) if grand_charge > 0 else 0

    data = [
        ["", "Cost", "Charge", "Profit"],
        ["Labor", _fmt(labor_cost), _fmt(labor_charge), _fmt(labor_charge - labor_cost)],
        ["Imagery", _fmt(img_cost), _fmt(img_charge), _fmt(img_charge - img_cost)],
        ["Grand Total", _fmt(grand_cost), _fmt(grand_charge), _fmt(profit)],
        ["Margin", "", "", f"{margin:.1f}%"],
    ]

    col_widths = [1.5 * inch, 1.8 * inch, 1.8 * inch, 1.8 * inch]
    table = Table(data, colWidths=col_widths)
    table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("BACKGROUND", (0, 0), (-1, 0), PRIMARY),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOX", (0, 0), (-1, -1), 0.5, TABLE_BORDER),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, TABLE_BORDER),
        ("FONTNAME", (0, -2), (-1, -2), "Helvetica-Bold"),
        ("BACKGROUND", (0, -2), (-1, -2), LIGHT_GRAY),
        ("LINEABOVE", (0, -2), (-1, -2), 1, PRIMARY),
        ("BACKGROUND", (0, -1), (-1, -1), LIGHT_GRAY),
    ]))
    elements.append(table)
    return elements


def _footer(canvas, doc):
    """Add footer with page number and generation date."""
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(DARK_TEXT)
    canvas.drawString(
        inch, 0.4 * inch,
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
    )
    canvas.drawRightString(
        letter[0] - inch, 0.4 * inch,
        f"Page {doc.page}",
    )
    canvas.restoreState()


def generate_report(project, labor_entries, imagery_orders,
                    include_summary=True, include_imagery=True, include_financials=True):
    """Generate a PDF report and return it as a BytesIO buffer."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        topMargin=0.5 * inch,
        bottomMargin=0.6 * inch,
        leftMargin=0.5 * inch,
        rightMargin=0.5 * inch,
    )

    styles = _get_styles()
    elements = []

    # Header
    elements.append(_build_header_table(project, styles))

    # Metadata
    if include_summary:
        elements.extend(_build_metadata(project, styles))

    # Personnel
    elements.extend(_build_labor_table(labor_entries, styles, include_financials=include_financials))

    # Imagery
    if include_imagery:
        elements.extend(_build_imagery_table(imagery_orders, styles, include_financials=include_financials))

    # Financial Summary
    if include_financials:
        elements.extend(_build_financial_summary(labor_entries, imagery_orders, styles))

    doc.build(elements, onFirstPage=_footer, onLaterPages=_footer)
    buffer.seek(0)
    return buffer


def generate_pws_report(pws_number, projects_data, include_summary=True,
                        include_imagery=True, include_financials=True):
    """Generate a consolidated PDF report for all projects under a PWS."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        topMargin=0.5 * inch,
        bottomMargin=0.6 * inch,
        leftMargin=0.5 * inch,
        rightMargin=0.5 * inch,
    )

    styles = _get_styles()
    elements = []

    # PWS-level header
    pws_header = {
        "report_title": f"PWS Consolidated Report",
        "pws_number": pws_number,
        "status": f"{len(projects_data)} project(s)",
    }
    elements.append(_build_header_table(pws_header, styles))

    # PWS summary table
    elements.append(Spacer(1, 12))
    elements.append(Paragraph("PWS Summary", styles["SectionHeader"]))

    all_labor = []
    all_imagery = []
    if include_financials:
        summary_rows = [["Project", "Labor Cost", "Labor Charge", "Img Cost", "Img Charge", "Profit"]]
    else:
        summary_rows = [["Project", "Status", "Days"]]

    for proj_info in projects_data:
        project = proj_info["project"]
        labor = proj_info["labor"]
        imagery = proj_info["imagery"]
        all_labor.extend(labor)
        all_imagery.extend(imagery)

        if include_financials:
            l_cost = sum(e.get("employee_rate", 0) * e.get("hours", 0) for e in labor)
            l_charge = sum(e.get("bid_rate", 0) * e.get("hours", 0) for e in labor)
            i_cost = sum(o.get("cost", 0) for o in imagery)
            i_charge = sum(o.get("charge", 0) for o in imagery)
            profit = (l_charge - l_cost) + (i_charge - i_cost)
            summary_rows.append([
                project.get("report_title", "")[:35],
                _fmt(l_cost), _fmt(l_charge), _fmt(i_cost), _fmt(i_charge), _fmt(profit),
            ])
        else:
            summary_rows.append([
                project.get("report_title", "")[:35],
                project.get("status", ""),
                str(project.get("days", "") or ""),
            ])

    if include_financials:
        col_widths = [2.0 * inch, 1.1 * inch, 1.1 * inch, 1.0 * inch, 1.0 * inch, 1.0 * inch]
    else:
        col_widths = [3.5 * inch, 2.0 * inch, 1.5 * inch]
    summary_table = Table(summary_rows, colWidths=col_widths)
    summary_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BACKGROUND", (0, 0), (-1, 0), TABLE_HEADER_BG),
        ("TEXTCOLOR", (0, 0), (-1, 0), TABLE_HEADER_TEXT),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOX", (0, 0), (-1, -1), 0.5, TABLE_BORDER),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, TABLE_BORDER),
    ]))
    for i in range(1, len(summary_rows)):
        if i % 2 == 0:
            summary_table.setStyle(TableStyle([("BACKGROUND", (0, i), (-1, i), TABLE_ALT_ROW)]))
    elements.append(summary_table)

    # Per-project sections
    for proj_info in projects_data:
        project = proj_info["project"]
        labor = proj_info["labor"]
        imagery = proj_info["imagery"]

        elements.append(Spacer(1, 16))
        elements.append(HRFlowable(width="100%", thickness=1, color=PRIMARY, spaceAfter=8))
        elements.append(Paragraph(f"Project: {project.get('report_title', '')}", styles["SectionHeader"]))

        if include_summary:
            elements.extend(_build_metadata(project, styles))

        elements.extend(_build_labor_table(labor, styles, include_financials=include_financials))

        if include_imagery:
            elements.extend(_build_imagery_table(imagery, styles, include_financials=include_financials))

    # Grand total financial summary across all projects
    if include_financials:
        elements.append(Spacer(1, 16))
        elements.append(HRFlowable(width="100%", thickness=2, color=PRIMARY, spaceAfter=8))
        elements.append(Paragraph("PWS Grand Total", styles["SectionHeader"]))
        elements.extend(_build_financial_summary(all_labor, all_imagery, styles))

    doc.build(elements, onFirstPage=_footer, onLaterPages=_footer)
    buffer.seek(0)
    return buffer
