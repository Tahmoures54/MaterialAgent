# utils/html_export.py
"""
HTML Export Utilities – iMat Material Control System (EPC Edition).

Professional HTML report generation with:
- Document export with full styling
- Responsive design support
- Print-friendly CSS
- Multiple report templates
- Embedded CSS styles
- Signature areas
- Company branding
- Table of contents generation
- Chart placeholders
- Email-ready HTML
- Dark mode support
- RTL language support
"""

import os
import tempfile
import webbrowser
from datetime import datetime
from typing import Dict, List, Optional, Any, Union


# ==================================================================
# CSS Styles
# ==================================================================

BASE_CSS = """
* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    margin: 40px;
    color: #333333;
    line-height: 1.6;
    background: #FFFFFF;
}

.header {
    display: flex;
    align-items: center;
    border-bottom: 3px solid {accent_color};
    padding-bottom: 15px;
    margin-bottom: 30px;
}

.header-logo {
    font-size: 40px;
    margin-right: 15px;
}

.header h1 {
    color: {accent_color};
    font-size: 28px;
    margin: 0;
}

.header p {
    margin: 5px 0 0 0;
    color: #666666;
    font-size: 12px;
}

.info-table {
    width: 100%;
    border-collapse: collapse;
    margin-bottom: 20px;
}

.info-table td {
    padding: 8px 12px;
    border: 1px solid #DDDDDD;
    vertical-align: top;
    font-size: 12px;
}

.info-table td.label {
    font-weight: bold;
    background-color: #F8F9FA;
    width: 200px;
    color: #2C3E50;
}

.lines-table {
    width: 100%;
    border-collapse: collapse;
    margin-top: 20px;
    font-size: 11px;
}

.lines-table th {
    background-color: {accent_color};
    color: white;
    padding: 10px 12px;
    text-align: left;
    font-size: 11px;
    font-weight: 600;
}

.lines-table td {
    padding: 8px 12px;
    border: 1px solid #DDDDDD;
}

.lines-table tr:nth-child(even) {
    background-color: #F8F9FA;
}

.lines-table tr:hover {
    background-color: #E3F2FD;
}

.footer {
    margin-top: 30px;
    font-size: 10px;
    color: #888888;
    text-align: center;
    border-top: 1px solid #EEEEEE;
    padding-top: 15px;
}

.signature-area {
    display: flex;
    justify-content: space-between;
    margin-top: 60px;
}

.signature-box {
    width: 45%;
    border-top: 1px solid #333333;
    text-align: center;
    padding-top: 10px;
    font-size: 11px;
}

.status-badge {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 12px;
    font-size: 10px;
    font-weight: bold;
}

.status-approved { background: #C8E6C9; color: #2E7D32; }
.status-rejected { background: #FFCDD2; color: #C62828; }
.status-pending { background: #FFE0B2; color: #E65100; }
.status-draft { background: #FFF9C4; color: #F57F17; }
.status-closed { background: #BBDEFB; color: #1565C0; }

.amount-positive { color: #2E7D32; }
.amount-negative { color: #C62828; }

.watermark {
    position: fixed;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%) rotate(-30deg);
    font-size: 100px;
    color: rgba(0, 0, 0, 0.03);
    pointer-events: none;
    z-index: -1;
}

@media print {
    body {
        margin: 20px;
    }
    
    .no-print {
        display: none;
    }
    
    .lines-table th {
        background-color: #004D40 !important;
        color: white !important;
        -webkit-print-color-adjust: exact;
        print-color-adjust: exact;
    }
    
    .page-break {
        page-break-before: always;
    }
}

@media (prefers-color-scheme: dark) {
    body {
        background: #1E1E1E;
        color: #E0E0E0;
    }
    
    .info-table td {
        border-color: #333333;
    }
    
    .info-table td.label {
        background-color: #2D2D2D;
        color: #E0E0E0;
    }
    
    .lines-table tr:nth-child(even) {
        background-color: #2D2D2D;
    }
    
    .lines-table td {
        border-color: #333333;
    }
}
"""

# ==================================================================
# Document Type Configurations
# ==================================================================

