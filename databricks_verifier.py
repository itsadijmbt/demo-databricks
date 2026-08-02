"""
databricks_verifier.py -- value-level pre-verifier for Databricks SQL writes.

AST-parses (sqlglot) every column<-value write from UPDATE / MERGE / INSERT into
invocation params. Column-agnostic: the MAPL policy decides which columns/thresholds
matter, e.g.
    comp_change_approved::{ params.bonus_resolution == 'resolved' AND params.bonus > 10000 }
    unclear_value::{ params.bonus_resolution == 'unresolved' }
So gating a new column is a policy edit, never a code change.

  extract_assignments(sql) -> {column: (resolution, value)}    # AST parse
  DatabricksSQLVerifier                                        # thin SDK glue

resolution is "resolved" (integer literal) or "unresolved" (expression / subquery /
variable / non-integer). The verifier writes <col>_resolution ALWAYS, and the value
param ONLY when resolved (never a sentinel) -- so params.<col> exists iff it is a
real, known integer. Unresolved fails closed via the policy's unclear_value gate.
"""
from typing import Dict, Optional, Tuple

import sqlglot
from sqlglot import expressions as exp


def extract_assignments(sql: str) -> Dict[str, Tuple[str, Optional[int]]]:
    """AST-extract every column<-value write from UPDATE / MERGE / INSERT.
    Unparseable SQL raises -> the verifier turns that into a fail-closed deny."""
    out: Dict[str, Tuple[str, Optional[int]]] = {}

    def record(col: str, rhs) -> None:
        col = col.lower()
        if isinstance(rhs, exp.Literal) and rhs.is_int:
            out[col] = ("resolved", int(rhs.name))
        else:
            out[col] = ("unresolved", None)        # expr / var / subquery / non-int

    for stmt in sqlglot.parse(sql):                # handles ; batches
        if stmt is None:
            continue
        # UPDATE ... SET col = val -- find_all ALSO reaches the UPDATE nested inside a
        # MERGE (WHEN MATCHED THEN UPDATE), which a top-level isinstance() check misses.
        for upd in stmt.find_all(exp.Update):
            for eq in upd.args.get("expressions", []):
                record(eq.this.name, eq.expression)
        # INSERT INTO t (c1, c2) VALUES (v1, v2)
        # NOTE: PARTIAL coverage. Multi-row VALUES takes the LAST row; INSERT ... SELECT
        # and column-less INSERT extract nothing. So keep a coarse allow_insert gate as
        # the net -- do NOT value-gate INSERT on this alone. (TODO: max-across-rows.)
        for ins in stmt.find_all(exp.Insert):
            schema = ins.this                       # exp.Schema: table + column list
            cols = [c.name for c in schema.expressions] if isinstance(schema, exp.Schema) else []
            values = ins.expression                 # exp.Values
            if cols and isinstance(values, exp.Values):
                for tup in values.expressions:      # each VALUES (...) row
                    for col, rhs in zip(cols, tup.expressions):
                        record(col, rhs)
    return out


# --- SDK glue (lazy import so extract_assignments stays import-safe without the SDK) --
try:
    from macaw.security.verification.verifier import Verifier
    from macaw.security.verification.result import VerificationResult

    class DatabricksSQLVerifier(Verifier):
        """Writes each extracted assignment to params so policy conditions can read it.
        - <col>_resolution: always set ("resolved" | "unresolved") -- authoritative signal.
        - <col>: real int ONLY when resolved; popped otherwise (no sentinel, no stale or
          forgeable value left behind).
        Fail-closed: unparseable SQL -> success=False (deny)."""

        def __init__(self):
            super().__init__(name="databricks_sql_verifier")
            self.scope.resource_patterns = ["*databricks*execute_sql"]  # write tool only
            self.scope.compile_patterns()

        def verify(self, invocation, context):
            sql = (invocation.params or {}).get("query", "")
            try:
                assignments = extract_assignments(sql)
            except Exception as e:
                return VerificationResult(False, f"Unparseable SQL, denied (fail-closed): {e}")
            for col, (res, val) in assignments.items():
                invocation.params[f"{col}_resolution"] = res
                if res == "resolved":
                    invocation.params[col] = val            # real int, only when known
                else:
                    invocation.params.pop(col, None)        # never leave a stale/forgeable value
            return VerificationResult(True, "extracted")
except ImportError:
    pass  # extractor remains importable/usable without the SDK present
