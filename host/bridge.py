"""Puntea MCP → tool-uri pentru model.

Un host MCP face trei lucruri pe care framework-urile le ascund:
1. **descoperă** tool-urile serverului (`tools/list`, cu paginare);
2. le **traduce** în formatul de tool-uri al API-ului de model (nume, descriere, JSON Schema);
3. **execută** apelurile modelului prin `tools/call` și întoarce rezultatul ca text.

Păstrăm și adnotările MCP (`readOnlyHint`, `destructiveHint`): pe ele se bazează politica
de aprobare. Adnotările vin de la server, deci sunt *indicii*, nu garanții: un server
necunoscut e tratat ca „orice tool poate scrie”, dacă nu e marcat explicit ca read-only.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

MAX_RESULT_CHARS = 8000


@dataclass
class ToolInfo:
    name: str            # numele expus modelului (cu prefixul serverului)
    server: str
    remote_name: str     # numele de pe server
    description: str
    input_schema: dict[str, Any]
    read_only: bool
    destructive: bool

    def to_model_tool(self) -> dict[str, Any]:
        return {"name": self.name, "description": self.description[:1024], "input_schema": self.input_schema}


@dataclass
class ToolResult:
    text: str
    is_error: bool
    truncated: bool = False


def safe_tool_name(server: str, tool: str) -> str:
    """Numele de tool la Claude: ^[a-zA-Z0-9_-]{1,64}$. Prefixul evită coliziuni între servere."""
    name = re.sub(r"[^a-zA-Z0-9_-]", "_", f"{server}__{tool}")
    return name[:64]


def _annotation(tool: Any, attr: str) -> bool | None:
    ann = getattr(tool, "annotations", None)
    return getattr(ann, attr, None) if ann is not None else None


@dataclass
class Bridge:
    """Ține clienții MCP (unul per server) și catalogul de tool-uri."""

    clients: dict[str, Any] = field(default_factory=dict)
    tools: dict[str, ToolInfo] = field(default_factory=dict)

    async def add_server(self, name: str, client: Any) -> list[ToolInfo]:
        self.clients[name] = client
        added, cursor = [], None
        while True:
            page = await client.list_tools(cursor=cursor) if cursor else await client.list_tools()
            for t in page.tools:
                info = ToolInfo(
                    name=safe_tool_name(name, t.name), server=name, remote_name=t.name,
                    description=t.description or "", input_schema=t.input_schema,
                    read_only=_annotation(t, "read_only_hint") is True,
                    destructive=_annotation(t, "destructive_hint") is not False and _annotation(t, "read_only_hint") is not True,
                )
                if info.name in self.tools:
                    raise ValueError(f"tool duplicat: {info.name}")
                self.tools[info.name] = info
                added.append(info)
            cursor = getattr(page, "next_cursor", None)
            if not cursor:
                return added

    def model_tools(self) -> list[dict[str, Any]]:
        # ordine stabilă: o schimbare de ordine ar invalida prompt cache-ul
        return [self.tools[n].to_model_tool() for n in sorted(self.tools)]

    async def call(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        info = self.tools.get(name)
        if info is None:
            return ToolResult(f"Tool necunoscut: {name}. Disponibile: {', '.join(sorted(self.tools))}", True)
        try:
            result = await self.clients[info.server].call_tool(info.remote_name, arguments)
        except Exception as err:  # transport căzut, timeout: modelul primește eroarea și poate decide
            return ToolResult(f"Eroare la apelul {info.remote_name}: {type(err).__name__}: {err}", True)
        parts = []
        for block in result.content:
            if getattr(block, "type", "") == "text":
                parts.append(block.text)
            else:
                parts.append(f"[conținut {getattr(block, 'type', '?')} omis]")
        if not parts and getattr(result, "structured_content", None) is not None:
            parts.append(json.dumps(result.structured_content, ensure_ascii=False))
        text = "\n".join(parts) or "(rezultat gol)"
        truncated = len(text) > MAX_RESULT_CHARS
        if truncated:
            text = text[:MAX_RESULT_CHARS] + f"\n…[trunchiat, {len(text) - MAX_RESULT_CHARS} caractere omise]"
        return ToolResult(text, bool(result.is_error), truncated)
