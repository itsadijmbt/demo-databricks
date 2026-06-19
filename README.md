# MACAW demo4 : Run-Anywhere Guide

A portable walkthrough for running the MACAW per-user MCP gateway demo (GitHub + Databricks),
governed by MACAW identity + policy. Works from **any** folder : everything keys off `$DEMO_ROOT`.

---

## 0. What this demo proves

A single human runs Claude/secCC. They register **per-user gateways** (`github-MACAW-bob`,
`databricks-MACAW-alice`, …). Each gateway is two things at once:

- **Face A** : a real stdio MCP server (so Claude can spawn it).
- **Face B** : a MACAW mesh client **bound to one user's JWT** (alice / bob / aditya).

So every tool call is relayed *as that user* → MACAW enforces **that user's policy**
(allow / deny / attestation) before the call reaches GitHub or Databricks.
Same machine, same upstream token : **different governance per persona**. That's the point.

---

## 1. What's portable vs what you supply

| Portable (carry the `demo4/` folder) | You must supply per environment |
|---|---|
| `demo/` gateway scripts, `test_jwt.py`, `approve.py`, `policies/` | A **GitHub PAT** (`GITHUB_TOKEN`) |
| The wheel + `secureAI/` source | A **Databricks token + workspace URL** (`DATABRICKS_TOKEN`, `DATABRICKS_MCP_URL`) |
| `…/.macaw/config.json` (MACAW tenant api_key + endpoint) | Claude Code installed (`claude` CLI) |

The Auth0 **test users** (`alice@macaw.com`, `bob@macaw.com`, `buszadi1@gmail.com`,
`adibhatt2203@gmail.com`, all password `test@123`) and the **MACAW tenant** travel with the
config : you reuse the same ones. Only the **upstream tokens** (GitHub/Databricks) are yours.

---

## 2. One-time setup (from any path)

```bash
# 1) point DEMO_ROOT at wherever you put the demo4 folder
export DEMO_ROOT="$HOME/demo4"                       # <-- change to your path

# 2) MACAW_HOME MUST be the wheel dir : the one that CONTAINS .macaw/config.json
export MACAW_HOME="$DEMO_ROOT/macaw-client-0.9.9.2-Linux-x86_64-py3.12"

# 3) create a venv (Python 3.12 to match the wheel) and install
python3.12 -m venv "$DEMO_ROOT/venv"        # or: uv venv "$DEMO_ROOT/venv"
source "$DEMO_ROOT/venv/bin/activate"
pip install "$MACAW_HOME"/macaw_client-0.9.9.2-cp312-cp312-manylinux_2_17_x86_64.whl
pip install "$MACAW_HOME/secureAI[all]"

# 4) sanity: imports + config found
python -c "import macaw_client, macaw_adapters; print('ok')"
```

> **Gotcha #1 (the #1 cause of `-32000`):** `MACAW_HOME` must point at the **wheel dir**, not
> `demo4/`. The `.macaw/config.json` lives *inside* the wheel dir. Point it at `demo4/` and you
> get `MACAW endpoint not configured` → tools never register on the mesh → gateway dies on
> startup → Claude shows `-32000`.

To use **your own** MACAW tenant instead of the demo's, replace the `api_key` in
`$MACAW_HOME/.macaw/config.json` (that key *is* the tenant : see the MACAW console).

---

## 3. Verify identity before touching gateways

```bash
cd "$DEMO_ROOT/demo"
python test_jwt.py
```
Expect every user to bind: `org=macaw  bu=…  roles=[…]  username=<x> -> user:<x>`.

> **Gotcha #2:** alice/bob log in with `@macaw.com` (their Auth0 **email**), not `@macaw.test`
> and not `alice@macaw`. buszadi1/aditya are the gmail addresses. Wrong email → `403 Wrong
> email or password`. The username→policy mapping:

| login email | `username` claim | policy id |
|---|---|---|
| `alice@macaw.com` | `alice` | `user:alice` |
| `bob@macaw.com` | `bob` | `user:bob` |
| `buszadi1@gmail.com` | `buszadi1` | `user:buszadi1` |
| `adibhatt2203@gmail.com` | `aditya` | `user:aditya` |

`test_jwt.py` checks the **token** only. For `user:<x>` to actually bind at policy time, the
MACAW **identity bridge** must map `name_path = https://macaw.local/username`.

### Identity bridge / claims mapping