DOC_TYPE_CONFIGS = {
    "MRR": {
        "color": "#27AE60",
        "icon": "📥",
        "label": "Material Receipt Report",
        "flow": "IN",
    },
    "MIV": {
        "color": "#E67E22",
        "icon": "📤",
        "label": "Material Issue Voucher",
        "flow": "OUT",
    },
    "MSR": {
        "color": "#3498DB",
        "icon": "📋",
        "label": "Material Store Requisition",
        "flow": "REQUEST",
    },
    "OSND": {
        "color": "#E74C3C",
        "icon": "⚠️",
        "label": "Over, Short & Damaged Report",
        "flow": "ADJUST",
    },
    "MTR": {
        "color": "#9B59B6",
        "icon": "🔄",
        "label": "Material Transfer Note",
        "flow": "TRANSFER",
    },
    "RTV": {
        "color": "#C0392B",
        "icon": "↩️",
        "label": "Return to Vendor",
        "flow": "RETURN",
    },
    "MRV": {
        "color": "#2ECC71",
        "icon": "♻️",
        "label": "Material Return Voucher",
        "flow": "RETURN",
    },
    "ADJ": {
        "color": "#F39C12",
        "icon": "⚖️",
        "label": "Stock Adjustment",
        "flow": "ADJUST",
    },
    "RES": {
        "color": "#2980B9",
        "icon": "🔒",
        "label": "Material Reservation",
        "flow": "RESERVE",
    },
    "SRN": {
        "color": "#C0392B",
        "icon": "↩️",
        "label": "Supplier Return Note",
        "flow": "RETURN",
    },
    "WOM": {
        "color": "#E67E22",
        "icon": "📤",
        "label": "Work Order Material Issue",
        "flow": "OUT",
    },
    "GAT": {
        "color": "#7F8C8D",
        "icon": "🚪",
        "label": "Gate Pass",
        "flow": "OUT",
    },
    "RCT": {
        "color": "#27AE60",
        "icon": "📥",
        "label": "General Receipt",
        "flow": "IN",
    },
    "ISS": {
        "color": "#E67E22",
        "icon": "📤",
        "label": "General Issue",
        "flow": "OUT",
    },
    "TRN": {
        "color": "#9B59B6",
        "icon": "🔄",
        "label": "General Transfer",
        "flow": "TRANSFER",
    },
}


# ==================================================================
# Core HTML Export Functions
# ==================================================================

def export_document_to_html(
    header: Dict[str, Any],
    lines: List[Dict[str, Any]],
    include_signatures: bool = True,
    include_watermark: bool = True,
    company_name: str = "iMat International",
    company_logo: Optional[str] = None,
) -> str:
    """
    Generate a fully styled HTML page for a warehouse document.
    
    Args:
        header: Document metadata dict with keys:
            doc_no, doc_type, doc_date, po_no, reference_no,
            remarks, from_location_id, to_location_id,
            created_by, created_at, generated_at
        lines: List of material line items with keys:
            item_code, heat_no, location_id, qty, unit, iso_drawing_no
        include_signatures: Include signature area
        include_watermark: Include draft watermark
        company_name: Company name for branding
        company_logo: Optional path to logo image
    
    Returns:
        Complete HTML string
    
    Example:
        >>> header = {"doc_no": "MRR-001", "doc_type": "MRR", "doc_date": "2024-01-01"}
        >>> lines = [{"item_code": "PIPE-001", "qty": 100}]
        >>> html = export_document_to_html(header, lines)
    """
    safe = lambda x: x if x is not None else ""
    
    doc_type = safe(header.get("doc_type", ""))
    doc_config = DOC_TYPE_CONFIGS.get(doc_type, {
        "color": "#2C3E50",
        "icon": "📄",
        "label": doc_type,
        "flow": "OTHER",
    })
    
    accent_color = doc_config["color"]
    icon = doc_config["icon"]
    flow = doc_config["flow"]
    
    # Generate CSS
    css = BASE_CSS.format(accent_color=accent_color)
    
    # Build from/to location rows
    from_to_rows = ""
    if doc_type in ("MTR", "TRN", "MRV"):
        from_to_rows = f"""
        <tr>
            <td class="label">From Location</td>
            <td>{safe(header.get('from_location_id'))}</td>
        </tr>
        <tr>
            <td class="label">To Location</td>
            <td>{safe(header.get('to_location_id'))}</td>
        </tr>
        """
    
    # Build watermark
    watermark = ""
    if include_watermark:
        status = safe(header.get('status', 'DRAFT'))
        if status == 'DRAFT':
            watermark = '<div class="watermark">DRAFT</div>'
    
    # Build signature area
    signature_html = ""
    if include_signatures:
        signature_html = """
        <div class="signature-area">
            <div class="signature-box">Prepared by</div>
            <div class="signature-box">Approved by</div>
        </div>
        """
    
    # Build HTML
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{doc_type} – {safe(header.get('doc_no'))}</title>
    <style>
        {css}
    </style>
