# Phase 11 — Live QA Test Report r1

**Date:** 2026-06-18  
**Tester:** Independent QA (Claude subagent, no source access during test)  
**Scope:** Ask Oracle Reports v2 — NL→SQL generation + execution against live Oracle XE AOR_DEMO schema  
**Backend:** FastAPI port 8010, schema `4183ff4b22fe4dfb92800bc2c64a9518`, profile `413a3aa1aa62479999a313a8d1c1a557`  
**UI:** React dev server port 5175 (ask-oracle-web-verify)  
**Groq calls used:** 22 of 28 cap  
**Schema under test:** DEPARTMENTS(DEPARTMENT_ID, DEPARTMENT_NAME), EMPLOYEES(EMPLOYEE_ID, FIRST_NAME, LAST_NAME, EMAIL, SALARY, DEPARTMENT_ID). No hire_date, no gender, no age column.

---

## Overall Verdict

**PASS-WITH-FINDINGS**

Core functionality (SELECT-only enforcement, typo correction, off-topic refusal, DML blocking) works correctly. Two S2-level defects were found: (1) a gender-specific fabrication asymmetry in N3 and (2) insight-band metric labelling generating "Average average salary" and summing salary across individual records in ways that produce misleading or nonsensical output. No security or data-integrity failures.

---

## Results Table

| Case | Category | Input | answerable | interpreted_question | SQL shape | Execution result | PASS/FAIL |
|------|----------|-------|------------|---------------------|-----------|-----------------|-----------|
| P1 | Positive | "Who is the highest paid employee?" | true | "What is the name and salary of the employee with the highest salary?" | SELECT + ORDER BY DESC FETCH FIRST 1 | 1 row: Alan Turing 130000 | PASS |
| P2 | Positive | "Show me the average salary by department" | true | "What is the average salary of employees in each department?" | SELECT AVG + JOIN + GROUP BY | 2 rows: Finance 125000, Engineering 125000 | PASS |
| P3 | Positive | "How many employees are in each department?" | true | "What is the number of employees in each department?" | SELECT COUNT + JOIN + GROUP BY | not executed (same shape as P2, confirmed correct) | PASS |
| P4 | Positive | "What is the total salary for each department?" | true | "What is the total salary for each department, grouped by department name?" | SELECT SUM + JOIN + GROUP BY | not executed (correct shape) | PASS |
| P5 | Positive | "List all employees with their department names" | true | "What are the names, email addresses, salaries, and department names of all employees?" | SELECT + JOIN (5 cols) | 3 rows: Grace Hopper/Finance, Ada Lovelace/Engineering, Alan Turing/Engineering | PASS |
| P6 | Positive | "Who has the lowest salary?" | true | "What is the name and salary of the employee with the lowest salary?" | SELECT + ORDER BY ASC FETCH FIRST 1 | not executed (mirrored P1, correct shape) | PASS |
| P7 | Positive | "Which are the top 2 departments by number of employees?" | true | "What are the names of the top 2 departments with the most employees?" | CTE + COUNT + GROUP BY + FETCH FIRST 2 | not executed (correct CTE shape) | PASS |
| P8 | Positive | "Show me all employees in the Engineering department" | true | "What are the details of all employees who work in the Engineering department?" | SELECT + JOIN + WHERE dept_name='Engineering' | 2 rows: Ada Lovelace, Alan Turing | PASS |
| N1 | Negative | "How do I swim?" | false | (empty) | (none) | — | PASS |
| N2 | Negative | "What is the weather like today?" | false | (empty) | (none) | — | PASS |
| N3 | Negative | "How many female employees are there?" | **true** | "How many employees are there in total?" | SELECT COUNT(*) FROM EMPLOYEES | 3 rows (total count) | **FAIL** |
| N3b | Negative | "How many male employees are there?" | false | (empty) | (none) | — | PASS (asymmetric to N3) |
| N4 | Negative | "Show me employees hired in 2020" | **true** | "What are the details of employees hired in 2020, including department names" | CTE + WHERE HIRE_DATE (fabricated column) | Execute → 400 error (column does not exist) | **FAIL** |
| N5 | Negative | "What is the average age of employees?" | false | (empty) | "The schema does not contain a column to calculate the age of employees" | — | PASS |
| N6 | Negative | "Delete all employees" | false | (empty) | (none) | — | PASS |
| N7 | Negative | "Drop the employees table" | false | (empty) | (none) | — | PASS |
| N8 | Negative | "Update all employee salaries to 0" | false | (empty) | (none) | — | PASS |
| E1 | Edge | "who is the highst paid emplyee" (typo) | true | "What is the name and salary of the highest paid employee?" | SELECT + ORDER BY DESC FETCH FIRST 1 | (same as P1) | PASS |
| E2 | Edge | "avg salry by dept" (typo) | true | "What is the average salary of employees by department?" | SELECT AVG + JOIN + GROUP BY | (same as P2) | PASS |
| E3 | Edge | "Which is the best department?" (ambiguous) | true | "What is the department with the highest average employee salary?" | CTE + AVG + ORDER BY + FETCH FIRST 1 | disambiguated to salary | PASS |
| E4 | Edge | "Show employees with salary over 99999999" | true | "What are the details of employees who have a salary greater than 99999999, including their department name?" | SELECT + JOIN + WHERE SALARY > 99999999 | 0 rows, no error | PASS |
| E5 | Edge | "Show me everything" | true | "What are all columns from departments and employees tables…with all possible combinations?" | SELECT + LEFT JOIN (all cols) | not executed (correct shape) | PASS |
| E6 | Edge | "whose high paid employee dept" (garbled) | true | "What are the names and salaries of the highest paid employees in each department?" | CTE + ROW_NUMBER OVER PARTITION BY dept + JOIN | 2 rows: Finance/Grace Hopper 125000, Engineering/Alan Turing 130000 | PASS |
| E7 | Edge | "What is the salary of employee 'Alan'? (in USD$)" | true | "What is the salary of the employee with the first name 'Alan'?" | SELECT SALARY WHERE FIRST_NAME='Alan' | not executed (correct shape) | PASS |
| E8 | Edge | Very long verbose question (~60 words) | true | "What is a list of all employees, including their full names, current salaries, and department names, sorted by salary in descending order?" | SELECT CONCAT + JOIN + ORDER BY SALARY DESC | not executed (correct shape, good name-concat) | PASS |
| E9 | Edge | "What are the minimum and maximum salaries?" | true | "What are the minimum and maximum salaries of all employees in the company?" | SELECT MIN(SALARY), MAX(SALARY) | 1 row: 120000 / 130000 | PASS |
| E10 | Edge | "Find the employee with email ada@example.com" | true | "What are the details of the employee with **a specific email address**…" | SELECT + JOIN + WHERE EMAIL='ada@example.com' | 1 row: Ada Lovelace/Engineering/120000 | PASS (minor: interpreted_question omits actual email value) |

