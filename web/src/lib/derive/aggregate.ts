import { Agg } from "./sql";

// Fold a list of finite numbers by a known aggregation. Used by both KPI and
// chart derivation so a column's roll-up matches its SQL aggregation exactly.
//
// The roll-up across pre-aggregated GROUP BY rows is only exact for additive
// aggregates: SUM/COUNT roll up by summing, MIN by the min-of-mins, MAX by the
// max-of-maxes. AVG is NOT recoverable as a true weighted mean without the group
// counts, so we report the average of the per-group values (labelled honestly by
// the caller) rather than fabricate precision. Manual loops (no spread) so MIN/
// MAX stay safe and O(n) at tens of thousands of rows.
export function foldAgg(nums: number[], agg: Agg): number {
  if (nums.length === 0) return 0;
  switch (agg) {
    case "min": {
      let m = nums[0];
      for (let i = 1; i < nums.length; i++) if (nums[i] < m) m = nums[i];
      return m;
    }
    case "max": {
      let m = nums[0];
      for (let i = 1; i < nums.length; i++) if (nums[i] > m) m = nums[i];
      return m;
    }
    case "avg": {
      let s = 0;
      for (const n of nums) s += n;
      return s / nums.length;
    }
    case "sum":
    case "count":
    default: {
      let s = 0;
      for (const n of nums) s += n;
      return s;
    }
  }
}
