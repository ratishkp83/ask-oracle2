import { ExecuteResult } from "@/lib/api/schemas";

// Sample result for previewing the executive Results design without a live DB.
// Clearly a sample — used by the "See a sample result" affordance and as an
// onboarding reference until the live nl2sql→execute flow (B5b) is wired.
export const SAMPLE_QUESTION = "Top customers by outstanding AR — FY26";

export const SAMPLE_SQL = `SELECT customer_name, invoice_count, outstanding_amount, days_overdue
FROM   ar_customer_summary
WHERE  fiscal_year = 2026
ORDER  BY outstanding_amount DESC`;

export const SAMPLE_RESULT: ExecuteResult = {
  columns: ["customer_name", "invoice_count", "outstanding_amount", "days_overdue"],
  rows: [
    ["Meridian Stores", 18, 1140200, 52],
    ["Northwind Foods", 14, 922500, 48],
    ["Halcyon Retail", 11, 735800, 31],
    ["Cedar & Pine", 9, 540100, 27],
    ["Atlas Supply", 7, 431050, 22],
    ["Brightway Co", 6, 388900, 19],
    ["Crestline Group", 5, 274300, 41],
    ["Dunmore Ltd", 4, 198450, 12],
    ["Evergreen LLC", 3, 152000, 8],
    ["Foxtrot Inc", 2, 96750, 15],
    ["Granite Partners", 2, 73200, 5],
    ["Harbor Trading", 1, 41900, 3],
  ],
  elapsed_seconds: 0.142,
  row_count: 12,
  truncated: false,
};
