import { ExecuteResult } from "@/lib/api/schemas";

// Sample result for previewing the executive Results design without a live DB.
//
// This is an AGGREGATED, multi-dimensional result (GROUP BY region, customer)
// chosen specifically to exercise the SQL-AWARE intelligence (B5b-1):
//   • REGION and CUSTOMER_NAME are GROUP BY keys      → dimensions
//   • SUM(outstanding_amount)                         → measure, summed
//   • COUNT(invoice_id)                               → measure, summed (grand count)
//   • AVG(days_overdue)                               → measure, averaged ("Average across N groups")
// The KPIs therefore roll up by the *exact* SQL aggregation (not name guesses),
// the driver chart rolls outstanding up by REGION, and clicking a region cascades
// the whole view to that region's customer breakdown + filtered detail. LATAM has
// a single customer, so drilling it shows the "no further breakdown → pull live
// data" path.
export const SAMPLE_QUESTION = "Outstanding AR by region and customer — FY26";

export const SAMPLE_SQL = `SELECT region,
       customer_name,
       SUM(outstanding_amount) AS outstanding,
       COUNT(invoice_id)       AS invoices,
       AVG(days_overdue)       AS avg_days_overdue
FROM   ar_open_items
WHERE  fiscal_year = 2026
GROUP  BY region, customer_name
ORDER  BY outstanding DESC`;

export const SAMPLE_RESULT: ExecuteResult = {
  columns: ["region", "customer_name", "outstanding", "invoices", "avg_days_overdue"],
  rows: [
    ["North America", "Meridian Stores", 1140200, 18, 47],
    ["EMEA", "Northwind Foods", 922500, 14, 41],
    ["North America", "Halcyon Retail", 735800, 11, 29],
    ["EMEA", "Cedar & Pine", 540100, 9, 24],
    ["North America", "Atlas Supply", 431050, 7, 22],
    ["North America", "Brightway Co", 388900, 6, 19],
    ["APAC", "Crestline Group", 274300, 5, 39],
    ["EMEA", "Dunmore Ltd", 198450, 4, 12],
    ["APAC", "Evergreen LLC", 152000, 3, 8],
    ["LATAM", "Foxtrot Inc", 96750, 2, 15],
  ],
  elapsed_seconds: 0.137,
  row_count: 10,
  truncated: false,
};
