"""Curated EBS report templates (Phase 4, charter D-C/D-D).

These are **standard E-Business Suite reference queries** — parameterized,
read-only starting points an analyst loads, reviews, and edits before running.
They assume a *standard* EBS schema (table/column names vary by version and
customization), so each is labelled "review before running" in the UI and is
**never auto-executed**. Every template is a single SELECT and is validated
against the safety layer by `tests/test_templates.py`.

Parameters are passed as **bind variables** at run time (see ADR-007); the SQL
here contains only `:name` placeholders, never interpolated values.
"""

from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field

from src.core.reports import ReportParam

Module = Literal["GL", "AP", "AR", "PO", "OM"]

REVIEW_NOTE = "Standard EBS reference query — review and adjust before running."


class Template(BaseModel):
    id: str
    module: Module
    name: str
    description: str
    sql: str
    parameters: List[ReportParam] = Field(default_factory=list)


_TEMPLATES: List[Template] = [
    # ----------------------------- General Ledger ----------------------------
    Template(
        id="gl_trial_balance",
        module="GL",
        name="GL Trial Balance (by account)",
        description=f"Net debit/credit per account for a ledger and period. {REVIEW_NOTE}",
        sql=(
            "SELECT b.code_combination_id, b.period_name,\n"
            "       SUM(b.period_net_dr) AS period_dr, SUM(b.period_net_cr) AS period_cr\n"
            "FROM gl_balances b\n"
            "WHERE b.ledger_id = :ledger_id\n"
            "  AND b.period_name = :period_name\n"
            "  AND b.currency_code = :currency_code\n"
            "GROUP BY b.code_combination_id, b.period_name\n"
            "ORDER BY b.code_combination_id"
        ),
        parameters=[
            ReportParam(name="ledger_id", label="Ledger ID", type="number"),
            ReportParam(name="period_name", label="Period name", type="string"),
            ReportParam(name="currency_code", label="Currency", type="string", default="USD"),
        ],
    ),
    Template(
        id="gl_journal_lines",
        module="GL",
        name="GL Journal Lines",
        description=f"Journal header and line detail for a ledger and period. {REVIEW_NOTE}",
        sql=(
            "SELECT h.je_header_id, h.name AS journal_name, l.je_line_num,\n"
            "       l.entered_dr, l.entered_cr, l.accounted_dr, l.accounted_cr\n"
            "FROM gl_je_headers h\n"
            "JOIN gl_je_lines l ON l.je_header_id = h.je_header_id\n"
            "WHERE h.ledger_id = :ledger_id\n"
            "  AND h.period_name = :period_name\n"
            "ORDER BY h.je_header_id, l.je_line_num"
        ),
        parameters=[
            ReportParam(name="ledger_id", label="Ledger ID", type="number"),
            ReportParam(name="period_name", label="Period name", type="string"),
        ],
    ),
    Template(
        id="gl_je_batches",
        module="GL",
        name="GL Journal Batches",
        description=f"Journal batches and posting status for a ledger/period. {REVIEW_NOTE}",
        sql=(
            "SELECT b.je_batch_id, b.name AS batch_name, b.status, b.posted_date,\n"
            "       b.running_total_accounted_dr, b.running_total_accounted_cr\n"
            "FROM gl_je_batches b\n"
            "WHERE b.set_of_books_id = :ledger_id\n"
            "  AND b.default_period_name = :period_name\n"
            "ORDER BY b.je_batch_id"
        ),
        parameters=[
            ReportParam(name="ledger_id", label="Ledger / set of books ID", type="number"),
            ReportParam(name="period_name", label="Period name", type="string"),
        ],
    ),
    # ------------------------------ Payables (AP) ----------------------------
    Template(
        id="ap_invoice_register",
        module="AP",
        name="AP Invoice Register",
        description=f"Invoices entered in an operating unit within a date range. {REVIEW_NOTE}",
        sql=(
            "SELECT i.invoice_id, i.invoice_num, i.invoice_date, i.invoice_amount,\n"
            "       i.invoice_currency_code, i.vendor_id\n"
            "FROM ap_invoices_all i\n"
            "WHERE i.org_id = :org_id\n"
            "  AND i.invoice_date BETWEEN :date_from AND :date_to\n"
            "ORDER BY i.invoice_date, i.invoice_num"
        ),
        parameters=[
            ReportParam(name="org_id", label="Operating unit (org) ID", type="number"),
            ReportParam(name="date_from", label="Invoice date from", type="date"),
            ReportParam(name="date_to", label="Invoice date to", type="date"),
        ],
    ),
    Template(
        id="ap_open_payables",
        module="AP",
        name="AP Open Payables",
        description=f"Unpaid payment schedules (open payables) for an operating unit. {REVIEW_NOTE}",
        sql=(
            "SELECT i.invoice_num, i.invoice_date, ps.due_date,\n"
            "       ps.amount_remaining, ps.gross_amount, i.vendor_id\n"
            "FROM ap_invoices_all i\n"
            "JOIN ap_payment_schedules_all ps ON ps.invoice_id = i.invoice_id\n"
            "WHERE i.org_id = :org_id\n"
            "  AND ps.payment_status_flag = :payment_status\n"
            "ORDER BY ps.due_date"
        ),
        parameters=[
            ReportParam(name="org_id", label="Operating unit (org) ID", type="number"),
            ReportParam(name="payment_status", label="Payment status flag", type="string", default="N"),
        ],
    ),
    Template(
        id="ap_supplier_balances",
        module="AP",
        name="AP Supplier Balances",
        description=f"Invoice count and total amount per supplier in a date range. {REVIEW_NOTE}",
        sql=(
            "SELECT i.vendor_id, COUNT(*) AS invoice_count, SUM(i.invoice_amount) AS total_amount\n"
            "FROM ap_invoices_all i\n"
            "WHERE i.org_id = :org_id\n"
            "  AND i.invoice_date BETWEEN :date_from AND :date_to\n"
            "GROUP BY i.vendor_id\n"
            "ORDER BY total_amount DESC"
        ),
        parameters=[
            ReportParam(name="org_id", label="Operating unit (org) ID", type="number"),
            ReportParam(name="date_from", label="Invoice date from", type="date"),
            ReportParam(name="date_to", label="Invoice date to", type="date"),
        ],
    ),
    # ----------------------------- Receivables (AR) --------------------------
    Template(
        id="ar_aging_open_items",
        module="AR",
        name="AR Open Items (aging input)",
        description=f"Open receivable payment schedules with amount due remaining. {REVIEW_NOTE}",
        sql=(
            "SELECT ps.customer_id, ps.customer_trx_id, ps.trx_number, ps.trx_date,\n"
            "       ps.due_date, ps.amount_due_remaining\n"
            "FROM ar_payment_schedules_all ps\n"
            "WHERE ps.org_id = :org_id\n"
            "  AND ps.status = :status\n"
            "ORDER BY ps.due_date"
        ),
        parameters=[
            ReportParam(name="org_id", label="Operating unit (org) ID", type="number"),
            ReportParam(name="status", label="Schedule status", type="string", default="OP"),
        ],
    ),
    Template(
        id="ar_customer_invoices",
        module="AR",
        name="AR Customer Invoices",
        description=f"Customer transactions (invoices) within a date range. {REVIEW_NOTE}",
        sql=(
            "SELECT t.customer_trx_id, t.trx_number, t.trx_date, t.bill_to_customer_id,\n"
            "       t.invoice_currency_code\n"
            "FROM ra_customer_trx_all t\n"
            "WHERE t.org_id = :org_id\n"
            "  AND t.trx_date BETWEEN :date_from AND :date_to\n"
            "ORDER BY t.trx_date, t.trx_number"
        ),
        parameters=[
            ReportParam(name="org_id", label="Operating unit (org) ID", type="number"),
            ReportParam(name="date_from", label="Transaction date from", type="date"),
            ReportParam(name="date_to", label="Transaction date to", type="date"),
        ],
    ),
    # ----------------------------- Purchasing (PO) ---------------------------
    Template(
        id="po_open_orders",
        module="PO",
        name="PO Open Purchase Orders",
        description=f"Purchase order headers by authorization status. {REVIEW_NOTE}",
        sql=(
            "SELECT h.po_header_id, h.segment1 AS po_number, h.type_lookup_code,\n"
            "       h.authorization_status, h.vendor_id, h.creation_date\n"
            "FROM po_headers_all h\n"
            "WHERE h.org_id = :org_id\n"
            "  AND h.authorization_status = :authorization_status\n"
            "ORDER BY h.creation_date DESC"
        ),
        parameters=[
            ReportParam(name="org_id", label="Operating unit (org) ID", type="number"),
            ReportParam(
                name="authorization_status",
                label="Authorization status",
                type="string",
                default="APPROVED",
            ),
        ],
    ),
    Template(
        id="po_lines",
        module="PO",
        name="PO Lines (by PO number)",
        description=f"Line detail for a specific purchase order. {REVIEW_NOTE}",
        sql=(
            "SELECT h.segment1 AS po_number, l.line_num, l.item_id,\n"
            "       l.quantity, l.unit_price, l.line_type_id\n"
            "FROM po_headers_all h\n"
            "JOIN po_lines_all l ON l.po_header_id = h.po_header_id\n"
            "WHERE h.org_id = :org_id\n"
            "  AND h.segment1 = :po_number\n"
            "ORDER BY l.line_num"
        ),
        parameters=[
            ReportParam(name="org_id", label="Operating unit (org) ID", type="number"),
            ReportParam(name="po_number", label="PO number (segment1)", type="string"),
        ],
    ),
    Template(
        id="po_receipts",
        module="PO",
        name="PO Receipts",
        description=f"Receiving shipment lines for an inventory org in a date range. {REVIEW_NOTE}",
        sql=(
            "SELECT sh.shipment_header_id, sh.receipt_num, sh.shipment_num,\n"
            "       sl.line_num, sl.quantity_received, sl.item_id\n"
            "FROM rcv_shipment_headers sh\n"
            "JOIN rcv_shipment_lines sl ON sl.shipment_header_id = sh.shipment_header_id\n"
            "WHERE sl.to_organization_id = :organization_id\n"
            "  AND sh.creation_date BETWEEN :date_from AND :date_to\n"
            "ORDER BY sh.shipment_header_id, sl.line_num"
        ),
        parameters=[
            ReportParam(name="organization_id", label="Inventory organization ID", type="number"),
            ReportParam(name="date_from", label="Receipt date from", type="date"),
            ReportParam(name="date_to", label="Receipt date to", type="date"),
        ],
    ),
    # --------------------------- Order Management (OM) -----------------------
    Template(
        id="om_sales_orders",
        module="OM",
        name="OM Sales Orders",
        description=f"Sales order headers by flow status for an operating unit. {REVIEW_NOTE}",
        sql=(
            "SELECT h.header_id, h.order_number, h.ordered_date, h.flow_status_code,\n"
            "       h.sold_to_org_id, h.transactional_curr_code\n"
            "FROM oe_order_headers_all h\n"
            "WHERE h.org_id = :org_id\n"
            "  AND h.flow_status_code = :flow_status\n"
            "ORDER BY h.ordered_date DESC"
        ),
        parameters=[
            ReportParam(name="org_id", label="Operating unit (org) ID", type="number"),
            ReportParam(name="flow_status", label="Flow status code", type="string", default="BOOKED"),
        ],
    ),
    Template(
        id="om_order_lines",
        module="OM",
        name="OM Order Lines (by order number)",
        description=f"Line detail for a specific sales order. {REVIEW_NOTE}",
        sql=(
            "SELECT h.order_number, l.line_number, l.ordered_item, l.ordered_quantity,\n"
            "       l.unit_selling_price, l.flow_status_code\n"
            "FROM oe_order_headers_all h\n"
            "JOIN oe_order_lines_all l ON l.header_id = h.header_id\n"
            "WHERE h.org_id = :org_id\n"
            "  AND h.order_number = :order_number\n"
            "ORDER BY l.line_number"
        ),
        parameters=[
            ReportParam(name="org_id", label="Operating unit (org) ID", type="number"),
            ReportParam(name="order_number", label="Order number", type="number"),
        ],
    ),
]


def list_templates() -> List[Template]:
    """Return the full curated catalog (read-only)."""
    return list(_TEMPLATES)


def get_template(template_id: str) -> Optional[Template]:
    return next((t for t in _TEMPLATES if t.id == template_id), None)
