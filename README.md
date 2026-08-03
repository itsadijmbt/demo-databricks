# MACAW demo4 : Run-Anywhere Guide

A portable walkthrough for running the MACAW per-user MCP demo,
governed by MACAW identity + policy. Works from **any** folder : everything keys off `$DEMO_ROOT`.

Unity Catalog enforces who's eligible, at the engine, for every path  but it can't tell INSERT from DELETE, and it can't pause for a human. MACAW adds per-action, role-tiered, 
just-in-time human approval on the agent's path  SELECT runs, an UPDATE needs a manager, a DELETE needs an admin  GA today, and the same gate spans GitHub and the model. Use both: UC 
for standing engine-level grants, MACAW for the agent's just-in-time sign-offs.

---


## 0. What this demo proves

A single human runs Claude/secCC. They register **per-user gateways** (`github-MACAW-bob`,
`databricks-MACAW-alice`, …). Each gateway is two things at once:

- **Face A** : a real stdio MCP server (so Claude can spawn it).
- **Face B** : a MACAW mesh client **bound to one user's JWT** (alice / bob / aditya).


---

## 1. What's portable vs what you supply


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



---



### 3 Identity bridge / claims mapping

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



### Databricks : aditya (analyst)
```bash
    claude mcp add databricks-MACAW-aditya --scope user \
      -- bash -lc 'source /home/itsadijmbt/demo5/venv/bin/activate && \
         MACAW_HOME="/home/itsadijmbt/demo5/macaw-client-0.9.9.6-Linux-x86_64-py3.12" && \
         export MACAW_USERID="aditya" && \
         export MACAW_USER="adibhatt2203@gmail.com" && \
         export MACAW_PASSWORD="test@123" && \
         export DATABRICKS_TOKEN="xxx" && \
         cd /home/itsadijmbt/demo5/demo-databricks && \
         python databricks_MACAW_aditya.py'
```


## 5. Approving attestations

When a call needs an attestation use file or console directly.
```bash
  python approve_bob.py
 
```


                                                      hard-denied, no approval      
