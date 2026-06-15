import { describe, expect, it } from "vitest";
import { buildAutoLookups, deriveBindColumns } from "./paramLookup";
import type { SchemaRecord } from "@/lib/api/schemas";

const SCHEMA: SchemaRecord = {
  id: "s1",
  name: "AOR_DEMO",
  source: "introspection",
  profile_id: null,
  table_count: 2,
  created_at: "x",
  updated_at: "x",
  definition: {
    tables: {
      EMPLOYEES: [
        { column_name: "EMPLOYEE_ID", is_primary_key: true, is_foreign_key: false },
        { column_name: "SALARY", is_primary_key: false, is_foreign_key: false },
        {
          column_name: "DEPARTMENT_ID",
          is_primary_key: false,
          is_foreign_key: true,
          references_table: "DEPARTMENTS",
          references_column: "DEPARTMENT_ID",
        },
      ],
      DEPARTMENTS: [
        { column_name: "DEPARTMENT_ID", is_primary_key: true, is_foreign_key: false },
        { column_name: "DEPARTMENT_NAME", is_primary_key: false, is_foreign_key: false },
      ],
    },
    relationships: [],
  },
};

describe("deriveBindColumns", () => {
  it("maps an equality predicate (qualifier stripped, upper-cased)", () => {
    expect(deriveBindColumns("SELECT * FROM employees e WHERE e.department_id = :dept_id")).toEqual({
      dept_id: "DEPARTMENT_ID",
    });
  });

  it("handles IN, BETWEEN, and bind-on-the-left", () => {
    expect(deriveBindColumns("WHERE org_id IN (:org)")).toEqual({ org: "ORG_ID" });
    expect(deriveBindColumns("WHERE created BETWEEN :from AND :to")).toEqual({ from: "CREATED", to: "CREATED" });
    expect(deriveBindColumns("WHERE :code = status_code")).toEqual({ code: "STATUS_CODE" });
  });
});

describe("buildAutoLookups", () => {
  it("derives a value-picker SELECT when the bind's column is a foreign key", () => {
    const out = buildAutoLookups("SELECT * FROM employees WHERE department_id = :dept_id", SCHEMA);
    expect(out).toEqual({
      dept_id: "SELECT DEPARTMENT_ID, DEPARTMENT_NAME FROM DEPARTMENTS ORDER BY DEPARTMENT_NAME",
    });
  });

  it("derives nothing for a non-FK column or when no schema is active", () => {
    expect(buildAutoLookups("SELECT * FROM employees WHERE salary > :min", SCHEMA)).toEqual({});
    expect(buildAutoLookups("SELECT * FROM employees WHERE department_id = :dept_id", undefined)).toEqual({});
  });
});
