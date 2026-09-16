"""Tool registration. Each module owns one slice of the surface."""

from __future__ import annotations

from typing import Any


def register_tools(mcp: Any) -> None:
    from . import designs, discovery, selection, structures, target_contacts

    discovery.register(mcp)
    designs.register(mcp)
    selection.register(mcp)
    structures.register(mcp)
    target_contacts.register(mcp)
