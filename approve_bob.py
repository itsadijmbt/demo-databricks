"""
approve_bob.py -- attestation approver hardwired to BOB (role:manager).

Same as approve.py but the approver identity is HARDCODED (no env needed):
    bob@macaw.com / test@123 / role:manager

Use this for the separation-of-duties demo: bob is the MANAGER who approves
aditya's (analyst) comp_review_approved gate (approval_criteria: role:manager).

RUN:
    export MACAW_HOME="/home/itsadijmbt/demo4/macaw-client-0.9.9.2-Linux-x86_64-py3.12"
    python approve_bob.py

    # non-interactive (auto-approve every request):
    AUTO=y python approve_bob.py
"""

import json
import os
import sys
import time

from macaw_client import MACAWClient, RemoteIdentityProvider

# --- hardcoded approver identity (bob, manager) ---
APPROVER_USER = "bob@macaw.com"
APPROVER_PW = "test@123"
APPROVER_ROLE = "manager"

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
        print("  Check MACAW_HOME and that the IdP is reachable.")
        return 1
    print("  got JWT")

    approver = MACAWClient(
        user_name=APPROVER_USER.split("@")[0],
        iam_token=jwt_token,
        agent_type="admin",
        app_name="databricks-attestation-approver-bob",
        intent_policy={
            "resources": ["attestation:*"],
            "constraints": {"roles": [APPROVER_ROLE]},
        },
    )
    if not approver.register():
        print("  ERROR: register failed (is the mesh/LocalAgent reachable?)")
        return 1
    print(f"  approver agent_id: {approver.agent_id}")
    print("  -> every approval below is signed by THIS identity (audit: approved_by)")

    print(f"\n[2] Watching for pending attestations (every {POLL_SECONDS}s). Ctrl-C to stop.")
    print("    Trigger one: as aditya, run  SELECT * FROM workspace.macaw_demo.eng_comp LIMIT 5\n")
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
                    print(f"    value (the SQL)  : {json.dumps(att.get('value'))}")
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
