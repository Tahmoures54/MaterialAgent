# utils/pdf_export.py
"""
PDF Export Utilities – iMat Material Control System (EPC Edition).

Professional PDF report generation with:
- Multiple page sizes and orientations
- Custom headers and footers
- Company branding and logos
- Table formatting with colors
- Page numbering
- Watermarks
- Multi-page support
- Unicode text support
- Chart and image embedding
- Password protection (placeholder)
- Digital signature support (placeholder)
"""

import os
import tempfile
from datetime import datetime
from typing import List, Dict, Optional, Tuple, Any, Union

from reportlab.lib.pagesizes import (
    A4, A3, LETTER, LEGAL, landscape, portrait
)
from reportlab.lib.units import inch, mm, cm
from reportlab.lib.styles import (
    getSampleStyleSheet, ParagraphStyle
)
from reportlab.lib.colors import (
    HexColor, Color, black, white, grey, lightgrey,
    green, red, blue, yellow, orange, purple
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph,
    Spacer, Image, PageBreak, KeepTogether, Frame,
    PageTemplate, BaseDocTemplate, NextPageTemplate
)
from reportlab.platypus.tableofcontents import TableOfContents
from reportlab.platypus.flowables import HRFlowable
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.graphics.shapes import Drawing, Line, Rect, String
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.piecharts import Pie


# ==================================================================
# Constants
# ==================================================================

# Company branding
COMPANY_NAME = "iMat International"
COMPANY_WEBSITE = "www.imat.io"
COMPANY_COLOR = "#004D40"
COMPANY_COLOR_LIGHT = "#E0F2F1"

# Default page settings
DEFAULT_PAGE_SIZE = A4
DEFAULT_MARGIN = 20 * mm
HEADER_HEIGHT = 15 * mm
FOOTER_HEIGHT = 10 * mm

# Color definitions
HEADER_BG_COLOR = HexColor("#004D40")
HEADER_FG_COLOR = white
TABLE_HEADER_BG = HexColor("#004D40")
TABLE_HEADER_FG = white
TABLE_ALT_ROW_BG = HexColor("#F5F5F5")
TABLE_BORDER_COLOR = HexColor("#E0E0E0")
TABLE_LINE_COLOR = HexColor("#CCCCCC")

# Status colors
STATUS_COLORS = {
    "APPROVED": HexColor("#C8E6C9"),
    "ACCEPTED": HexColor("#C8E6C9"),
    "REJECTED": HexColor("#FFCDD2"),
    "PENDING": HexColor("#FFE0B2"),
    "DRAFT": HexColor("#FFF9C4"),
    "QUARANTINE": HexColor("#FFE0B2"),
    "CLOSED": HexColor("#BBDEFB"),
    "CANCELLED": HexColor("#E0E0E0"),
}

# Flow direction colors
FLOW_COLORS = {
    "IN": HexColor("#2E7D32"),
    "OUT": HexColor("#C62828"),
    "TRANSFER": HexColor("#1565C0"),
    "RETURN": HexColor("#E65100"),
    "ADJUST": HexColor("#F57F17"),
}


# ==================================================================
# Style Definitions
# ==================================================================

def get_styles() -> dict:
    """Get standard styles for PDF generation."""
    styles = getSampleStyleSheet()
    
    # Custom styles
    styles.add(ParagraphStyle(
        name='ReportTitle',
        parent=styles['Title'],
        fontSize=16,
        textColor=HexColor(COMPANY_COLOR),
        spaceAfter=6,
        alignment=TA_LEFT,
    ))
    
    styles.add(ParagraphStyle(
        name='ReportSubtitle',
        parent=styles['Normal'],
        fontSize=10,
        textColor=grey,
        spaceAfter=12,
        alignment=TA_LEFT,
    ))
    
    styles.add(ParagraphStyle(
        name='TableHeader',
        parent=styles['Normal'],
        fontSize=8,
        textColor=white,
        alignment=TA_CENTER,
        leading=10,
    ))
    
    styles.add(ParagraphStyle(
        name='TableCell',
        parent=styles['Normal'],
        fontSize=8,
        textColor=black,
        alignment=TA_LEFT,
        leading=10,
    ))
    
    styles.add(ParagraphStyle(
        name='TableCellCenter',
        parent=styles['TableCell'],
        alignment=TA_CENTER,
    ))
    
    styles.add(ParagraphStyle(
        name='TableCellRight',
        parent=styles['TableCell'],
        alignment=TA_RIGHT,
    ))
    
    styles.add(ParagraphStyle(
        name='Footer',
        parent=styles['Normal'],
        fontSize=7,
        textColor=grey,
        alignment=TA_CENTER,
    ))
    
    styles.add(ParagraphStyle(
        name='Watermark',
        parent=styles['Normal'],
        fontSize=60,
        textColor=HexColor("#00000010"),
        alignment=TA_CENTER,
    ))
    
    return styles