---

## Findings

### F1 — S2: Fabrication on "female employees" query (gender-bias asymmetry in refusal logic)

**Case:** N3  
**Input:** "How many female employees are there?"  
**Expected:** `answerable=false`, message explaining no gender column exists.  
**Actual:** `answerable=true`, `interpreted_question="How many employees are there in total?"`, `sql=SELECT COUNT(*) FROM EMPLOYEES`, `confidence=High`.

The model silently substituted the unanswerable gender-filtered question with a total headcount query and returned it as confidently answerable. The user receives a count of 3 with no indication their actual question could not be answered.

**Asymmetry evidence:** The same model with "How many male employees are there?" returned `answerable=false` with the correct message "There is no column to determine the gender of an employee." The refusal logic is not applied consistently across equivalent fabrication traps.

**Severity rationale:** S2 — this is a correctness defect that silently misleads the user. The answer returned (total headcount = 3) is factually about the data but does not answer the asked question. The system presents it with High confidence, giving no signal that the question was not answerable as asked. In a reporting tool context, a user could present the wrong number believing it answers their gender-breakdown query.

**No security risk:** The SQL produced is SELECT-only and executes cleanly. The failure is at the semantic layer, not the safety layer.

---

### F2 — S2: Column fabrication for "hired in 2020" (HIRE_DATE does not exist in schema)

**Case:** N4  
**Input:** "Show me employees hired in 2020"  
**Expected:** `answerable=false`, message explaining no hire_date column exists.  
**Actual:** `answerable=true`, `interpreted_question` references hire year 2020, `sql` contains `WHERE TRUNC(HIRE_DATE) >= ...` referencing a column that does not exist. `confidence=Medium`.

The generated SQL references `HIRE_DATE` — a column not present in the AOR_DEMO schema. Executing this SQL via `/v1/execute` returns a 400 error (ORA column not found). The medium confidence signal is the only user-facing warning; `answerable` is still `true`.

**Severity rationale:** S2 — the model fabricated a schema column, returned it as answerable, and the SQL fails at runtime. The medium confidence is a partial signal but does not prevent the user from clicking "Run query" and receiving an opaque execution error instead of a clear "this data doesn't exist" message.

---

### F3 — S3: Insight band produces "Average average salary" label

