"""Server MCP de exemplu (stdio): notițe de suport, cu un tool read-only și unul distructiv.

    python examples/notes_server.py
"""

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp_types import ToolAnnotations

NOTES = {
    "livrare": "Livrarea standard costă 50 de lei; gratuită peste 1000 de lei.",
    "retur": "Returul se face în 30 de zile de la livrare.",
    "promo-vechi": "Promoția de vară (expirată în august).",
}

server = MCPServer("notes", instructions="Notițe interne ale echipei de suport.")


@server.tool(annotations=ToolAnnotations(read_only_hint=True))
def search_notes(query: str) -> str:
    """Caută în notițele echipei de suport după un cuvânt."""
    hits = [f"{k}: {v}" for k, v in NOTES.items() if query.lower() in (k + " " + v).lower()]
    return "\n".join(hits) or "nimic găsit"


@server.tool(annotations=ToolAnnotations(read_only_hint=False, destructive_hint=True))
def delete_note(note_id: str) -> str:
    """Șterge definitiv o notiță."""
    if note_id not in NOTES:
        raise ToolError(f"notița {note_id} nu există")
    del NOTES[note_id]
    return f"notița {note_id} a fost ștearsă"


if __name__ == "__main__":
    server.run("stdio")
