"""MCP server for Binderdash, mounted into the FastAPI app at /api/mcp.

Named ``mcp_server`` rather than ``mcp``: pytest puts ``backend/`` on ``sys.path``, and
a package called ``mcp`` there shadows the MCP SDK that fastmcp imports, breaking it
with a bare "No module named 'mcp.client'".

Import this package freely: nothing here imports ``fastmcp`` at module scope, so a
build without the optional ``mcp`` extra (notably the PyInstaller desktop bundle)
imports it harmlessly and simply gets no MCP endpoint.
"""

from .server import MCP_MOUNT_PATH, build_mcp_http_app

__all__ = ["MCP_MOUNT_PATH", "build_mcp_http_app"]