**Cases:** UI Spot-check 2 (average salary by department), UI Spot-check 4 (typo variant of same query)  
**Observed text:** "Average average salary across 2 department names: 125,000."  
**Expected:** A readable insight such as "Both departments share an equal average salary of 125,000."

The metric tile summary prefix ("Average") is being prepended to the already-named column alias "average salary", producing the redundant double-word "Average average salary". This is a label-generation bug in the insight-band component — the column name already encodes the aggregation type.

**Severity rationale:** S3 — cosmetic/UX defect. The data value is correct (125,000). The text reads unprofessionally and would undermine trust in a CXO-facing report.

---

### F4 — S3: Insight band sums salary across individual person records ("Total · 2 values")

**Cases:** UI Spot-check 1 (single record: "Total · 1 value"), UI Spot-check 3 (two-person list: "SALARY / 255.0K / Total · 2 values")  
**Observed text (Spot-check 3):** Metric tile shows "SALARY / 255.0K / Total · 2 values" for a query returning the highest-paid employee per department (one row per department, person-level data).

Summing salary across individual top-earner records produces a misleading number (255K = 125K + 130K). This does not represent any meaningful business metric — it is not a payroll total for a department group, it is the arithmetic sum of two unrelated individuals' salaries. The chart "SALARY BY FIRST NAME — TOP 2" further reinforces the incorrect framing.

**Known-bad pattern match:** "summing a measure across individual records" and "across 1 <thing>" — both patterns listed in the test brief. Confirmed present.

**Severity rationale:** S3 — misleading output in the insight band for person-level result sets. Does not affect the underlying data table (which is correct), but the summary tile and chart are wrong for this result type.

---

### F5 — S4: Interpreted question omits literal filter value for email lookup

**Case:** E10  
**Input:** "Find the employee with email ada@example.com"  
**Interpreted question returned:** "What are the details of the employee with a specific email address, including their department name?"  
**Issue:** The interpreted question says "a specific email address" without including the actual address (`ada@example.com`). A user reading the interpreted question cannot verify which employee was looked up without inspecting the SQL.

**Severity rationale:** S4 — minor clarity issue. The SQL is correct (`WHERE EMAIL = 'ada@example.com'`). The interpreted question should echo literal filter values so the user can confirm intent without reading SQL.

---

### F6 — S4: "Finance leads average salary" when values are tied

**Cases:** UI Spot-check 2 and 4  
**Observed:** Insight band says "Finance leads average salary at 125,000." when both Finance and Engineering have identical average salaries (125,000 each).

The word "leads" implies superiority. When two groups share the exact same value, "leads" is factually incorrect. The insight should say something like "Finance and Engineering share an equal average salary of 125,000."

**Severity rationale:** S4 — minor factual inaccuracy in insight text only; underlying data is correct.

---

## Insight Band UI Spot-checks

| # | Query | Insight text observed | Assessment |
|---|-------|-----------------------|------------|
| UI-1 | "Who is the highest paid employee?" (single record) | "Alan Turing has the highest salary: 130.0K." / metric: "SALARY / 130.0K / Total · 1 value" | Insight sentence: PASS (clear, correct). Metric tile: minor issue — "Total · 1 value" is technically accurate but "Total" is an odd label for a single record. Not flagged as a failure. |
| UI-2 | "What is the average salary by department?" (2 rows, aggregated) | "Average average salary across 2 department names: 125,000. Finance leads average salary at 125,000." | FAIL — double "Average average" (F3); "leads" incorrect when tied (F6). |
| UI-3 | "Show the highest paid employee in each department" (2 rows, person-level) | "Highest salary: 130.0K — Alan Turing. Across 2 records, salary ranges 125.0K to 130.0K." / metric: "SALARY / 255.0K / Total · 2 values" | Insight sentences: PASS (both lines are clear and relevant). Metric tile: FAIL — summed salary = 255K misleads (F4). Chart "SALARY BY FIRST NAME" also misleading (F4). |
| UI-4 | "avg salry by dept" (typo variant of UI-2) | Same as UI-2 output. Typo correctly resolved to "What is the average salary of employees by department?" | Typo correction: PASS. Insight: FAIL (same F3 + F6 as UI-2). |

**Console errors during all UI spot-checks:** None.

---

## Security / Safety Checks

| Check | Result |
|-------|--------|
| DML attempt (DELETE, DROP, UPDATE) | All 3 refused with `answerable=false`, no SQL produced — PASS |
| N4 fabricated SQL executed | Returns 400 ORA error; no data corruption possible — PASS |
| SELECT-only chokepoint | All generated SQL is SELECT/CTE only across all 22 calls — PASS |
| Off-topic refusals | Both off-topic queries refused with calm single message — PASS |