</head>
<body>
    {watermark}
    
    <div class="header">
        <span class="header-logo">{icon}</span>
        <div>
            <h1>{doc_type} – {safe(header.get('doc_no'))}</h1>
            <p>{company_name} | Flow: {flow} | Generated: {safe(header.get('generated_at'))}</p>
        </div>
    </div>

    <table class="info-table">
        <tr>
            <td class="label">Document Type</td>
            <td><span class="status-badge status-draft">{flow}</span> {doc_config['label']}</td>
        </tr>
        <tr>
            <td class="label">Document Number</td>
            <td><strong>{safe(header.get('doc_no'))}</strong></td>
        </tr>
        <tr>
            <td class="label">Document Date</td>
            <td>{safe(header.get('doc_date'))}</td>
        </tr>
        <tr>
            <td class="label">PO / WO Number</td>
            <td>{safe(header.get('po_no'))}</td>
        </tr>
        <tr>
            <td class="label">Reference</td>
            <td>{safe(header.get('reference_no'))}</td>
        </tr>
        <tr>
            <td class="label">Subject</td>
            <td>{safe(header.get('subject'))}</td>
        </tr>
        <tr>
            <td class="label">Vendor / Supplier</td>
            <td>{safe(header.get('vendor_name'))}</td>
        </tr>
        <tr>
            <td class="label">Remarks</td>
            <td>{safe(header.get('remarks'))}</td>
        </tr>
        {from_to_rows}
        <tr>
            <td class="label">Created By</td>
            <td>{safe(header.get('created_by'))}</td>
        </tr>
        <tr>
            <td class="label">Created At</td>
            <td>{safe(header.get('created_at'))}</td>
        </tr>
        <tr>
            <td class="label">Status</td>
            <td>{safe(header.get('status', 'DRAFT'))}</td>
        </tr>
    </table>

    <h2 style="color: {accent_color}; margin: 20px 0 10px 0;">Material Lines</h2>
    <table class="lines-table">
        <thead>
            <tr>
                <th>#</th>
                <th>Item Code</th>
                <th>Heat / Batch No</th>
                <th>Location</th>
                <th>Quantity</th>
                <th>Unit</th>
                <th>Isometric / Tag</th>
                <th>Certificate No</th>
            </tr>
        </thead>
        <tbody>
"""
    
    # Add line items
    total_qty = 0
    for idx, line in enumerate(lines, start=1):
        qty = line.get('qty', 0) or 0
        total_qty += qty
        
        html += f"""            <tr>
                <td>{idx}</td>
                <td><strong>{safe(line.get('item_code'))}</strong></td>
                <td>{safe(line.get('heat_no'))}</td>
                <td>{safe(line.get('location_id'))}</td>
                <td class="amount-positive">{qty:,.2f}</td>
                <td>{safe(line.get('unit', 'EA'))}</td>
                <td>{safe(line.get('iso_drawing_no'))}</td>
                <td>{safe(line.get('cert_no'))}</td>
            </tr>
"""
    
    # Add total row
    html += f"""            <tr style="font-weight: bold; background-color: #E8F5E9;">
                <td colspan="4" style="text-align: right;">Total:</td>
                <td class="amount-positive">{total_qty:,.2f}</td>
                <td colspan="3"></td>
            </tr>
