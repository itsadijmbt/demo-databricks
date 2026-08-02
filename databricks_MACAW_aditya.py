"""
databricks-MACAW-aditya  --  Databricks managed SQL MCP via SecureMCPProxy, bound to aditya (analyst).

    claude mcp add databricks-MACAW-aditya --scope user \
      -- bash -lc 'source /home/itsadijmbt/demo5/venv/bin/activate && \
         MACAW_HOME="/home/itsadijmbt/demo5/macaw-client-0.9.9.6-Linux-x86_64-py3.12" && \
         export MACAW_USERID="aditya" && \
         export MACAW_USER="adibhatt2203@gmail.com" && \
         export MACAW_PASSWORD="test@123" && \
         export DATABRICKS_TOKEN="xxx" && \
         cd /home/itsadijmbt/demo5/demo-databricks && \
         python databricks_MACAW_aditya.py'
"""

import os
import sys
import json
import asyncio
import logging
import httpx
from macaw_adapters.mcp import SecureMCPProxy
from macaw_client import MACAWClient, RemoteIdentityProvider


logging.basicConfig(level=logging.INFO, stream=sys.stderr)

USERID             = os.environ["MACAW_USERID"]
MACAW_USER         = os.environ["MACAW_USER"]
MACAW_PASSWORD     = os.environ["MACAW_PASSWORD"]
DATABRICKS_TOKEN   = os.environ["DATABRICKS_TOKEN"]
DATABRICKS_MCP_URL = "https://dbc-492b5d82-20eb.cloud.databricks.com/api/2.0/mcp/sql"


import httpx as _httpx
def _timed_create_http_client(self):
    ua = self.upstream_auth
    headers = {}
    if getattr(ua, "type", None) == "bearer" and getattr(ua, "token", None):
        headers["Authorization"] = f"Bearer {ua.token}"
    elif getattr(ua, "type", None) == "api_key" and getattr(ua, "api_key", None):
        headers[getattr(ua, "header_name", None) or "X-API-Key"] = ua.api_key
    return _httpx.AsyncClient(
        headers=headers or None,
        timeout=_httpx.Timeout(connect=30, read=300, write=30, pool=30),
    )
SecureMCPProxy._create_http_client = _timed_create_http_client   

proxy = SecureMCPProxy(
    app_name="databricks-remote-proxy",
    upstream_url=DATABRICKS_MCP_URL,
    upstream_auth={"type": "bearer", "token": DATABRICKS_TOKEN},
)
jwt_token, _ = RemoteIdentityProvider().login(MACAW_USER, MACAW_PASSWORD)
bound = proxy.bind_to_user(MACAWClient(
    app_name=f"databricks-macaw-{USERID}", agent_type="user",
    user_name=MACAW_USER, iam_token=jwt_token))
print(f"[databricks-MACAW-{USERID}] bound to {MACAW_USER} -- "
      f"{len(proxy.list_tools())} tools", file=sys.stderr)


import macaw_adapters.mcp._endpoint as _endpoint

_StubClient = _endpoint.Client


def _bound_stub_client(name):
    stub = _StubClient(name)
    stub.macaw_client = bound.user_client
    return stub


_endpoint.Client = _bound_stub_client

proxy.run()   