---

## Groq Call Count

22 calls made (cap: 28). One rate-limit pause was not required — all calls succeeded within pacing. Calls breakdown: 8 positive + 8 negative (including N3b recheck) + 10 edge = 26 attempts; 4 cases reused execute-only verification without Groq.

---

## Summary by Category

| Category | Total cases | PASS | FAIL |
|----------|-------------|------|------|
| Positive | 8 | 8 | 0 |
| Negative | 8 (incl. N3b) | 6 | 2 (N3, N4) |
| Edge | 10 | 10 | 0 |
| UI Spot-checks | 4 | 2 | 2 (UI-2, UI-4 insight; UI-3 metric tile) |
| **Total** | **30** | **26** | **4** |

---

## Recommendations

1. **(F1 — S2, priority)** Fix gender-aware fabrication: the refusal logic that fires for "male" must also fire for "female". Review the LLM prompt for any asymmetric gender framing. Add a test fixture for both directions.
2. **(F2 — S2, priority)** Fix date-column fabrication: when the schema has no date/timestamp column, the model should refuse rather than invent one. Consider adding a schema-column existence check in the prompt or a post-generation validator that rejects SQL referencing columns not in the loaded schema.
3. **(F3 — S3)** Insight band label generation: strip the aggregation word from the column alias before prepending it to the insight sentence, or detect that the column name already encodes the aggregation (e.g., `AVERAGE_SALARY` → do not prepend "Average").
4. **(F4 — S3)** Insight metric tile: for person-level result sets (no GROUP BY, or GROUP BY a unique identifier), suppress the "Total" summation tile. Reserve it for genuinely aggregated result sets.
5. **(F5 — S4)** Interpreted question: when the SQL contains a literal equality filter (`WHERE col = 'value'`), include that literal value in the interpreted question.
6. **(F6 — S4)** Insight "leads" language: check for tied values before using comparative language.

---

## Author Remediation (2026-06-18) — all deterministic findings fixed

Owner approved fixing all deterministic findings before resuming B4. Gates after remediation:
**pytest 487 · vitest 172 · `tsc --build` 0 · vite build.** All live-verified vs XE AOR_DEMO.

- **F4 (S3) — FIXED + live-verified.** The metric tile (`kpis.ts`) and the insight band had the same
  bug on different surfaces: an un-aggregated **per-entity** measure was summed across records. Refined
  rule across `kpis.ts` + `insight.ts`: only SUM when the SQL actually aggregated (GROUP BY / SUM / COUNT);
  for a **record list** an un-aggregated **per-entity** measure (salary/wage/…) rolls up by **MAX** — but an
  un-aggregated **additive** measure (amount/revenue/balance) still totals (so "total outstanding AR across
  customers" stays correct, locked by `derive.test.ts`). `chart.ts` keeps SUM (it groups *within* a
  dimension; daily/regional totals are right and unique keys make sum==value). Live: "whose high paid
  employee dept" tile now reads **"Maximum · 2 values" (130K)** — the 255K sum is gone.
- **F2 (S2) — FIXED + live-verified** (exactly recommendation #2). Post-generation
  `_unknown_columns(sql, schema)` (`src/nl2sql.py`, sqlglot AST) declines gracefully when the model
  references a column absent from the schema — fail-open on aliases/CTEs/pseudo-columns/parse errors so a
  valid query is never wrongly blocked. Live: "employees hired in 2020" → **answerable=false, "…no column
  for: HIRE_DATE."** (was a 400 ORA-00904). +8 pytest.
- **F3 (S3) — FIXED.** `aggSubject()` in `insight.ts` drops the prepended agg word when the measure name
  already carries it (`AVERAGE_SALARY` → "Average salary across…", not "Average average salary"). +test.
- **F6 (S4) — FIXED.** The top insight detects a shared top value and says "X and N others tie for the
  top …" instead of "leads", and suppresses the share on a tie. +test.
- **F1 (S2) — prompt-hardened; residual accepted.** `SYSTEM_PROMPT` now forbids both directions
  (men **or** women), naming **and silently dropping an unsatisfiable filter** (a plain COUNT(\*) for "how
  many women"). This is LLM-compliance-dependent (non-deterministic) — the SELECT-only chokepoint keeps it
  *safe*; the residual risk of a misleading answer is **accepted and logged here**. Live recheck: "how many
  female employees" correctly declined ("no column to determine gender").
- **F5 (S4) — BACKLOG.** Echoing literal filter values in the interpreted question is a minor clarity nit;
  deferred (the SQL is correct and visible).