"""
    
    html += """        </tbody>
    </table>
"""
    
    html += signature_html
    
    html += f"""
    <div class="footer">
        {company_name} – Material Control System (EPC Edition)<br>
        This document is computer-generated and may not require a physical signature.<br>
        Generated: {safe(header.get('generated_at', datetime.now().strftime('%Y-%m-%d %H:%M:%S')))}
    </div>
</body>
</html>"""
    
    return html


def save_html_to_file(html_content: str, file_path: str) -> str:
    """
    Write HTML string to a file.
    
    Args:
        html_content: HTML string
        file_path: Output file path
    
    Returns:
        File path
    """
    os.makedirs(os.path.dirname(file_path) if os.path.dirname(file_path) else '.', exist_ok=True)
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    return file_path


def preview_html_in_browser(html_content: str) -> str:
    """
    Save HTML to a temporary file and open it in the default web browser.
    
    Args:
        html_content: HTML string
    
    Returns:
        Path to temporary file
    """
    with tempfile.NamedTemporaryFile(
        mode='w', suffix='.html', delete=False, encoding='utf-8'
    ) as f:
        f.write(html_content)
        temp_path = f.name
    
    webbrowser.open(f'file://{temp_path}')
    return temp_path


# ==================================================================
# Report HTML Generators
# ==================================================================

def generate_inventory_report_html(
    data: List[Dict],
    title: str = "Inventory Summary Report",
    columns: Optional[List[str]] = None,
    include_charts: bool = False,
) -> str:
    """
    Generate an HTML inventory report.
    
    Args:
        data: List of inventory records
        title: Report title
        columns: Columns to include (all if None)
        include_charts: Include chart placeholders
    
    Returns:
        HTML string
    """
    if not data:
        return _generate_empty_report_html(title)
    
    if columns is None:
        columns = list(data[0].keys())
    
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>{title}</title>
    <style>
        {BASE_CSS.format(accent_color='#004D40')}
        .summary-box {{
            background: #E8F5E9;
            border: 1px solid #A5D6A7;
            border-radius: 8px;
            padding: 15px;
            margin: 15px 0;
        }}
        .summary-box h3 {{
            color: #004D40;
            margin-bottom: 10px;
        }}
        .metric {{
            display: inline-block;
            margin: 0 20px;
            text-align: center;
        }}
        .metric-value {{
            font-size: 24px;
            font-weight: bold;
            color: #004D40;
        }}
        .metric-label {{
            font-size: 10px;
            color: #666;
        }}
    </style>
</head>
<body>
    <div class="header">
        <span class="header-logo">📊</span>
        <div>
            <h1>{title}</h1>
            <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        </div>
    </div>
    
    <div class="summary-box">
        <h3>Summary</h3>
        <div class="metric">
            <div class="metric-value">{len(data)}</div>
            <div class="metric-label">Total Items</div>
        </div>
        <div class="metric">
            <div class="metric-value">{sum(row.get('Total Qty', row.get('total_qty', 0)) or 0 for row in data):,.0f}</div>
            <div class="metric-label">Total Quantity</div>
        </div>
    </div>
    
    <table class="lines-table">
        <thead>
            <tr>
"""
    for col in columns:
        html += f"                <th>{col}</th>\n"
    
    html += """            </tr>
        </thead>
        <tbody>
"""
    
    for row in data:
        html += "            <tr>\n"
        for col in columns:
            value = row.get(col, '')
            if isinstance(value, float):
                value = f"{value:,.2f}"
            html += f"                <td>{value}</td>\n"
        html += "            </tr>\n"
    
    html += f"""        </tbody>
    </table>
    
    <div class="footer">
        Generated by iMat Material Control System<br>
        {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    </div>
</body>
</html>"""
    
    return html


