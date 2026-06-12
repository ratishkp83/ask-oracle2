# EBS Pack Contents — Self-Audit (pre-instance, knowledge-based)

> **Date:** 2026-06-12 · **Author:** Engineering (curator) · **Scope:** `src/core/ebs_packs.py`
> **Purpose:** an honest, confidence-flagged review of the curated EBS R12.2 names *before* a
> real-instance validation. This is **not** a substitute for the live check — it tells the
> reviewer which entries are rock-solid vs. which to verify first. The authoritative close is
> `scripts/ebs_pack_validate.py` against a real EBS instance (ITM-012).

**Confidence key:** **H** = standard, well-known R12.2 object I'm highly confident of ·
**M** = correct to the best of my knowledge but worth a deliberate column check ·
**(version note)** = depends on the EBS release/footprint.

## General caveats (apply to every pack)
- Targets **standard R12 / 12.2**. 11i differs (e.g. suppliers were `PO_VENDORS` /
  `PO_VENDOR_SITES_ALL` before R12's `AP_SUPPLIERS` / `AP_SUPPLIER_SITES_ALL`).
- `_ALL` tables are **multi-org** (`org_id`); single-org views (without `_ALL`) also exist.
- Apps access base tables via **`APPS` synonyms**; the base tables are owned by `AP`, `GL`, `AR`,
  `PO`, `ONT`, `INV`, `HZ`, `WSH`, `RCV`, … The validator looks up by table name across owners.
- **Customizations/localizations** can add or (rarely) rename columns — only a live check catches these.

## GL — General Ledger
| Object | Conf | Notes |
|---|---|---|
| `GL_LEDGERS` (ledger_id, name, currency_code) | H | R12 replaced `GL_SETS_OF_BOOKS` (11i). |
| `GL_BALANCES` (ledger_id, code_combination_id, period_name, currency_code, period_net_dr, period_net_cr) | H | Standard balance columns. |
| `GL_CODE_COMBINATIONS` (code_combination_id, segment1–3…) | H | Segments are flexfield-defined (count varies by COA). |
| `GL_JE_BATCHES` / `GL_JE_HEADERS` / `GL_JE_LINES` | H | `je_category`, `je_source`, `entered_dr/cr`, `accounted_dr/cr` standard. |

## AP — Accounts Payable
| Object | Conf | Notes |
|---|---|---|
| `AP_INVOICES_ALL` (invoice_id, vendor_id, invoice_num, invoice_amount, invoice_date, org_id) | H | Core AP header. |
| `AP_INVOICE_LINES_ALL` (invoice_id, line_number, amount) | H | R12 lines architecture; `line_number` + `amount`. |
| `AP_PAYMENT_SCHEDULES_ALL` (invoice_id, payment_num, due_date, gross_amount, amount_remaining) | H | Open-AP via `amount_remaining`. |
| `AP_CHECKS_ALL` (check_id, vendor_id, amount, check_date) | H | Payments. |
| `AP_SUPPLIERS` (vendor_id, vendor_name, segment1) | H *(R12)* | `segment1` = supplier number. |
| `AP_SUPPLIER_SITES_ALL` (vendor_site_id, vendor_id, org_id) | H *(R12)* | |

## AR — Accounts Receivable
| Object | Conf | Notes |
|---|---|---|
| `RA_CUSTOMER_TRX_ALL` (customer_trx_id, trx_number, trx_date, bill_to_customer_id, org_id) | H | AR transactions (invoices/CM/DM). |
| `RA_CUSTOMER_TRX_LINES_ALL` (customer_trx_id, customer_trx_line_id, line_type, extended_amount) | H | `line_type` ∈ LINE/TAX/FREIGHT. |
| `AR_PAYMENT_SCHEDULES_ALL` (customer_trx_id, payment_schedule_id, due_date, amount_due_remaining, status, class) | H | Aging/open-AR. |
| `AR_CASH_RECEIPTS_ALL` (cash_receipt_id, amount, receipt_date, pay_from_customer) | **M** | `pay_from_customer` (customer who paid) — confirm exact column. |
| `HZ_CUST_ACCOUNTS` (cust_account_id, account_number, party_id) | H | TCA customer account. |
| `HZ_PARTIES` (party_id, party_name, party_number) | H | TCA party. |

## PO — Purchasing
| Object | Conf | Notes |
|---|---|---|
| `PO_HEADERS_ALL` (po_header_id, segment1, vendor_id, type_lookup_code, org_id) | H | `segment1` = PO number. |
| `PO_LINES_ALL` (po_line_id, po_header_id, line_num, item_id, quantity, unit_price) | H | |
| `PO_LINE_LOCATIONS_ALL` (line_location_id, po_line_id, quantity, quantity_received, quantity_billed) | H | Shipments/schedules. |
| `PO_DISTRIBUTIONS_ALL` (po_distribution_id, po_line_id, code_combination_id) | H | |
| `RCV_SHIPMENT_HEADERS` (shipment_header_id, receipt_num, vendor_id) | H | |
| `RCV_SHIPMENT_LINES` (shipment_line_id, shipment_header_id, po_line_id, quantity_received) | H | |

## OM — Order Management
| Object | Conf | Notes |
|---|---|---|
| `OE_ORDER_HEADERS_ALL` (header_id, order_number, sold_to_org_id, order_type_id, org_id) | H | `sold_to_org_id` = customer account. |
| `OE_ORDER_LINES_ALL` (line_id, header_id, line_number, inventory_item_id, ordered_quantity, shipped_quantity, unit_selling_price) | H | |
| `OE_TRANSACTION_TYPES_ALL` (transaction_type_id, name) | H | Order/line type defs. |
| `WSH_DELIVERY_DETAILS` (delivery_detail_id, source_header_id, source_line_id, shipped_quantity) | **M** | `source_line_id` → `OE_ORDER_LINES_ALL.line_id`; confirm shipped-qty column. |

## Summary
- **Tables:** all are standard R12.2 objects — **High** confidence on every table name.
- **Columns to verify first** when an instance is available: `AR_CASH_RECEIPTS_ALL.pay_from_customer`,
  `WSH_DELIVERY_DETAILS` shipped-quantity column. Everything else is standard.
- **Action:** run `scripts/ebs_pack_validate.py` against a real EBS 12.2 instance; remediate any
  `[MISSING …]` and re-run; record the output as the ITM-012 evidence.
