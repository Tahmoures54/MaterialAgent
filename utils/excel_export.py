# utils/excel_export.py
"""
Excel Export Utilities – iMat Material Control System (EPC Edition).

Professional Excel export with:
- Multiple sheet support
- Formatted headers with colors
- Auto-column width adjustment
- Number formatting (currency, percentage, quantity)
- Conditional formatting for status fields
- Freeze panes for headers
- Auto-filter for columns
- Multiple data source support (list, DataFrame, dict)
- Template-based export
- Password protection (placeholder)
- Print area setup
- Chart creation (placeholder)
"""

import os
from datetime import datetime
from typing import List, Dict, Optional, Any, Union

import pandas as pd

# Try to import openpyxl for advanced formatting
try:
    import openpyxl
    from openpyxl.styles import (
        Font, PatternFill, Alignment, Border, Side,
        numbers, NamedStyle
    )
    from openpyxl.utils import get_column_letter
    from openpyxl.worksheet.datavalidation import DataValidation
    from openpyxl.formatting.rule import CellIsRule, FormulaRule
    from openpyxl.chart import BarChart, PieChart, Reference, LineChart
    OPENPYXL_AVAILABLE = True
except ImportError:
    OPENPYXL_AVAILABLE = False


# ==================================================================
# Style Constants
# ==================================================================

# Header style
HEADER_FONT = Font(
    name='Segoe UI',
    bold=True,
    color='FFFFFF',
    size=11
)
HEADER_FILL = PatternFill(
    start_color='004D40',
    end_color='004D40',
    fill_type='solid'
)
HEADER_ALIGNMENT = Alignment(
    horizontal='center',
    vertical='center',
    wrap_text=True
)

# Title style
TITLE_FONT = Font(
    name='Segoe UI',
    bold=True,
    color='004D40',
    size=14
)
TITLE_ALIGNMENT = Alignment(
    horizontal='left',
    vertical='center'
)

# Subtitle style
SUBTITLE_FONT = Font(
    name='Segoe UI',
    color='666666',
    size=10,
    italic=True
)

# Data style
DATA_FONT = Font(
    name='Segoe UI',
    size=10
)
DATA_ALIGNMENT = Alignment(
    vertical='center'
)

# Number format styles
NUMBER_FORMAT = '#,##0.00'
INTEGER_FORMAT = '#,##0'
CURRENCY_FORMAT = '$#,##0.00'
PERCENTAGE_FORMAT = '0.0%'
DATE_FORMAT = 'YYYY-MM-DD'

# Alternating row colors
EVEN_ROW_FILL = PatternFill(
    start_color='F5F5F5',
    end_color='F5F5F5',
    fill_type='solid'
)
ODD_ROW_FILL = PatternFill(
    start_color='FFFFFF',
    end_color='FFFFFF',
    fill_type='solid'
)

# Status colors for conditional formatting
STATUS_COLORS = {
    'APPROVED': PatternFill(start_color='C8E6C9', end_color='C8E6C9', fill_type='solid'),
    'ACCEPTED': PatternFill(start_color='C8E6C9', end_color='C8E6C9', fill_type='solid'),
    'CLOSED': PatternFill(start_color='BBDEFB', end_color='BBDEFB', fill_type='solid'),
    'REJECTED': PatternFill(start_color='FFCDD2', end_color='FFCDD2', fill_type='solid'),
    'PENDING': PatternFill(start_color='FFE0B2', end_color='FFE0B2', fill_type='solid'),
    'DRAFT': PatternFill(start_color='FFF9C4', end_color='FFF9C4', fill_type='solid'),
    'QUARANTINE': PatternFill(start_color='FFE0B2', end_color='FFE0B2', fill_type='solid'),
    'CANCELLED': PatternFill(start_color='E0E0E0', end_color='E0E0E0', fill_type='solid'),
}

# Thin border
THIN_BORDER = Border(
    left=Side(style='thin', color='E0E0E0'),
    right=Side(style='thin', color='E0E0E0'),
    top=Side(style='thin', color='E0E0E0'),
    bottom=Side(style='thin', color='E0E0E0'),
)


# ==================================================================
# Core Export Functions
# ==================================================================