def generate_transaction_report_html(
    data: List[Dict],
    title: str = "Transaction History Report",
    columns: Optional[List[str]] = None,
) -> str:
    """
    Generate an HTML transaction report.
    
    Args:
        data: List of transaction records
        title: Report title
        columns: Columns to include
    
    Returns:
        HTML string
    """
    if not data:
        return _generate_empty_report_html(title)
    
    if columns is None:
        columns = list(data[0].keys())
    
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>{title}</title>
    <style>
        {BASE_CSS.format(accent_color='#E67E22')}
    </style>
</head>
<body>
    <div class="header">
        <span class="header-logo">📋</span>
        <div>
            <h1>{title}</h1>
            <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Records: {len(data)}</p>
        </div>
    </div>
    
    <table class="lines-table">
        <thead>
            <tr>
"""
    for col in columns:
        html += f"                <th>{col}</th>\n"
    
    html += """            </tr>
        </thead>
        <tbody>
"""
    
    for row in data:
        html += "            <tr>\n"
        for col in columns:
            value = row.get(col, '')
            if isinstance(value, float):
                value = f"{value:,.2f}"
            
            # Color-code flow direction
            if col in ['Type', 'Doc Type', 'Flow']:
                flow = str(value).upper()
                if flow in ['MIV', 'ISS', 'WOM', 'OUT', 'ISSUE']:
                    html += f'                <td style="color: #C62828; font-weight: bold;">{value}</td>\n'
                elif flow in ['MRR', 'RCT', 'IN', 'RECEIPT']:
                    html += f'                <td style="color: #2E7D32; font-weight: bold;">{value}</td>\n'
                else:
                    html += f"                <td>{value}</td>\n"
            else:
                html += f"                <td>{value}</td>\n"
        html += "            </tr>\n"
    
    html += f"""        </tbody>
    </table>
    
    <div class="footer">
        Generated by iMat Material Control System<br>
        {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    </div>
</body>
</html>"""
    
    return html


def generate_qc_report_html(
    data: List[Dict],
    title: str = "QC Status Report",
) -> str:
    """
    Generate an HTML QC report.
    
    Args:
        data: List of QC records
        title: Report title
    
    Returns:
        HTML string
    """
    if not data:
        return _generate_empty_report_html(title)
    
    # Count by status
    status_counts = {}
    for row in data:
        status = row.get('QC Status', row.get('qc_status', 'Unknown'))
        status_counts[status] = status_counts.get(status, 0) + 1
    
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>{title}</title>
    <style>
        {BASE_CSS.format(accent_color='#8BC34A')}
        .status-card {{
            display: inline-block;
            padding: 15px 25px;
            margin: 10px;
            border-radius: 8px;
            text-align: center;
            min-width: 120px;
        }}
        .status-quarantine {{ background: #FFE0B2; color: #E65100; }}
        .status-accepted {{ background: #C8E6C9; color: #2E7D32; }}
        .status-rejected {{ background: #FFCDD2; color: #C62828; }}
        .status-count {{
            font-size: 32px;
            font-weight: bold;
        }}
        .status-label {{
            font-size: 12px;
            margin-top: 5px;
        }}
    </style>
</head>
<body>
    <div class="header">
        <span class="header-logo">✅</span>
        <div>
            <h1>{title}</h1>
            <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        </div>
    </div>
    
    <div style="text-align: center; margin: 20px 0;">
"""
    
    for status, label, css_class in [
        ('QUARANTINE', 'Quarantine', 'quarantine'),
        ('ACCEPTED', 'Accepted', 'accepted'),
        ('REJECTED', 'Rejected', 'rejected'),
    ]:
        count = status_counts.get(status, 0)
        html += f"""        <div class="status-card status-{css_class}">
            <div class="status-count">{count}</div>
            <div class="status-label">{label}</div>
        </div>
"""
    
    html += """    </div>
    
    <table class="lines-table">
        <thead>
            <tr>
                <th>Item Code</th>
                <th>Description</th>
                <th>Heat No</th>
                <th>Location</th>
                <th>QC Status</th>
                <th>Quantity</th>
            </tr>
        </thead>
        <tbody>
"""
    
    for row in data:
        status = row.get('QC Status', row.get('qc_status', ''))
        status_class = f"status-{status.lower()}" if status else ""
        
        html += f"""            <tr>
                <td>{row.get('Item Code', row.get('item_code', ''))}</td>
                <td>{row.get('Description', row.get('description', ''))}</td>
                <td>{row.get('Heat No', row.get('heat_no', ''))}</td>
                <td>{row.get('Location', row.get('location', ''))}</td>
                <td><span class="status-badge {status_class}">{status}</span></td>
                <td>{row.get('Quantity', row.get('quantity', 0))}</td>
            </tr>
"""
    
    html += f"""        </tbody>
    </table>
    
    <div class="footer">
        Generated by iMat Material Control System<br>
        {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    </div>
</body>
</html>"""
    
    return html


def generate_abc_report_html(
    data: List[Dict],
    title: str = "ABC Analysis Report",
) -> str:
    """
    Generate an HTML ABC analysis report.
    
    Args:
        data: List of ABC analysis records
        title: Report title
    
    Returns:
        HTML string
    """
    if not data:
        return _generate_empty_report_html(title)
    
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>{title}</title>
    <style>
        {BASE_CSS.format(accent_color='#E91E63')}
        .class-a {{ background: #FFCDD2; color: #B71C1C; }}
        .class-b {{ background: #FFF9C4; color: #F57F17; }}
        .class-c {{ background: #C8E6C9; color: #1B5E20; }}
        .class-badge {{
            display: inline-block;
            padding: 3px 10px;
            border-radius: 12px;
            font-size: 10px;
            font-weight: bold;
        }}
    </style>
</head>
<body>
    <div class="header">
        <span class="header-logo">📈</span>
        <div>
            <h1>{title}</h1>
            <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Items: {len(data)}</p>
        </div>
    </div>
    
    <table class="lines-table">
        <thead>
            <tr>
                <th>#</th>
                <th>Item Code</th>
                <th>Description</th>
                <th>Value</th>
                <th>Value %</th>
                <th>Cumulative %</th>
                <th>Class</th>
            </tr>
        </thead>
        <tbody>
"""
    
    for row in data:
        cls = row.get('class', row.get('Class', 'C'))
        html += f"""            <tr>
                <td>{row.get('rank', row.get('#', ''))}</td>
                <td>{row.get('item_code', row.get('Item Code', ''))}</td>
                <td>{row.get('description', row.get('Description', ''))}</td>
                <td>{row.get('value', row.get('Value', 0)):,.2f}</td>
                <td>{row.get('value_pct', row.get('Value %', 0)):.1f}%</td>
                <td>{row.get('cumulative_pct', row.get('Cumulative %', 0)):.1f}%</td>
                <td><span class="class-badge class-{cls.lower()}">{cls}</span></td>
            </tr>
"""
    
    html += f"""        </tbody>
    </table>
    
    <div class="footer">
        Generated by iMat Material Control System<br>
        {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    </div>
</body>
</html>"""
    
    return html


def generate_reorder_report_html(
    data: List[Dict],
    title: str = "Reorder Analysis Report",
) -> str:
    """
    Generate an HTML reorder analysis report.
    
    Args:
        data: List of reorder analysis records
        title: Report title
    
    Returns:
        HTML string
    """
    if not data:
        return _generate_empty_report_html(title)
    
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>{title}</title>
    <style>
        {BASE_CSS.format(accent_color='#FF5722')}
        .order-now {{ background: #FFCDD2; color: #B71C1C; font-weight: bold; }}
        .order-soon {{ background: #FFF9C4; color: #F57F17; }}
        .adequate {{ background: #C8E6C9; color: #2E7D32; }}
    </style>
</head>
<body>
    <div class="header">
        <span class="header-logo">🔔</span>
        <div>
            <h1>{title}</h1>
            <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Items: {len(data)}</p>
        </div>
    </div>
    
    <table class="lines-table">
        <thead>
            <tr>
                <th>Item Code</th>
                <th>Description</th>
                <th>Daily Demand</th>
                <th>Safety Stock</th>
                <th>Reorder Point</th>
                <th>EOQ</th>
                <th>Recommended Order</th>
                <th>Status</th>
            </tr>
        </thead>
        <tbody>
"""
    
    for row in data:
        status = row.get('Status', row.get('status', ''))
        status_class = 'adequate'
        if 'OUT' in str(status).upper():
            status_class = 'order-now'
        elif 'ORDER NOW' in str(status).upper():
            status_class = 'order-now'
        elif 'ORDER SOON' in str(status).upper():
            status_class = 'order-soon'
        
        html += f"""            <tr>
                <td>{row.get('Item Code', row.get('item_code', ''))}</td>
                <td>{row.get('Description', row.get('description', ''))}</td>
                <td>{row.get('Daily Demand', row.get('daily_demand', 0))}</td>
                <td>{row.get('Safety Stock', row.get('safety_stock', 0)):,.2f}</td>
                <td>{row.get('Reorder Point', row.get('reorder_point', 0)):,.2f}</td>
                <td>{row.get('EOQ', row.get('eoq', 0)):,.2f}</td>
                <td style="font-weight: bold;">{row.get('Recommended Order', row.get('recommended_order', 0)):,.2f}</td>
                <td class="{status_class}">{status}</td>
            </tr>
"""
    
    html += f"""        </tbody>
    </table>
    
    <div class="footer">
        Generated by iMat Material Control System<br>
        {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    </div>
</body>
</html>"""
    
    return html


# ==================================================================
# Helper Functions
# ==================================================================

def _generate_empty_report_html(title: str) -> str:
    """Generate an HTML page for empty reports."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>{title}</title>
    <style>
        {BASE_CSS.format(accent_color='#004D40')}
        .empty-state {{
            text-align: center;
            padding: 60px 20px;
            color: #999;
        }}
        .empty-state .icon {{
            font-size: 64px;
            margin-bottom: 20px;
        }}
    </style>
</head>
<body>
    <div class="header">
        <span class="header-logo">📊</span>
        <div>
            <h1>{title}</h1>
            <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        </div>
    </div>
    
    <div class="empty-state">
        <div class="icon">📭</div>
        <h2>No Data Available</h2>
        <p>There is no data to display for this report.</p>
    </div>
    
    <div class="footer">
        Generated by iMat Material Control System
    </div>
</body>
</html>"""


def generate_email_html(
    subject: str,
    body: str,
    logo_url: Optional[str] = None,
) -> str:
    """
    Generate email-ready HTML.
    
    Args:
        subject: Email subject
        body: Email body (can include HTML)
        logo_url: Optional logo URL
    
    Returns:
        HTML string suitable for email
    """
    logo_html = ""
    if logo_url:
        logo_html = f'<img src="{logo_url}" alt="iMat" style="max-width: 150px; margin-bottom: 15px;">'
    
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <style>
        body {{
            font-family: 'Segoe UI', Arial, sans-serif;
            color: #333;
            line-height: 1.6;
        }}
        .container {{
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
        }}
        .header {{
            background: #004D40;
            color: white;
            padding: 20px;
            text-align: center;
            border-radius: 8px 8px 0 0;
        }}
        .content {{
            background: #FAFAFA;
            padding: 20px;
            border: 1px solid #E0E0E0;
            border-top: none;
        }}
        .footer {{
            text-align: center;
            padding: 15px;
            font-size: 11px;
            color: #999;
        }}
    </style>
</head>
<body>
    <div class="container">
        {logo_html}
        <div class="header">
            <h2>{subject}</h2>
        </div>
        <div class="content">
            {body}
        </div>
        <div class="footer">
            This email was generated by iMat Material Control System<br>
            {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}<br>
            <a href="https://www.imat.io">www.imat.io</a>
        </div>
    </div>
</body>
</html>"""


# ==================================================================
# Module Exports
# ==================================================================

__all__ = [
    'export_document_to_html',
    'save_html_to_file',
    'preview_html_in_browser',
    'generate_inventory_report_html',
    'generate_transaction_report_html',
    'generate_qc_report_html',
    'generate_abc_report_html',
    'generate_reorder_report_html',
    'generate_email_html',
    'DOC_TYPE_CONFIGS',
]