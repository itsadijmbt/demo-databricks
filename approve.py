"""
approve.py -- attestation approver console for the MACAW demo.
Defaults to alice@macaw (role:admin) -- the approver for the demo's
identity-policy gates.

A MACAWClient minted from an APPROVER's JWT. Polls for pending attestations, prints
WHO asked + WHAT (the SQL), prompts, and approve_attestation()s it. The blocked caller
then unblocks. Mirrors the Snowflake approve_manager.py.

Which attestations a user can satisfy depends on the policy's approval_criteria:
    user:bob allow_write / user:aditya allow_update  ->  role:admin    (alice)
    databricks SERVER policy allow_write             ->  role:manager  (bob / buszadi1)

RUN (one terminal per approver -- same script, different creds):
    # alice (admin) -- approves the identity-side allow_write / allow_update   [DEFAULT]
    python approve.py

    # buszadi1 (manager) -- approves the databricks server-side allow_write
    APPROVER_USER=buszadi1@gmail.com APPROVER_PW=test@123 APPROVER_ROLE=manager python approve.py

Needs MACAW_HOME set (RemoteIdentityProvider reads .macaw to find the tenant's IdP).
AUTO=y  -> auto-approve every request (non-interactive demo).
"""

import json
import os
import sys
import time

from macaw_client import MACAWClient, RemoteIdentityProvider

APPROVER_USER = os.environ.get("APPROVER_USER", "alice@macaw.com")
APPROVER_PW = os.environ.get("APPROVER_PW", "test@123")
APPROVER_ROLE = os.environ.get("APPROVER_ROLE", "admin")
POLL_SECONDS = float(os.environ.get("POLL_SECONDS", "2"))
AUTO = os.environ.get("AUTO", "")


def main():
    print("=" * 64)
    print(f"DATABRICKS ATTESTATION APPROVER  --  {APPROVER_USER} (role:{APPROVER_ROLE})")
    print("=" * 64)

    print(f"\n[1] Authenticating as '{APPROVER_USER}'...")
    try:
        jwt_token, _ = RemoteIdentityProvider().login(APPROVER_USER, APPROVER_PW)
    except Exception as e:
        print(f"  ERROR: login failed: {e}")
        print("  Check APPROVER_USER/APPROVER_PW, MACAW_HOME, and that the IdP is reachable.")
        return 1
    print("  got JWT")

    approver = MACAWClient(
        user_name=APPROVER_USER.split("@")[0],
        iam_token=jwt_token,
        agent_type="admin",
        app_name="databricks-attestation-approver",
        intent_policy={
            "resources": ["attestation:*"],
            "constraints": {"roles": [APPROVER_ROLE]},
        },
    )
    if not approver.register():
        print("  ERROR: register failed (is LocalAgent running?)")
        return 1
    print(f"  approver agent_id: {approver.agent_id}")
    print("  -> every approval below is signed by THIS identity (audit: approved_by)")

    print(f"\n[2] Watching for pending attestations (every {POLL_SECONDS}s). Ctrl-C to stop.")
    print("    Trigger one: run an INSERT/UPDATE (allow_write) or DROP/GRANT "
          "(allow_destroy / allow_privilege) via the databricks gateway in the caller.\n")
    seen = set()
    try:
        while True:
            try:
                pending = approver.list_attestations(status="pending") or []
            except Exception as e:
                print(f"  [warn] list_attestations error: {e}")
                pending = []

            for att in pending:
                rid = att.get("request_id") or att.get("id") or json.dumps(att, sort_keys=True)
                if rid in seen:
                    continue
                seen.add(rid)
                print("-" * 64)
                print("  PENDING attestation")
                print(f"    key              : {att.get('key')}")
                print(f"    requested by     : {att.get('for_agent')}")
                print(f"    approval_criteria: {att.get('approval_criteria')}")
                print(f"    one_time         : {att.get('one_time')}")
                if att.get("value"):
                    print(f"    value            : {json.dumps(att.get('value'))}")
                print("-" * 64)

                choice = AUTO or input("  Approve / Deny / Skip? [y/d/s]: ").strip().lower()
                if choice == "y":
                    ok = approver.approve_attestation(
                        att, reason=f"Approved by {APPROVER_USER} ({APPROVER_ROLE})")
                    print(f"  -> APPROVED by {approver.agent_id} : {ok}")
                elif choice == "d":
                    ok = approver.deny_attestation(att, reason=f"Denied by {APPROVER_USER}")
                    print(f"  -> DENIED by {approver.agent_id} : {ok}")
                else:
                    print("  -> skipped (will reappear next poll)")
                    seen.discard(rid)

            time.sleep(POLL_SECONDS)
    except KeyboardInterrupt:
        print("\n  stopping...")
    finally:
        try:
            approver.unregister()
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