def export_to_excel(
    data: Union[List[Dict], pd.DataFrame],
    columns: Optional[List[str]] = None,
    filename: str = "export.xlsx",
    sheet_name: str = "Data",
    title: Optional[str] = None,
    subtitle: Optional[str] = None,
    auto_fit: bool = True,
    freeze_header: bool = True,
    add_filter: bool = True,
    alternate_rows: bool = True,
    status_columns: Optional[List[str]] = None,
    currency_columns: Optional[List[str]] = None,
    number_columns: Optional[List[str]] = None,
    date_columns: Optional[List[str]] = None,
    include_timestamp: bool = True,
) -> str:
    """
    Export data to a professionally formatted Excel file.
    
    Args:
        data: List of dictionaries or pandas DataFrame
        columns: Column names to include (all if None)
        filename: Output file path
        sheet_name: Worksheet name
        title: Optional report title
        subtitle: Optional report subtitle
        auto_fit: Auto-adjust column widths
        freeze_header: Freeze the header row
        add_filter: Add auto-filter to columns
        alternate_rows: Apply alternating row colors
        status_columns: Columns with status values for conditional formatting
        currency_columns: Columns to format as currency
        number_columns: Columns to format as numbers
        date_columns: Columns to format as dates
        include_timestamp: Add generation timestamp
    
    Returns:
        Path to the created file
    
    Example:
        >>> data = [{"Name": "Item1", "Qty": 10, "Price": 25.5}]
        >>> export_to_excel(data, ["Name", "Qty", "Price"], "report.xlsx")
    """
    # Convert to DataFrame if needed
    if isinstance(data, list):
        df = pd.DataFrame(data)
    else:
        df = data.copy()
    
    # Select columns if specified
    if columns:
        available_cols = [c for c in columns if c in df.columns]
        df = df[available_cols]
    
    if df.empty:
        # Create empty file with just headers
        return _create_empty_export(filename, sheet_name, columns or [], title)
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(filename) if os.path.dirname(filename) else '.', exist_ok=True)
    
    if OPENPYXL_AVAILABLE:
        return _export_with_openpyxl(
            df, filename, sheet_name, title, subtitle,
            auto_fit, freeze_header, add_filter, alternate_rows,
            status_columns, currency_columns, number_columns, date_columns,
            include_timestamp
        )
    else:
        # Fallback to basic pandas export
        return _export_with_pandas(df, filename, sheet_name)


