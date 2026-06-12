"""Curated EBS metadata packs (Phase 7, charter D-B/D-C).

Per-module **metadata** that makes NL→SQL EBS-aware: standard E-Business Suite
(R12 / 12.2) table descriptions, key columns, canonical join paths, and a
business-term **glossary** (e.g. "invoice" → ``AP_INVOICES_ALL``). These are
curated *names and descriptions* — **never row data** — so they compose with the
existing external-prompt redaction (`src/core/llm/redaction.py`) and are
review-before-run starting points like the template catalog (`templates.py`),
whose tables they describe.

Read-only and static this phase (D-C). Real-EBS validation of contents remains
ITM-012 (table/column names vary by version and customization).
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field

from src.core.templates import Module  # Literal["GL","AP","AR","PO","OM"]


class GlossaryTerm(BaseModel):
    term: str
    table: str
    column: Optional[str] = None
    note: Optional[str] = None


class TableNote(BaseModel):
    table: str
    description: str
    key_columns: List[str] = Field(default_factory=list)
    joins: List[str] = Field(default_factory=list)  # "A.col -> B.col" hints


class EbsPack(BaseModel):
    module: Module
    name: str
    tables: List[TableNote] = Field(default_factory=list)
    glossary: List[GlossaryTerm] = Field(default_factory=list)


_PACKS: List[EbsPack] = [
    # ------------------------------ General Ledger ------------------------------
    EbsPack(
        module="GL",
        name="General Ledger",
        tables=[
            TableNote(table="GL_LEDGERS", description="Ledger (set of books) definitions — name, currency, calendar.",
                      key_columns=["ledger_id", "name", "currency_code"]),
            TableNote(table="GL_BALANCES", description="Account balances by code combination and accounting period (period_net_dr/cr).",
                      key_columns=["ledger_id", "code_combination_id", "period_name", "currency_code", "period_net_dr", "period_net_cr"],
                      joins=["GL_BALANCES.ledger_id -> GL_LEDGERS.ledger_id",
                             "GL_BALANCES.code_combination_id -> GL_CODE_COMBINATIONS.code_combination_id"]),
            TableNote(table="GL_CODE_COMBINATIONS", description="Accounting flexfield (chart of accounts) code combinations — one row per account.",
                      key_columns=["code_combination_id", "segment1", "segment2", "segment3"]),
            TableNote(table="GL_JE_BATCHES", description="Journal entry batches — a group of journals for a period.",
                      key_columns=["je_batch_id", "name", "status"]),
            TableNote(table="GL_JE_HEADERS", description="Journal entry headers — one per journal (ledger, period, category, source).",
                      key_columns=["je_header_id", "ledger_id", "period_name", "je_category", "je_source", "je_batch_id"],
                      joins=["GL_JE_HEADERS.je_batch_id -> GL_JE_BATCHES.je_batch_id",
                             "GL_JE_LINES.je_header_id -> GL_JE_HEADERS.je_header_id"]),
            TableNote(table="GL_JE_LINES", description="Journal entry lines — entered/accounted debit and credit per account.",
                      key_columns=["je_header_id", "je_line_num", "code_combination_id", "entered_dr", "entered_cr", "accounted_dr", "accounted_cr"],
                      joins=["GL_JE_LINES.code_combination_id -> GL_CODE_COMBINATIONS.code_combination_id"]),
        ],
        glossary=[
            GlossaryTerm(term="ledger", table="GL_LEDGERS", note="also 'set of books'"),
            GlossaryTerm(term="set of books", table="GL_LEDGERS"),
            GlossaryTerm(term="account balance", table="GL_BALANCES"),
            GlossaryTerm(term="trial balance", table="GL_BALANCES", note="net dr/cr per account+period"),
            GlossaryTerm(term="accounting period", table="GL_BALANCES", column="period_name"),
            GlossaryTerm(term="journal", table="GL_JE_HEADERS"),
            GlossaryTerm(term="journal entry", table="GL_JE_HEADERS"),
            GlossaryTerm(term="journal line", table="GL_JE_LINES"),
            GlossaryTerm(term="chart of accounts", table="GL_CODE_COMBINATIONS"),
            GlossaryTerm(term="account code", table="GL_CODE_COMBINATIONS", note="code combination / flexfield"),
        ],
    ),
    # ----------------------------- Accounts Payable -----------------------------
    EbsPack(
        module="AP",
        name="Accounts Payable",
        tables=[
            TableNote(table="AP_INVOICES_ALL", description="Supplier (payables) invoices — header level (amount, supplier, dates, org).",
                      key_columns=["invoice_id", "vendor_id", "invoice_num", "invoice_amount", "invoice_date", "org_id"],
                      joins=["AP_INVOICE_LINES_ALL.invoice_id -> AP_INVOICES_ALL.invoice_id",
                             "AP_PAYMENT_SCHEDULES_ALL.invoice_id -> AP_INVOICES_ALL.invoice_id",
                             "AP_INVOICES_ALL.vendor_id -> AP_SUPPLIERS.vendor_id"]),
            TableNote(table="AP_INVOICE_LINES_ALL", description="AP invoice line detail (amount, distributions, item).",
                      key_columns=["invoice_id", "line_number", "amount"]),
            TableNote(table="AP_PAYMENT_SCHEDULES_ALL", description="AP invoice payment schedules — due dates and open/closed amounts.",
                      key_columns=["invoice_id", "payment_num", "due_date", "gross_amount", "amount_remaining"]),
            TableNote(table="AP_CHECKS_ALL", description="AP payments (check/EFT) made to suppliers.",
                      key_columns=["check_id", "vendor_id", "amount", "check_date"],
                      joins=["AP_CHECKS_ALL.vendor_id -> AP_SUPPLIERS.vendor_id"]),
            TableNote(table="AP_SUPPLIERS", description="Suppliers (vendors) — R12 supplier master.",
                      key_columns=["vendor_id", "vendor_name", "segment1"],
                      joins=["AP_SUPPLIER_SITES_ALL.vendor_id -> AP_SUPPLIERS.vendor_id"]),
            TableNote(table="AP_SUPPLIER_SITES_ALL", description="Supplier sites — addresses and pay sites per supplier and org.",
                      key_columns=["vendor_site_id", "vendor_id", "org_id"]),
        ],
        glossary=[
            GlossaryTerm(term="invoice", table="AP_INVOICES_ALL", note="payables/supplier invoice"),
            GlossaryTerm(term="supplier invoice", table="AP_INVOICES_ALL"),
            GlossaryTerm(term="payables invoice", table="AP_INVOICES_ALL"),
            GlossaryTerm(term="invoice line", table="AP_INVOICE_LINES_ALL"),
            GlossaryTerm(term="payment schedule", table="AP_PAYMENT_SCHEDULES_ALL"),
            GlossaryTerm(term="due date", table="AP_PAYMENT_SCHEDULES_ALL", column="due_date"),
            GlossaryTerm(term="open payables", table="AP_PAYMENT_SCHEDULES_ALL", note="amount_remaining > 0"),
            GlossaryTerm(term="payment", table="AP_CHECKS_ALL"),
            GlossaryTerm(term="check", table="AP_CHECKS_ALL"),
            GlossaryTerm(term="supplier", table="AP_SUPPLIERS"),
            GlossaryTerm(term="vendor", table="AP_SUPPLIERS"),
        ],
    ),
    # --------------------------- Accounts Receivable ----------------------------
    EbsPack(
        module="AR",
        name="Accounts Receivable",
        tables=[
            TableNote(table="RA_CUSTOMER_TRX_ALL", description="AR transactions — customer invoices, credit/debit memos (header).",
                      key_columns=["customer_trx_id", "trx_number", "trx_date", "bill_to_customer_id", "org_id"],
                      joins=["RA_CUSTOMER_TRX_LINES_ALL.customer_trx_id -> RA_CUSTOMER_TRX_ALL.customer_trx_id",
                             "AR_PAYMENT_SCHEDULES_ALL.customer_trx_id -> RA_CUSTOMER_TRX_ALL.customer_trx_id",
                             "RA_CUSTOMER_TRX_ALL.bill_to_customer_id -> HZ_CUST_ACCOUNTS.cust_account_id"]),
            TableNote(table="RA_CUSTOMER_TRX_LINES_ALL", description="AR transaction line detail (line/tax/freight amounts).",
                      key_columns=["customer_trx_id", "customer_trx_line_id", "line_type", "extended_amount"]),
            TableNote(table="AR_PAYMENT_SCHEDULES_ALL", description="AR payment schedules — invoice due dates and amount_due_remaining (aging / open AR).",
                      key_columns=["customer_trx_id", "payment_schedule_id", "due_date", "amount_due_remaining", "status", "class"]),
            TableNote(table="AR_CASH_RECEIPTS_ALL", description="AR cash receipts — customer payments.",
                      key_columns=["cash_receipt_id", "amount", "receipt_date", "pay_from_customer"]),
            TableNote(table="HZ_CUST_ACCOUNTS", description="Customer accounts (TCA) — links a party to a customer account.",
                      key_columns=["cust_account_id", "account_number", "party_id"],
                      joins=["HZ_CUST_ACCOUNTS.party_id -> HZ_PARTIES.party_id"]),
            TableNote(table="HZ_PARTIES", description="Trading Community parties — customer/party names and details.",
                      key_columns=["party_id", "party_name", "party_number"]),
        ],
        glossary=[
            GlossaryTerm(term="customer invoice", table="RA_CUSTOMER_TRX_ALL"),
            GlossaryTerm(term="receivables transaction", table="RA_CUSTOMER_TRX_ALL"),
            GlossaryTerm(term="AR invoice", table="RA_CUSTOMER_TRX_ALL"),
            GlossaryTerm(term="invoice line", table="RA_CUSTOMER_TRX_LINES_ALL", note="AR context"),
            GlossaryTerm(term="open receivables", table="AR_PAYMENT_SCHEDULES_ALL", note="amount_due_remaining > 0"),
            GlossaryTerm(term="aging", table="AR_PAYMENT_SCHEDULES_ALL"),
            GlossaryTerm(term="amount due", table="AR_PAYMENT_SCHEDULES_ALL", column="amount_due_remaining"),
            GlossaryTerm(term="receipt", table="AR_CASH_RECEIPTS_ALL"),
            GlossaryTerm(term="cash receipt", table="AR_CASH_RECEIPTS_ALL"),
            GlossaryTerm(term="customer", table="HZ_CUST_ACCOUNTS"),
            GlossaryTerm(term="customer name", table="HZ_PARTIES", column="party_name"),
        ],
    ),
    # -------------------------------- Purchasing --------------------------------
    EbsPack(
        module="PO",
        name="Purchasing",
        tables=[
            TableNote(table="PO_HEADERS_ALL", description="Purchase order headers (PO number, supplier, type, status, org).",
                      key_columns=["po_header_id", "segment1", "vendor_id", "type_lookup_code", "org_id"],
                      joins=["PO_LINES_ALL.po_header_id -> PO_HEADERS_ALL.po_header_id",
                             "PO_HEADERS_ALL.vendor_id -> AP_SUPPLIERS.vendor_id"]),
            TableNote(table="PO_LINES_ALL", description="PO line detail (item, quantity, unit price).",
                      key_columns=["po_line_id", "po_header_id", "line_num", "item_id", "quantity", "unit_price"],
                      joins=["PO_LINE_LOCATIONS_ALL.po_line_id -> PO_LINES_ALL.po_line_id"]),
            TableNote(table="PO_LINE_LOCATIONS_ALL", description="PO shipments/schedules — quantity ordered/received/billed per ship-to.",
                      key_columns=["line_location_id", "po_line_id", "quantity", "quantity_received", "quantity_billed"]),
            TableNote(table="PO_DISTRIBUTIONS_ALL", description="PO distributions — accounting/quantity distribution per line.",
                      key_columns=["po_distribution_id", "po_line_id", "code_combination_id"]),
            TableNote(table="RCV_SHIPMENT_HEADERS", description="Receiving shipment headers (receipt number, supplier).",
                      key_columns=["shipment_header_id", "receipt_num", "vendor_id"],
                      joins=["RCV_SHIPMENT_LINES.shipment_header_id -> RCV_SHIPMENT_HEADERS.shipment_header_id"]),
            TableNote(table="RCV_SHIPMENT_LINES", description="Receiving shipment lines — received quantity per PO line.",
                      key_columns=["shipment_line_id", "shipment_header_id", "po_line_id", "quantity_received"]),
        ],
        glossary=[
            GlossaryTerm(term="purchase order", table="PO_HEADERS_ALL"),
            GlossaryTerm(term="PO", table="PO_HEADERS_ALL"),
            GlossaryTerm(term="PO line", table="PO_LINES_ALL"),
            GlossaryTerm(term="PO shipment", table="PO_LINE_LOCATIONS_ALL", note="schedule / received qty"),
            GlossaryTerm(term="received quantity", table="PO_LINE_LOCATIONS_ALL", column="quantity_received"),
            GlossaryTerm(term="receipt", table="RCV_SHIPMENT_HEADERS", note="receiving"),
            GlossaryTerm(term="receipt line", table="RCV_SHIPMENT_LINES"),
            GlossaryTerm(term="supplier", table="AP_SUPPLIERS", note="shared with AP"),
        ],
    ),
    # ----------------------------- Order Management -----------------------------
    EbsPack(
        module="OM",
        name="Order Management",
        tables=[
            TableNote(table="OE_ORDER_HEADERS_ALL", description="Sales order headers (order number, customer, order type, org).",
                      key_columns=["header_id", "order_number", "sold_to_org_id", "order_type_id", "org_id"],
                      joins=["OE_ORDER_LINES_ALL.header_id -> OE_ORDER_HEADERS_ALL.header_id",
                             "OE_ORDER_HEADERS_ALL.order_type_id -> OE_TRANSACTION_TYPES_ALL.transaction_type_id"]),
            TableNote(table="OE_ORDER_LINES_ALL", description="Sales order lines (item, ordered/shipped quantity, selling price).",
                      key_columns=["line_id", "header_id", "line_number", "inventory_item_id", "ordered_quantity", "shipped_quantity", "unit_selling_price"],
                      joins=["WSH_DELIVERY_DETAILS.source_line_id -> OE_ORDER_LINES_ALL.line_id"]),
            TableNote(table="OE_TRANSACTION_TYPES_ALL", description="Order/line transaction (order) type definitions.",
                      key_columns=["transaction_type_id", "name"]),
            TableNote(table="WSH_DELIVERY_DETAILS", description="Shipping delivery details — what shipped for an order line.",
                      key_columns=["delivery_detail_id", "source_header_id", "source_line_id", "shipped_quantity"]),
        ],
        glossary=[
            GlossaryTerm(term="sales order", table="OE_ORDER_HEADERS_ALL"),
            GlossaryTerm(term="order", table="OE_ORDER_HEADERS_ALL", note="sales/OM order"),
            GlossaryTerm(term="order line", table="OE_ORDER_LINES_ALL"),
            GlossaryTerm(term="sales order line", table="OE_ORDER_LINES_ALL"),
            GlossaryTerm(term="order type", table="OE_TRANSACTION_TYPES_ALL"),
            GlossaryTerm(term="shipment", table="WSH_DELIVERY_DETAILS", note="delivery / shipped qty"),
            GlossaryTerm(term="shipped quantity", table="OE_ORDER_LINES_ALL", column="shipped_quantity"),
        ],
    ),
]


# --------------------------------------------------------------------------- #
# Accessors
# --------------------------------------------------------------------------- #
def list_packs() -> List[EbsPack]:
    """All curated EBS packs (one per module family)."""
    return list(_PACKS)


def get_pack(module: str) -> Optional[EbsPack]:
    """The pack for ``module`` (case-insensitive), or ``None``."""
    m = (module or "").upper()
    for p in _PACKS:
        if p.module == m:
            return p
    return None


def build_ebs_context(modules: List[str]) -> str:
    """Curated EBS metadata as prompt context for the selected modules.

    Names and descriptions only — **no row data** — so the result always passes
    ``assert_no_values`` and composes with the schema-name context. Returns ``""``
    when no module is selected (the opt-in default).
    """
    wanted = {(m or "").upper() for m in (modules or [])}
    packs = [p for p in _PACKS if p.module in wanted]
    if not packs:
        return ""
    lines: List[str] = ["EBS Metadata (curated — table/column names + descriptions only):"]
    for p in packs:
        lines.append(f"Module {p.module} — {p.name}:")
        for t in p.tables:
            keys = f" [key cols: {', '.join(t.key_columns)}]" if t.key_columns else ""
            joins = f" joins: {'; '.join(t.joins)}" if t.joins else ""
            lines.append(f"- {t.table}: {t.description}{keys}{joins}")
        if p.glossary:
            lines.append(f"Glossary ({p.module}):")
            for g in p.glossary:
                target = g.table + (f".{g.column}" if g.column else "")
                note = f" — {g.note}" if g.note else ""
                lines.append(f"- {g.term} -> {target}{note}")
    return "\n".join(lines)
