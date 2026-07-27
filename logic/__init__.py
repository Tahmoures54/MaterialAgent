# logic/__init__.py
from .inventory import (
    search_inventory, 
    get_filter_options, 
    add_transaction,
    update_inventory_summary,
    get_inventory_by_item,
    get_all_inventory
)
from .reports import (
    generate_inventory_summary, 
    generate_transaction_report,
    get_low_stock_items,
    get_stock_value_report,
    get_movement_report
)
from .stock_logic import (
    add_stock,
    remove_stock,
    move_stock,
    change_qc_status,
    get_stock_record,
    get_stock_by_item,
    get_stock_by_location
)
from .document_logic import (
    create_document,
    update_document_status,
    get_document_by_no,
    get_documents_by_date,
    delete_document
)
from .product_logic import (
    create_product,
    update_product,
    get_product,
    get_all_products,
    search_products,
    delete_product
)
from .location_logic import (
    create_location,
    get_all_locations,
    get_location_by_code,
    get_location_by_id,
    update_location,
    delete_location,
    get_location_tree
)
from .reports_logic import (
    get_current_inventory,
    get_preservation_alerts,
    get_traceability_report,
    get_stock_movements,
    get_qc_summary
)
from .material_request_logic import (
    create_material_request,
    update_material_request_status,
    get_material_requests,
    get_material_request_by_no
)

__all__ = [
    # Inventory
    'search_inventory',
    'get_filter_options',
    'add_transaction',
    'update_inventory_summary',
    'get_inventory_by_item',
    'get_all_inventory',
    # Reports
    'generate_inventory_summary',
    'generate_transaction_report',
    'get_low_stock_items',
    'get_stock_value_report',
    'get_movement_report',
    # Stock
    'add_stock',
    'remove_stock',
    'move_stock',
    'change_qc_status',
    'get_stock_record',
    'get_stock_by_item',
    'get_stock_by_location',
    # Document
    'create_document',
    'update_document_status',
    'get_document_by_no',
    'get_documents_by_date',
    'delete_document',
    # Product
    'create_product',
    'update_product',
    'get_product',
    'get_all_products',
    'search_products',
    'delete_product',
    # Location
    'create_location',
    'get_all_locations',
    'get_location_by_code',
    'get_location_by_id',
    'update_location',
    'delete_location',
    'get_location_tree',
    # Reports Logic
    'get_current_inventory',
    'get_preservation_alerts',
    'get_traceability_report',
    'get_stock_movements',
    'get_qc_summary',
    # Material Request
    'create_material_request',
    'update_material_request_status',
    'get_material_requests',
    'get_material_request_by_no',
]