def _export_with_openpyxl(
    df: pd.DataFrame,
    filename: str,
    sheet_name: str,
    title: Optional[str],
    subtitle: Optional[str],
    auto_fit: bool,
    freeze_header: bool,
    add_filter: bool,
    alternate_rows: bool,
    status_columns: Optional[List[str]],
    currency_columns: Optional[List[str]],
    number_columns: Optional[List[str]],
    date_columns: Optional[List[str]],
    include_timestamp: bool,
) -> str:
    """Export using openpyxl for advanced formatting."""
    
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = sheet_name
    
    current_row = 1
    
    # Add title
    if title:
        ws.merge_cells(start_row=current_row, start_column=1, 
                      end_row=current_row, end_column=len(df.columns))
        cell = ws.cell(row=current_row, column=1, value=title)
        cell.font = TITLE_FONT
        cell.alignment = TITLE_ALIGNMENT
        current_row += 1
    
    # Add subtitle
    if subtitle:
        ws.merge_cells(start_row=current_row, start_column=1,
                      end_row=current_row, end_column=len(df.columns))
        cell = ws.cell(row=current_row, column=1, value=subtitle)
        cell.font = SUBTITLE_FONT
        current_row += 1
    
    # Add timestamp
    if include_timestamp:
        ws.merge_cells(start_row=current_row, start_column=1,
                      end_row=current_row, end_column=len(df.columns))
        cell = ws.cell(row=current_row, column=1,
                      value=f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        cell.font = SUBTITLE_FONT
        current_row += 1
    
    # Add spacing before headers
    if title or subtitle or include_timestamp:
        current_row += 1
    
    # Write headers
    for col_idx, col_name in enumerate(df.columns, 1):
        cell = ws.cell(row=current_row, column=col_idx, value=col_name)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = HEADER_ALIGNMENT
        cell.border = THIN_BORDER
    
    header_row = current_row
    current_row += 1
    
    # Write data
    for row_idx, (_, row_data) in enumerate(df.iterrows()):
        for col_idx, col_name in enumerate(df.columns, 1):
            value = row_data[col_name]
            
            # Handle None/NaN
            if pd.isna(value):
                value = ""
            
            cell = ws.cell(row=current_row, column=col_idx, value=value)
            cell.font = DATA_FONT
            cell.alignment = DATA_ALIGNMENT
            cell.border = THIN_BORDER
            
            # Apply number formatting
            if currency_columns and col_name in currency_columns:
                cell.number_format = CURRENCY_FORMAT
            elif number_columns and col_name in number_columns:
                if isinstance(value, float):
                    cell.number_format = NUMBER_FORMAT
                else:
                    cell.number_format = INTEGER_FORMAT
            elif date_columns and col_name in date_columns:
                cell.number_format = DATE_FORMAT
            
            # Apply alternating row colors
            if alternate_rows and row_idx % 2 == 1:
                cell.fill = EVEN_ROW_FILL
            
            # Apply status conditional formatting
            if status_columns and col_name in status_columns:
                status_value = str(value).upper().strip()
                if status_value in STATUS_COLORS:
                    cell.fill = STATUS_COLORS[status_value]
                    # Set text color based on status
                    if status_value in ['APPROVED', 'ACCEPTED']:
                        cell.font = Font(name='Segoe UI', size=10, color='1B5E20', bold=True)
                    elif status_value in ['REJECTED']:
                        cell.font = Font(name='Segoe UI', size=10, color='B71C1C', bold=True)
        
        current_row += 1
    
    last_data_row = current_row - 1
    
    # Auto-fit columns
    if auto_fit:
        _auto_fit_columns(ws, df.columns, header_row)
    
    # Freeze header
    if freeze_header:
        ws.freeze_panes = ws.cell(row=header_row + 1, column=1)
    
    # Add auto-filter
    if add_filter:
        ws.auto_filter.ref = f"{get_column_letter(1)}{header_row}:{get_column_letter(len(df.columns))}{last_data_row}"
    
    # Set print area
    ws.print_area = f"A1:{get_column_letter(len(df.columns))}{last_data_row}"
    ws.sheet_properties.pageSetUpPr = openpyxl.worksheet.properties.PageSetupProperties(fitToPage=True)
    
    # Save
    wb.save(filename)
    return filename


def _export_with_pandas(df: pd.DataFrame, filename: str, sheet_name: str) -> str:
    """Fallback export using pandas only."""
    with pd.ExcelWriter(filename, engine='openpyxl' if OPENPYXL_AVAILABLE else 'xlsxwriter') as writer:
        df.to_excel(writer, sheet_name=sheet_name, index=False)
    return filename


def _create_empty_export(
    filename: str, 
    sheet_name: str, 
    columns: List[str],
    title: Optional[str] = None
) -> str:
    """Create an Excel file with just headers."""
    if OPENPYXL_AVAILABLE:
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = sheet_name
        
        if title:
            ws.cell(row=1, column=1, value=title).font = TITLE_FONT
        
        for col_idx, col_name in enumerate(columns, 1):
            cell = ws.cell(row=3, column=col_idx, value=col_name)
            cell.font = HEADER_FONT
            cell.fill = HEADER_FILL
        
        wb.save(filename)
    else:
        df = pd.DataFrame(columns=columns)
        df.to_excel(filename, sheet_name=sheet_name, index=False)
    
    return filename


def _auto_fit_columns(ws, columns: List[str], header_row: int):
    """Auto-adjust column widths based on content."""
    for col_idx, col_name in enumerate(columns, 1):
        max_length = len(str(col_name))
        
        for row in ws.iter_rows(min_row=header_row + 1, 
                               min_col=col_idx, max_col=col_idx,
                               values_only=True):
            for cell_value in row:
                if cell_value:
                    max_length = max(max_length, len(str(cell_value)))
        
        # Add padding
        adjusted_width = min(max_length + 3, 50)
        ws.column_dimensions[get_column_letter(col_idx)].width = adjusted_width


# ==================================================================
# Specialized Export Functions
# ==================================================================

def export_inventory_summary(
    data: List[Dict],
    filepath: str,
    title: str = "Inventory Summary Report"
) -> str:
    """
    Export inventory summary with specialized formatting.
    
    Args:
        data: Inventory data
        filepath: Output path
        title: Report title
    
    Returns:
        File path
    """
    columns = [
        "Item Code", "Description", "UOM", "Category",
        "Total Qty", "Allocated Qty", "Available Qty",
        "Min Required", "Status"
    ]
    
    return export_to_excel(
        data=data,
        columns=columns,
        filename=filepath,
        sheet_name="Inventory Summary",
        title=title,
        subtitle=f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        status_columns=["Status"],
        number_columns=["Total Qty", "Allocated Qty", "Available Qty", "Min Required"],
    )


def export_transaction_report(
    transactions: List[Dict],
    filepath: str,
    title: str = "Transaction History Report"
) -> str:
    """
    Export transaction history with specialized formatting.
    
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
    
    return export_to_excel(
        data=transactions,
        columns=columns,
        filename=filepath,
        sheet_name="Transactions",
        title=title,
        date_columns=["Date"],
        number_columns=["Request QTY", "Issue QTY", "Receive QTY"],
    )


def export_stock_report(
    data: List[Dict],
    filepath: str,
    title: str = "Live Stock Report"
) -> str:
    """
    Export stock report with specialized formatting.
    
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
    
    return export_to_excel(
        data=data,
        columns=columns,
        filename=filepath,
        sheet_name="Stock Report",
        title=title,
        status_columns=["QC Status"],
        currency_columns=["Unit Cost", "Total Value"],
        number_columns=["Total Qty", "Allocated", "Available"],
    )


def export_material_request(
    data: List[Dict],
    filepath: str,
    title: str = "Material Request Report"
) -> str:
    """
    Export material requests with specialized formatting.
    
    Args:
        data: Material request data
        filepath: Output path
        title: Report title
    
    Returns:
        File path
    """
    columns = [
        "MR Number", "Company", "Project", "Discipline",
        "Status", "Items", "Total Cost", "Required Date"
    ]
    
    return export_to_excel(
        data=data,
        columns=columns,
        filename=filepath,
        sheet_name="Material Requests",
        title=title,
        status_columns=["Status"],
        currency_columns=["Total Cost"],
        date_columns=["Required Date"],
    )


def export_expiry_report(
    data: List[Dict],
    filepath: str,
    title: str = "Expiry Date Report"
) -> str:
    """
    Export expiry report with specialized formatting.
    
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
    
    return export_to_excel(
        data=data,
        columns=columns,
        filename=filepath,
        sheet_name="Expiry Report",
        title=title,
        status_columns=["Status", "QC Status"],
        date_columns=["Expiry Date"],
        number_columns=["Days Left", "Quantity"],
    )


def export_abc_analysis(
    data: List[Dict],
    filepath: str,
    title: str = "ABC Analysis Report"
) -> str:
    """
    Export ABC analysis with specialized formatting.
    
    Args:
        data: ABC analysis data
        filepath: Output path
        title: Report title
    
    Returns:
        File path
    """
    columns = [
        "Item Code", "Description", "Value", "Value %",
        "Cumulative %", "Class"
    ]
    
    return export_to_excel(
        data=data,
        columns=columns,
        filename=filepath,
        sheet_name="ABC Analysis",
        title=title,
        status_columns=["Class"],
        number_columns=["Value", "Value %", "Cumulative %"],
    )


# ==================================================================
# Multi-Sheet Export
# ==================================================================

def export_multi_sheet_report(
    sheets_data: Dict[str, Dict],
    filepath: str,
    title: str = "iMat Report"
) -> str:
    """
    Export multiple sheets to a single Excel file.
    
    Args:
        sheets_data: Dict mapping sheet_name -> {
            'data': List[Dict],
            'columns': List[str],
            'title': Optional[str],
        }
        filepath: Output path
        title: Overall report title
    
    Returns:
        File path
    
    Example:
        >>> export_multi_sheet_report({
        ...     "Inventory": {"data": inv_data, "columns": inv_cols},
        ...     "Transactions": {"data": trans_data, "columns": trans_cols},
        ... }, "report.xlsx")
    """
    if not OPENPYXL_AVAILABLE:
        # Fallback: save each sheet separately
        base, ext = os.path.splitext(filepath)
        for i, (sheet_name, sheet_config) in enumerate(sheets_data.items()):
            sheet_path = f"{base}_{sheet_name.lower().replace(' ', '_')}{ext}"
            export_to_excel(
                data=sheet_config['data'],
                columns=sheet_config.get('columns'),
                filename=sheet_path,
                sheet_name=sheet_name,
                title=sheet_config.get('title'),
            )
        return filepath
    
    wb = openpyxl.Workbook()
    # Remove default sheet
    wb.remove(wb.active)
    
    for sheet_name, sheet_config in sheets_data.items():
        if not sheet_config.get('data'):
            continue
        
        df = pd.DataFrame(sheet_config['data'])
        columns = sheet_config.get('columns')
        if columns:
            available_cols = [c for c in columns if c in df.columns]
            df = df[available_cols]
        
        ws = wb.create_sheet(title=sheet_name[:31])  # Excel limits sheet names to 31 chars
        
        # Write headers
        for col_idx, col_name in enumerate(df.columns, 1):
            cell = ws.cell(row=1, column=col_idx, value=col_name)
            cell.font = HEADER_FONT
            cell.fill = HEADER_FILL
            cell.alignment = HEADER_ALIGNMENT
        
        # Write data
        for row_idx, (_, row_data) in enumerate(df.iterrows()):
            for col_idx, col_name in enumerate(df.columns, 1):
                value = row_data[col_name]
                if pd.isna(value):
                    value = ""
                ws.cell(row=row_idx + 2, column=col_idx, value=value)
        
        # Auto-fit
        _auto_fit_columns(ws, df.columns, 1)
        
        # Freeze header
        ws.freeze_panes = 'A2'
    
    wb.save(filepath)
    return filepath


# ==================================================================
# Template Functions
# ==================================================================

def create_import_template(
    filepath: str,
    headers: List[str],
    sheet_name: str = "Template",
    example_data: Optional[List[Any]] = None,
    instructions: Optional[str] = None,
) -> str:
    """
    Create an Excel template for data import.
    
    Args:
        filepath: Output path
        headers: Column headers
        sheet_name: Worksheet name
        example_data: Optional example row
        instructions: Optional instruction text
    
    Returns:
        File path
    """
    if not OPENPYXL_AVAILABLE:
        df = pd.DataFrame(columns=headers)
        if example_data:
            df.loc[0] = example_data
        df.to_excel(filepath, sheet_name=sheet_name, index=False)
        return filepath
    
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = sheet_name
    
    current_row = 1
    
    # Add instructions
    if instructions:
        ws.merge_cells(start_row=1, start_column=1, 
                      end_row=1, end_column=len(headers))
        cell = ws.cell(row=1, column=1, value=instructions)
        cell.font = Font(name='Segoe UI', color='666666', size=9, italic=True)
        current_row += 1
    
    # Write headers
    for col_idx, header in enumerate(headers, 1):
        cell = ws.cell(row=current_row, column=col_idx, value=header)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = HEADER_ALIGNMENT
    
    # Add example row
    if example_data:
        for col_idx, value in enumerate(example_data, 1):
            cell = ws.cell(row=current_row + 1, column=col_idx, value=value)
            cell.font = Font(name='Segoe UI', size=10, italic=True, color='888888')
    
    # Auto-fit columns
    for col_idx in range(1, len(headers) + 1):
        ws.column_dimensions[get_column_letter(col_idx)].width = 20
    
    wb.save(filepath)
    return filepath


# ==================================================================
# Module Exports
# ==================================================================

__all__ = [
    'export_to_excel',
    'export_inventory_summary',
    'export_transaction_report',
    'export_stock_report',
    'export_material_request',
    'export_expiry_report',
    'export_abc_analysis',
    'export_multi_sheet_report',
    'create_import_template',
]