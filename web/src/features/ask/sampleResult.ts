import { ExecuteResult } from "@/lib/api/schemas";

// Sample result for previewing the executive Results design without a live DB.
// Category-level rows per customer so the drill-down has real sub-data: most
// customers break down by product category; a few have a single record (to show
// the "no further breakdown → pull live data" path).
export const SAMPLE_QUESTION = "Top customers by outstanding AR — FY26";

export const SAMPLE_SQL = `SELECT customer_name, product_category, invoice_count, outstanding_amount, days_overdue
FROM   ar_customer_category_summary
WHERE  fiscal_year = 2026
ORDER  BY outstanding_amount DESC`;

export const SAMPLE_RESULT: ExecuteResult = {
  columns: ["customer_name", "product_category", "invoice_count", "outstanding_amount", "days_overdue"],
  rows: [
    ["Meridian Stores", "Electronics", 8, 520000, 52],
    ["Meridian Stores", "Apparel", 6, 410200, 48],
    ["Meridian Stores", "Home", 4, 210000, 33],
    ["Northwind Foods", "Beverages", 6, 402500, 44],
    ["Northwind Foods", "Produce", 5, 320000, 29],
    ["Northwind Foods", "Frozen", 3, 200000, 51],
    ["Halcyon Retail", "Electronics", 7, 460800, 31],
    ["Halcyon Retail", "Apparel", 4, 275000, 22],
    ["Cedar & Pine", "Home", 5, 300100, 27],
    ["Cedar & Pine", "Apparel", 4, 240000, 19],
    ["Atlas Supply", "Hardware", 7, 431050, 22],
    ["Brightway Co", "Beverages", 6, 388900, 19],
    ["Crestline Group", "Electronics", 3, 174300, 41],
    ["Crestline Group", "Home", 2, 100000, 38],
    ["Dunmore Ltd", "Apparel", 4, 198450, 12],
    ["Evergreen LLC", "Produce", 3, 152000, 8],
    ["Foxtrot Inc", "Hardware", 2, 96750, 15],
  ],
  elapsed_seconds: 0.142,
  row_count: 17,
  truncated: false,
};
