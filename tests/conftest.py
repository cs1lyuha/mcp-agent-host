"""Un server MCP mic, în memorie: notițe, cu un tool de citire și unul distructiv."""

import pytest
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp_types import ToolAnnotations


def make_notes_server(name: str = "notes"):
    notes = {"n1": "Livrarea standard costă 50 de lei.", "n2": "Returul: 30 de zile."}
    s = MCPServer(name)

    @s.tool(annotations=ToolAnnotations(read_only_hint=True))
    def search_notes(query: str) -> str:
        """Caută în notițe."""
        hits = [f"{k}: {v}" for k, v in notes.items() if query.lower() in v.lower()]
        return "\n".join(hits) or "nimic găsit"

    @s.tool(annotations=ToolAnnotations(read_only_hint=False, destructive_hint=True))
    def delete_note(note_id: str) -> str:
        """Șterge o notiță."""
        if note_id not in notes:
            raise ToolError(f"notița {note_id} nu există")
        del notes[note_id]
        return f"șters {note_id}"

    @s.tool()
    def big_dump() -> str:
        """Fără adnotări: tratat ca potențial distructiv."""
        return "x" * 20000

    s.notes = notes
    return s


@pytest.fixture
def notes_server():
    return make_notes_server()
