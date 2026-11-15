"""Requirement 16: expose your tools over MCP.

    python mcp_server.py            # speaks JSON-RPC on stdin/stdout

Then connect to it with your Chapter 16 client, from a separate process.

THE ONE RULE: nothing but JSON-RPC messages goes to stdout. Log to stderr.
"""

from __future__ import annotations

# TODO
# server = MCPServer("capstone")
# for t in my_tools: server.add_tool(t)
# server.add_resource(...)   # optional
# server.serve_stdio()
