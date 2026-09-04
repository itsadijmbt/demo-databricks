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


   

proxy = SecureMCPProxy(
    app_name="databricks-remote-proxy",
    upstream_url=DATABRICKS_MCP_URL,
    upstream_auth={"type": "bearer", "token": DATABRICKS_TOKEN},
)



proxy.run()   