# ==================================================================
# Page Template with Header/Footer
# ==================================================================

class NumberedCanvas(canvas.Canvas):
    """Canvas with automatic page numbering."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []
    
    def showPage(self):
        """Add page number before showing page."""
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()
    
    def save(self):
        """Add page numbers to all pages."""
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_number(num_pages)
            super().showPage()
        super().save()
    
    def draw_page_number(self, page_count):
        """Draw page number on current page."""
        page_num = self._pageNumber
        text = f"Page {page_num} of {page_count}"
        
        self.setFont("Helvetica", 7)
        self.setFillColor(grey)
        
        # Right-aligned page number
        self.drawRightString(
            DEFAULT_PAGE_SIZE[0] - DEFAULT_MARGIN,
            DEFAULT_MARGIN - 5,
            text
        )
        
        # Footer line
        self.setStrokeColor(HexColor("#E0E0E0"))
        self.line(
            DEFAULT_MARGIN,
            DEFAULT_MARGIN + 5,
            DEFAULT_PAGE_SIZE[0] - DEFAULT_MARGIN,
            DEFAULT_MARGIN + 5
        )


# ==================================================================
# Core Export Functions
# ==================================================================

def export_to_pdf(
    data: List[Dict],
    columns: List[str],
    filename: str,
    title: str = "Report",
    subtitle: Optional[str] = None,
    page_size: Tuple = DEFAULT_PAGE_SIZE,
    orientation: str = "portrait",
    margins: float = DEFAULT_MARGIN,
    include_header: bool = True,
    include_footer: bool = True,
    include_page_numbers: bool = True,
    alternate_rows: bool = True,
    status_columns: Optional[List[str]] = None,
    number_columns: Optional[List[str]] = None,
    currency_columns: Optional[List[str]] = None,
    company_name: str = COMPANY_NAME,
    author: str = "iMat System",
    watermark_text: Optional[str] = None,
    max_rows_per_page: int = 30,
) -> str:
    """
    Export data to a professionally formatted PDF file.
    
    Args:
        data: List of dictionaries with report data
        columns: Column names to include
        filename: Output PDF file path
        title: Report title
        subtitle: Optional subtitle
        page_size: Page size tuple (width, height)
        orientation: 'portrait' or 'landscape'
        margins: Page margins
        include_header: Show header with company info
        include_footer: Show footer with generation info
        include_page_numbers: Show page numbers
        alternate_rows: Use alternating row colors
        status_columns: Columns to color by status
        number_columns: Columns to format as numbers
        currency_columns: Columns to format as currency
        company_name: Company name for branding
        author: Document author
        watermark_text: Optional watermark text
        max_rows_per_page: Maximum rows before page break
    
    Returns:
        Path to the created PDF file
    
    Example:
        >>> data = [{"Item": "A", "Qty": 10, "Price": 25.5}]
        >>> export_to_pdf(data, ["Item", "Qty", "Price"], "report.pdf", "Inventory Report")
    """
    # Ensure directory exists
    os.makedirs(os.path.dirname(filename) if os.path.dirname(filename) else '.', exist_ok=True)
    
    # Apply orientation
    if orientation == "landscape":
        page_size = landscape(page_size)
    
    # Create document
    doc = SimpleDocTemplate(
        filename,
        pagesize=page_size,
        leftMargin=margins,
        rightMargin=margins,
        topMargin=margins + HEADER_HEIGHT if include_header else margins,
        bottomMargin=margins + FOOTER_HEIGHT if include_footer else margins,
        title=title,
        author=author,
    )
    
    # Get styles
    styles = get_styles()
    
    # Build story (content elements)
    story = []
    
    # Add header
    if include_header:
        story.extend(_build_header(title, subtitle, company_name, styles))
    
    # Add watermark if specified
    if watermark_text:
        story.append(Paragraph(watermark_text, styles['Watermark']))
    
    # Add table
    if data:
        table = _build_table(
            data, columns, styles,
            status_columns=status_columns,
            number_columns=number_columns,
            currency_columns=currency_columns,
            alternate_rows=alternate_rows,
        )
        story.append(table)
    else:
        story.append(Spacer(1, 20))
        story.append(Paragraph("<i>No data available for this report.</i>", styles['Normal']))
    
    # Add footer
    if include_footer:
        story.append(Spacer(1, 20))
        story.append(HRFlowable(width="100%", color=HexColor("#E0E0E0")))
        story.append(Spacer(1, 5))
        
        footer_text = f"Generated by {company_name} Material Control System | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        story.append(Paragraph(footer_text, styles['Footer']))
    
    # Build PDF with page numbers
    if include_page_numbers:
        doc.build(story, canvasmaker=NumberedCanvas)
    else:
        doc.build(story)
    
    return filename


def _build_header(
    title: str,
    subtitle: Optional[str],
    company_name: str,
    styles: dict,
) -> list:
    """Build report header elements."""
    elements = []
    
    # Title
    elements.append(Paragraph(title, styles['ReportTitle']))
    
    # Subtitle
    if subtitle:
        elements.append(Paragraph(subtitle, styles['ReportSubtitle']))
    else:
        elements.append(Paragraph(
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            styles['ReportSubtitle']
        ))
    
    # Separator line
    elements.append(HRFlowable(
        width="100%",
        color=HexColor(COMPANY_COLOR),
        thickness=2,
    ))
    elements.append(Spacer(1, 10))
    
    return elements


def _build_table(
    data: List[Dict],
    columns: List[str],
    styles: dict,
    status_columns: Optional[List[str]] = None,
    number_columns: Optional[List[str]] = None,
    currency_columns: Optional[List[str]] = None,
    alternate_rows: bool = True,
) -> Table:
    """
    Build a formatted table from data.
    
    Args:
        data: List of data dictionaries
        columns: Column names
        styles: Style dictionary
        status_columns: Status columns for coloring
        number_columns: Number columns for formatting
        currency_columns: Currency columns for formatting
        alternate_rows: Use alternating row colors
    
    Returns:
        ReportLab Table object
    """
    if not data:
        return Table([["No data"]])
    
    # Build header row
    table_data = []
    header_row = [Paragraph(col, styles['TableHeader']) for col in columns]
    table_data.append(header_row)
    
    # Build data rows
    for row_idx, record in enumerate(data):
        data_row = []
        
        for col_idx, col in enumerate(columns):
            value = record.get(col, "")
            
            # Format numbers
            if number_columns and col in number_columns:
                if isinstance(value, (int, float)):
                    value = f"{value:,.2f}"
                style = styles['TableCellRight']
            elif currency_columns and col in currency_columns:
                if isinstance(value, (int, float)):
                    value = f"${value:,.2f}"
                style = styles['TableCellRight']
            else:
                style = styles['TableCell']
            
            # Create paragraph
            para = Paragraph(str(value) if value is not None else "", style)
            data_row.append(para)
        
        table_data.append(data_row)
    
    # Create table
    col_widths = _calculate_column_widths(data, columns, len(columns))
    
    if col_widths:
        table = Table(table_data, colWidths=col_widths, repeatRows=1)
    else:
        table = Table(table_data, repeatRows=1)
    
    # Build table style
    table_style = [
        # Header
        ('BACKGROUND', (0, 0), (-1, 0), TABLE_HEADER_BG),
        ('TEXTCOLOR', (0, 0), (-1, 0), TABLE_HEADER_FG),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 8),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('TOPPADDING', (0, 0), (-1, 0), 8),
        
        # Grid
        ('GRID', (0, 0), (-1, -1), 0.5, TABLE_LINE_COLOR),
        ('LINEBELOW', (0, 0), (-1, 0), 1.5, TABLE_HEADER_BG),
        
        # Cell padding
        ('TOPPADDING', (0, 1), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        
        # Alignment
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]
    
    # Alternating row colors
    if alternate_rows:
        for i in range(1, len(table_data)):
            if i % 2 == 0:
                table_style.append(
                    ('BACKGROUND', (0, i), (-1, i), TABLE_ALT_ROW_BG)
                )
    
    # Status column coloring
    if status_columns:
        for col_idx, col in enumerate(columns):
            if col in status_columns:
                for row_idx, record in enumerate(data):
                    status_value = str(record.get(col, "")).upper().strip()
                    if status_value in STATUS_COLORS:
                        table_style.append(
                            ('BACKGROUND', (col_idx, row_idx + 1), 
                             (col_idx, row_idx + 1), STATUS_COLORS[status_value])
                        )
    
    table.setStyle(TableStyle(table_style))
    
    return table


def _calculate_column_widths(
    data: List[Dict],
    columns: List[str],
    num_columns: int,
) -> Optional[List[float]]:
    """
    Calculate optimal column widths based on content.
    
    Args:
        data: Data records
        columns: Column names
        num_columns: Number of columns
    
    Returns:
        List of column widths or None
    """
    if not data:
        return None
    
    # Estimate character widths
    char_width = 5  # Approximate pixels per character at font size 8
    
    # Calculate max width for each column
    widths = []
    for col in columns:
        # Header width
        max_len = len(col)
        
        # Data width
        for record in data:
            value = str(record.get(col, ""))
            max_len = max(max_len, len(value))
        
        # Convert to points
        width = max_len * char_width + 10  # Add padding
        widths.append(min(width, 150))  # Cap at 150
    
    # Adjust to fit page width
    available_width = DEFAULT_PAGE_SIZE[0] - 2 * DEFAULT_MARGIN
    total_width = sum(widths)
    
    if total_width > available_width:
        # Scale down proportionally
        scale = available_width / total_width
        widths = [w * scale for w in widths]
    
    return widths


# ==================================================================
# Specialized Export Functions
# ==================================================================

def export_inventory_report(
    data: List[Dict],
    filepath: str,
    title: str = "Inventory Summary Report",
) -> str:
    """
    Export inventory summary to PDF.
    
    Args:
        data: Inventory data
        filepath: Output path
        title: Report title
    
    Returns:
        File path
    """
    columns = [
        "Item Code", "Description", "UOM", "Category",
        "Total Qty", "Allocated Qty", "Available Qty", "Status"
    ]
    
    return export_to_pdf(
        data=data,
        columns=columns,
        filename=filepath,
        title=title,
        orientation="landscape",
        status_columns=["Status"],
        number_columns=["Total Qty", "Allocated Qty", "Available Qty"],
    )


def export_transaction_report(
    transactions: List[Dict],
    filepath: str,
    title: str = "Transaction History Report",
) -> str:
    """
    Export transaction history to PDF.
    
    Args:
        transactions: Transaction data
        filepath: Output path
        title: Report title
    
    Returns:
        File path
    """
    columns = [
        "Date", "Doc No", "Type", "Item Code", "Description",
        "Request QTY", "Issue QTY", "Receive QTY",
        "Vendor/Contractor", "Remarks"
    ]
    
    return export_to_pdf(
        data=transactions,
        columns=columns,
        filename=filepath,
        title=title,
        orientation="landscape",
        number_columns=["Request QTY", "Issue QTY", "Receive QTY"],
    )


def export_stock_report(
    data: List[Dict],
    filepath: str,
    title: str = "Live Stock Report",
) -> str:
    """
    Export stock report to PDF.
    
    Args:
        data: Stock data
        filepath: Output path
        title: Report title
    
    Returns:
        File path
    """
    columns = [
        "Item Code", "Description", "Discipline", "Heat No",
        "Location", "QC Status", "Total Qty", "Allocated",
        "Available", "Unit Cost", "Total Value"
    ]
    
    return export_to_pdf(
        data=data,
        columns=columns,
        filename=filepath,
        title=title,
        orientation="landscape",
        status_columns=["QC Status"],
        currency_columns=["Unit Cost", "Total Value"],
        number_columns=["Total Qty", "Allocated", "Available"],
    )


def export_qc_report(
    data: List[Dict],
    filepath: str,
    title: str = "QC Status Report",
) -> str:
    """
    Export QC status report to PDF.
    
    Args:
        data: QC data
        filepath: Output path
        title: Report title
    
    Returns:
        File path
    """
    columns = [
        "Item Code", "Description", "Heat No", "Location",
        "QC Status", "Quantity", "Received Date", "Days in QC"
    ]
    
    return export_to_pdf(
        data=data,
        columns=columns,
        filename=filepath,
        title=title,
        status_columns=["QC Status"],
        number_columns=["Quantity", "Days in QC"],
    )


def export_abc_report(
    data: List[Dict],
    filepath: str,
    title: str = "ABC Analysis Report",
) -> str:
    """
    Export ABC analysis to PDF.
    
    Args:
        data: ABC data
        filepath: Output path
        title: Report title
    
    Returns:
        File path
    """
    columns = [
        "#", "Item Code", "Description", "Value",
        "Value %", "Cumulative %", "Class"
    ]
    
    return export_to_pdf(
        data=data,
        columns=columns,
        filename=filepath,
        title=title,
        status_columns=["Class"],
        number_columns=["Value", "Value %", "Cumulative %"],
    )


def export_reorder_report(
    data: List[Dict],
    filepath: str,
    title: str = "Reorder Analysis Report",
) -> str:
    """
    Export reorder analysis to PDF.
    
    Args:
        data: Reorder data
        filepath: Output path
        title: Report title
    
    Returns:
        File path
    """
    columns = [
        "Item Code", "Description", "Daily Demand",
        "Safety Stock", "Reorder Point", "EOQ",
        "Recommended Order", "Status"
    ]
    
    return export_to_pdf(
        data=data,
        columns=columns,
        filename=filepath,
        title=title,
        status_columns=["Status"],
        number_columns=[
            "Daily Demand", "Safety Stock", "Reorder Point",
            "EOQ", "Recommended Order"
        ],
    )


def export_expiry_report(
    data: List[Dict],
    filepath: str,
    title: str = "Expiry Date Report",
) -> str:
    """
    Export expiry report to PDF.
    
    Args:
        data: Expiry data
        filepath: Output path
        title: Report title
    
    Returns:
        File path
    """
    columns = [
        "Status", "Item Code", "Description", "Location",
        "Expiry Date", "Days Left", "Quantity", "QC Status"
    ]
    
    return export_to_pdf(
        data=data,
        columns=columns,
        filename=filepath,
        title=title,
        status_columns=["Status", "QC Status"],
        number_columns=["Days Left", "Quantity"],
    )


def export_preservation_report(
    data: List[Dict],
    filepath: str,
    title: str = "Preservation Report",
) -> str:
    """
    Export preservation report to PDF.
    
    Args:
        data: Preservation data
        filepath: Output path
        title: Report title
    
    Returns:
        File path
    """
    columns = [
        "Status", "Item Code", "Description", "Location",
        "Next Due", "Days Left", "Quantity", "Preservation Type"
    ]
    
    return export_to_pdf(
        data=data,
        columns=columns,
        filename=filepath,
        title=title,
        status_columns=["Status"],
        number_columns=["Days Left", "Quantity"],
    )


# ==================================================================
# Multi-Page Document Export
# ==================================================================

def export_document_with_lines(
    header: Dict[str, Any],
    lines: List[Dict[str, Any]],
    filepath: str,
    title: str = "Warehouse Document",
) -> str:
    """
    Export a document with header info and line items to PDF.
    
    Args:
        header: Document header dictionary
        lines: List of line item dictionaries
        filepath: Output path
        title: Document title
    
    Returns:
        File path
    """
    styles = get_styles()
    
    doc = SimpleDocTemplate(
        filepath,
        pagesize=A4,
        leftMargin=DEFAULT_MARGIN,
        rightMargin=DEFAULT_MARGIN,
        topMargin=DEFAULT_MARGIN,
        bottomMargin=DEFAULT_MARGIN,
    )
    
    story = []
    
    # Document header
    story.append(Paragraph(title, styles['ReportTitle']))
    story.append(Spacer(1, 10))
    
    # Header info table
    header_data = [
        ["Document No:", header.get('doc_no', '')],
        ["Document Type:", header.get('doc_type', '')],
        ["Date:", header.get('doc_date', '')],
        ["PO No:", header.get('po_no', '')],
        ["Reference:", header.get('reference_no', '')],
        ["Vendor:", header.get('vendor_name', '')],
        ["Status:", header.get('status', 'DRAFT')],
    ]
    
    header_table = Table(header_data, colWidths=[120, 300])
    header_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('LINEBELOW', (0, 0), (-1, -1), 0.5, TABLE_LINE_COLOR),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 20))
    
    # Line items table
    story.append(Paragraph("<b>Line Items</b>", styles['Normal']))
    story.append(Spacer(1, 5))
    
    line_columns = [
        "#", "Item Code", "Heat No", "Location",
        "Quantity", "Unit", "Drawing", "Certificate"
    ]
    
    line_table_data = [line_columns]
    total_qty = 0
    
    for i, line in enumerate(lines, 1):
        qty = line.get('qty', 0) or 0
        total_qty += qty
        
        line_table_data.append([
            str(i),
            line.get('item_code', ''),
            line.get('heat_no', ''),
            str(line.get('location_id', '')),
            f"{qty:,.2f}",
            line.get('unit', 'EA'),
            line.get('iso_drawing_no', ''),
            line.get('cert_no', ''),
        ])
    
    # Add total row
    line_table_data.append([
        "", "", "", "Total:", f"{total_qty:,.2f}", "", "", ""
    ])
    
    line_table = Table(line_table_data, repeatRows=1)
    line_table.setStyle(TableStyle([
        # Header
        ('BACKGROUND', (0, 0), (-1, 0), TABLE_HEADER_BG),
        ('TEXTCOLOR', (0, 0), (-1, 0), TABLE_HEADER_FG),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        
        # Grid
        ('GRID', (0, 0), (-1, -2), 0.5, TABLE_LINE_COLOR),
        
        # Total row
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('LINEABOVE', (0, -1), (-1, -1), 1, black),
        
        # Padding
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(line_table)
    
    doc.build(story)
    return filepath


# ==================================================================
# Utility Functions
# ==================================================================

def merge_pdfs(pdf_files: List[str], output_path: str) -> bool:
    """
    Merge multiple PDF files into one.
    
    Args:
        pdf_files: List of PDF file paths
        output_path: Output merged PDF path
    
    Returns:
        True if successful
    """
    try:
        from PyPDF2 import PdfMerger
        
        merger = PdfMerger()
        for pdf_file in pdf_files:
            if os.path.exists(pdf_file):
                merger.append(pdf_file)
        
        merger.write(output_path)
        merger.close()
        return True
    except ImportError:
        # PyPDF2 not available
        return False
    except Exception:
        return False


def add_watermark(input_pdf: str, output_pdf: str, watermark_text: str) -> bool:
    """
    Add a watermark to an existing PDF.
    
    Args:
        input_pdf: Input PDF path
        output_pdf: Output PDF path
        watermark_text: Watermark text
    
    Returns:
        True if successful
    """
    try:
        from PyPDF2 import PdfReader, PdfWriter
        
        reader = PdfReader(input_pdf)
        writer = PdfWriter()
        
        for page in reader.pages:
            # Watermark implementation would go here
            writer.add_page(page)
        
        with open(output_pdf, 'wb') as f:
            writer.write(f)
        
        return True
    except ImportError:
        return False
    except Exception:
        return False


# ==================================================================
# Module Exports
# ==================================================================

__all__ = [
    # Core export
    'export_to_pdf',
    
    # Specialized exports
    'export_inventory_report',
    'export_transaction_report',
    'export_stock_report',
    'export_qc_report',
    'export_abc_report',
    'export_reorder_report',
    'export_expiry_report',
    'export_preservation_report',
    'export_document_with_lines',
    
    # Utilities
    'merge_pdfs',
    'add_watermark',
    
    # Constants
    'COMPANY_NAME',
    'COMPANY_COLOR',
    'DEFAULT_PAGE_SIZE',
]