Paste this into the MACAW Console → **Settings → Identity Providers → Configure Identity
Provider (Auth0) → Claims Mapping → Review & Save**. Keep exactly **one** provider block
(duplicate keys silently last-win) and **no trailing spaces** in any path. Do **not** use Auth0
`name` for `name_path` : it resolves to the display name (`bob@macaw.com`) → MACAW looks up
`user:bob@macaw.com` (invalid policy id, `found:false`). The username claim is the only one that
yields the short id. (Also saved as `identity_bridge.yaml` next to this file.)

```yaml
identity_providers:
  macaw-mcp-test-api-(test-application):
    name: macaw-mcp-test-api (Test Application)
    type: auth0
    detection:
      iss_pattern: '*dev-5ntnefdmlsiwh7nv.us.auth0.com*'
    mappings:
      subject_path: sub
      email_path: email
      name_path: https://macaw.local/username      # -> user:<username>  (alice|bob|aditya)
      organization_path: https://macaw.local/organization   # -> company:macaw
      roles_path: https://macaw.local/roles
      business_unit_path: https://macaw.local/business_unit  # -> bu:Engineering|Analytics
      team_path: https://macaw.local/team
    role_filter:
      allowed:
      - analyst
      - manager
      - admin
      - viewer
      case_sensitive: false
```

The Auth0 **Post-Login Action** (in the flow, e.g. `LoginFlow`) must emit that username claim
from `app_metadata`, on both tokens:
```js
const NS = "https://macaw.local/";
const username = event.user.app_metadata?.username || null;   // "alice" / "bob" / "aditya"
for (const t of [api.idToken, api.accessToken]) {
  t.setCustomClaim(NS + "organization",  "macaw");
  t.setCustomClaim(NS + "business_unit", event.user.app_metadata?.business_unit || "Unassigned");
  t.setCustomClaim(NS + "team",          event.user.app_metadata?.team || null);
  t.setCustomClaim(NS + "username",      username);
  t.setCustomClaim(NS + "roles",         event.authorization?.roles || event.user.app_metadata?.roles || []);
}
```
Each user's `app_metadata` must contain `"username": "<short id>"` : that's the value
`name_path` reads, and it must equal the policy id (`user:alice` / `user:bob` / `user:aditya`).

---

## 4. Register the gateways with Claude

Each gateway is registered as its own MCP server. **All creds come from env exports in the
register command : nothing is hardcoded in the `.py`.** Re-add per user:

### GitHub : bob (manager)
```bash
claude mcp add github-MACAW-bob --scope user \
  -- bash -lc 'source '"$DEMO_ROOT"'/venv/bin/activate && \
     export MACAW_HOME="'"$DEMO_ROOT"'/macaw-client-0.9.9.2-Linux-x86_64-py3.12" && \
     export MACAW_USERID="bob" && \
     export MACAW_USER="bob@macaw.com" && \
     export MACAW_PASSWORD="test@123" && \
     export GITHUB_TOKEN="<YOUR_GITHUB_PAT>" && \
     cd '"$DEMO_ROOT"'/demo && python github_MACAW_bob.py'
```

### Databricks : alice (admin)
```bash
claude mcp add databricks-MACAW-alice --scope user \
  -- bash -lc 'source '"$DEMO_ROOT"'/venv/bin/activate && \
     export MACAW_HOME="'"$DEMO_ROOT"'/macaw-client-0.9.9.2-Linux-x86_64-py3.12" && \
     export MACAW_USERID="alice" && \
     export MACAW_USER="alice@macaw.com" && \
     export MACAW_PASSWORD="test@123" && \
     export DATABRICKS_TOKEN="<YOUR_DATABRICKS_TOKEN>" && \
     export DATABRICKS_MCP_URL="https://<your-workspace>.cloud.databricks.com/api/2.0/mcp/sql" && \
     cd '"$DEMO_ROOT"'/demo && python databricks_MACAW_alice.py'
```


## 5. Approving attestations

When a call needs an attestation (e.g. aditya's `INSERT` → `allow_update`, criteria
`role:admin`), an admin approves it:

```bash
cd "$DEMO_ROOT/demo"
APPROVER_USER="alice@macaw.com" APPROVER_PW="test@123" APPROVER_ROLE="admin" \
  python approve.py
```
This lists pending attestations and approves them. (Approve as the role the gate requires —
`role:admin` = alice.)
