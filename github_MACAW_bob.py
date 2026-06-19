"""
github-MACAW-bob  --  GitHub remote MCP via SecureMCPProxy, bound to bob (manager).

Per-user gateway: secCC does NOT propagate identity, so the caller is baked in here
(RemoteIdentityProvider login -> JWT -> MACAWClient). secCC spawns this stdio server;
each tools/call is relayed through the mesh AS bob -> proxy -> GitHub.

REGISTER (token passed as an env export in the register command -- NOT stored in this file):
 claude mcp add github-MACAW-bob --scope user \
    -- bash -lc 'source /home/itsadijmbt/demo4/venv/bin/activate && \
       export MACAW_HOME="/home/itsadijmbt/demo4/macaw-client-0.9.9.2-Linux-x86_64-py3.12" && \
       export MACAW_USERID="bob" && \
       export MACAW_USER="bob@macaw.com" && \
       export MACAW_PASSWORD="test@123" && \
       export GITHUB_TOKEN="github_pat" && \
       cd /home/itsadijmbt/demo4/demo && \
       python github_MACAW_bob.py'

"""

import os
import sys
import json
import asyncio
import logging

from macaw_adapters.mcp import SecureMCPProxy
from macaw_client import MACAWClient, RemoteIdentityProvider

from mcp.server import Server
from mcp.server.stdio import stdio_server
import mcp.types as types

logging.basicConfig(level=logging.INFO, stream=sys.stderr)

# --- identity + creds: ALL via env exports in the register command (nothing hardcoded) ---
USERID         = os.environ["MACAW_USERID"]
MACAW_USER     = os.environ["MACAW_USER"]
MACAW_PASSWORD = os.environ["MACAW_PASSWORD"]
GITHUB_TOKEN   = os.environ["GITHUB_TOKEN"]
GITHUB_MCP_URL = "https://api.githubcopilot.com/mcp/x/repos/readonly"

proxy = SecureMCPProxy(
    app_name="github-remote-proxy",
    upstream_url=GITHUB_MCP_URL,
    upstream_auth={"type": "bearer", "token": GITHUB_TOKEN},
)
jwt_token, _ = RemoteIdentityProvider().login(MACAW_USER, MACAW_PASSWORD)
bound = proxy.bind_to_user(MACAWClient(
    app_name=f"github-macaw-{USERID}", agent_type="user",
    user_name=MACAW_USER, iam_token=jwt_token))
print(f"[github-MACAW-{USERID}] bound to {MACAW_USER} -- "
      f"{len(proxy.list_tools())} tools", file=sys.stderr)

srv = Server(f"github-macaw-{USERID}")


@srv.list_tools()
async def _list():
    return [types.Tool(name=t["name"], description=t.get("description", ""),
                       inputSchema=t.get("schema") or {"type": "object"})
            for t in proxy.list_tools()]


@srv.call_tool()
async def _call(name, arguments):
    try:
        r = bound.call_tool(name, arguments or {})
        text = json.dumps(r, default=str) if isinstance(r, (dict, list)) else str(r)
    except Exception as e:
        text = f"MACAW deny / upstream error: {e}"
    return [types.TextContent(type="text", text=text)]


async def _serve():
    async with stdio_server() as (rd, wr):
        await srv.run(rd, wr, srv.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(_serve())
