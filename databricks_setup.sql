-- ============================================================================
-- MACAW separation-of-duties demo -- Databricks setup
-- Paste this whole file into the Databricks SQL editor (serverless warehouse)
-- and Run All. Creates the schema + the two tables the demo uses.
-- ============================================================================

-- 0) wake the warehouse / sanity
SELECT 1 AS warehouse_awake;

-- 1) schema
CREATE SCHEMA IF NOT EXISTS workspace.macaw_demo;

-- 2) customers -- used for the NORMAL read (runs free for aditya)
CREATE OR REPLACE TABLE workspace.macaw_demo.customers (
  customer_id  INT,
  name         STRING,
  email        STRING,
  loyalty_tier STRING
);
INSERT INTO workspace.macaw_demo.customers VALUES
  (1, 'Alan Park',   'alan@example.com',  'silver'),
  (2, 'Bee Nguyen',  'bee@example.com',   'bronze'),
  (3, 'Carol White', 'carol@example.com', 'gold'),
  (4, 'Dan Cole',    'dan@example.com',   'gold');

-- 3) eng_comp -- the COMP/PAYROLL table; reads of this are GATED behind a
--    manager (bob) attestation in user:aditya's policy.
--    NOTE: use eng_comp, NOT hr_salaries -- hr_salaries is HARD-DENIED in the
--    server policy and could never reach the approval gate.
CREATE OR REPLACE TABLE workspace.macaw_demo.eng_comp (
  employee_id INT,
  name        STRING,
  dept        STRING,
  level       STRING,
  base_salary INT,
  bonus       INT
);
INSERT INTO workspace.macaw_demo.eng_comp VALUES
  (1, 'Carol White', 'Engineering', 'L5', 185000, 35000),
  (2, 'Dave Green',  'Engineering', 'L4', 150000, 20000),
  (3, 'Erin Black',  'Analytics',   'L4', 145000, 18000),
  (4, 'Frank Blue',  'Engineering', 'L6', 230000, 60000);

-- 4) verify
SELECT 'customers' AS tbl, count(*) AS rows FROM workspace.macaw_demo.customers
UNION ALL
SELECT 'eng_comp'  AS tbl, count(*) AS rows FROM workspace.macaw_demo.eng_comp;

-- ============================================================================
-- Demo queries (run these THROUGH databricks-MACAW-aditya in Claude, NOT here):
--   FREE  : SELECT name, loyalty_tier FROM workspace.macaw_demo.customers WHERE loyalty_tier='gold';
--   GATED : SELECT * FROM workspace.macaw_demo.eng_comp LIMIT 5;        -> needs bob (manager)
--   DENIED: DELETE FROM workspace.macaw_demo.customers WHERE customer_id=1;
-- ============================================================================
