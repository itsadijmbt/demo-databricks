# MACAW Hierarchical Policy Demo

Org `MACAW` with two business units and three users, expressed as a MAPL policy
hierarchy (`extends` chain). Each child may only **add restrictions** to its
parent (monotonic restriction, Theorem 1). The effective policy for any request
is the **intersection** up the chain: `user ∩ bu ∩ company`.

## Hierarchy

```
company:MACAW                         resources tool:**            LLM 1,000,000 tok, any model
├── bu:Engineering   (extends company)  db + github proxies + LLM    LLM 800k, model claude-opus-4-8
│   ├── user:alice   (admin)            inherit Engineering          LLM 300k  (model/tools inherited)
│   └── user:bob     (manager)          inherit Engineering          LLM 100k; writes -> admin attest; destructive hard-denied
└── bu:Analytics     (extends company)  databricks proxy only + LLM  LLM 500k, model claude-sonnet-4-6, opus/fable hard-denied
    └── user:aditya  (analyst)          only execute_sql(+ro) + LLM  updates -> admin attest; destructive hard-denied; SELECT free
```

## Files
`policies/company_MACAW.json`, `bu_Engineering.json`, `bu_Analytics.json`,
`user_alice.json`, `user_bob.json`, `user_aditya.json`.

## Resolved effective policy (intersection up the chain)

| user | chain | max_tokens | model | tools (resources) | write/update | destructive |
|---|---|---|---|---|---|---|
| **alice** (admin) | alice→Engineering→MACAW | **300k** | `claude-opus-4-8` | databricks + github (+LLM) | free (admin) | free |
| **bob** (manager) | bob→Engineering→MACAW | **100k** | `claude-opus-4-8` | databricks + github (+LLM) | `INSERT/UPDATE/CREATE/MERGE/COPY` → **admin attest** (`allow_write`, ttl 120s) | `DROP/DELETE/TRUNCATE/ALTER/REVOKE/GRANT/VACUUM` + secret files (gh) **hard-DENY** |
| **aditya** (analyst) | aditya→Analytics→MACAW | **500k** | `claude-sonnet-4-6` | only `execute_sql` + `execute_sql_read_only` (+LLM) | `INSERT/UPDATE/CREATE/MERGE/COPY` → **admin attest** (`allow_update`, one-time) | `DROP/DELETE/TRUNCATE/...` + `hr_salaries` **hard-DENY** |

Escalation ladder: **everyone's writes/updates → admin (alice) signs off; destructive ops can never be signed off (hard-denied).**

## MAPL rules applied (verified)
- **Hierarchy / `extends`** — each policy points at its parent `policy_id`; chain resolves with no dangling refs or cycles.
- **Monotonic restriction (Theorem 1)** — children only narrow: `max_tokens` merges by **min** (1M→800k→300k/100k; 1M→500k), `model` by **intersection** (`any`→opus / sonnet), `resources` by **domain-aware narrowing** (`tool:**` → proxy subset → single tools). No child raises a parent's limit. *(All verified programmatically.)*
- **Eval order** `denied_resources → parameters → denied_parameters → attestations`. Destructive SQL is caught at **`denied_parameters` (step 3)** — *before* the attestation stage — so it is **never approvable**. Additive writes pass step 3 and hit the **attestation (step 4)**.
- **Red-team principle (must-block vs checkpoint)** — irreversible ops (`DROP/DELETE/TRUNCATE/REVOKE/...`) are **deterministic hard-denies**, never attestations (attestation approval is not enforced in 0.9.4, and an irreversible op must not be approvable). Reversible writes (`INSERT/UPDATE/CREATE`) are the only things gated by attestation.
- **`denied_parameters` copied verbatim** in bob from the GitHub + Databricks server policies (machine-diff: 9 / 15 / 25 patterns, exact).
- **No `MATCHES '*'` presence-test** — every condition keys on real value content (`'*UPDATE *'`, `'*DROP *'`), not the always-true `'*'`.

## Runtime prerequisite (claims mapping)
For the hierarchy to bind, each user's JWT must carry (via Auth0 Action + Console Identity Bridge):
`organization=MACAW` → `company:MACAW`; `business_unit=Engineering|Analytics` → `bu:*`;
`user=alice|bob|aditya` → `user:*`; `roles=[admin|manager|analyst]` (alice=admin, bob=manager, aditya=analyst).
Attestation visibility is role-gated, so the approver's token must resolve to `role:admin`.

## Honest caveats (do not skip)
1. **Cross-policy attestation overlap.** The Databricks **server** policy (`app:databricks-remote-proxy`, v0.3.0) also defines `allow_write` with `approval_criteria: role:manager`. It applies *in addition to* the identity policy (dual-perspective = union of attestations). So an `UPDATE`/write by bob or aditya fires **both** gates: the server's `allow_write` (→ **manager**/bob) **and** the identity-side attestation (→ **admin**/alice) — i.e. it needs **two approvals** (bob *and* alice). Align the server's `allow_write` to `role:admin` if you want a single admin approver.
2. **`denied_parameters` is path-dependent** (verified): enforced via SecureMCPProxy, **inert** on owned-SecureMCP. Analytics's `denied_parameters.model` (opus/fable block) is belt-and-suspenders — the **`allowed_values: [claude-sonnet-4-6]`** is what actually enforces the model pin.
3. **Glob conditions are case-sensitive + substring** (the splunk lesson): `Drop`, `/*c*/`, or whitespace tricks can dodge them. The **real controls are the upstream token scopes** (read-only Databricks warehouse, least-privilege GitHub PAT); MAPL is defense-in-depth.
4. **LLM tools (`tool:*/generate`, `tool:*/complete`) are included in each tier's `resources`** so the agent can still run its model after narrowing; otherwise "opus-only / sonnet-only" would apply to a tool the tier couldn't call.

## Verification
`python3 - <<…` over `policies/*.json` checks: JSON validity (6), extends resolves (no dangling/cycle), monotonic `max_tokens`/`model`/`resources`, attestation form + no `MATCHES '*'`, `approval_criteria` format, and the red-team invariant (destructive hard-denied, not attested). **Result: ALL CHECKS PASS.**
