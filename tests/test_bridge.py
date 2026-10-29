import asyncio

from mcp import Client

from host.bridge import Bridge, safe_tool_name


def run(coro):
    return asyncio.run(coro)


def test_discovery_annotations_and_schema(notes_server):
    async def go():
        async with Client(notes_server) as c:
            b = Bridge()
            await b.add_server("notes", c)
            return b
    b = run(go())
    assert sorted(b.tools) == ["notes__big_dump", "notes__delete_note", "notes__search_notes"]
    assert b.tools["notes__search_notes"].read_only and not b.tools["notes__search_notes"].destructive
    assert b.tools["notes__delete_note"].destructive
    assert b.tools["notes__big_dump"].destructive  # fără adnotări → presupunem că poate scrie
    tool = b.model_tools()[2]
    assert tool["name"] == "notes__search_notes" and tool["input_schema"]["properties"]["query"]["type"] == "string"


def test_call_ok_error_unknown_and_truncation(notes_server):
    async def go():
        async with Client(notes_server) as c:
            b = Bridge()
            await b.add_server("notes", c)
            return (await b.call("notes__search_notes", {"query": "lei"}),
                    await b.call("notes__delete_note", {"note_id": "n9"}),
                    await b.call("notes__nope", {}),
                    await b.call("notes__big_dump", {}))
    ok, err, unknown, big = run(go())
    assert "50 de lei" in ok.text and not ok.is_error
    assert err.is_error and "n9" in err.text
    assert unknown.is_error and "Disponibile" in unknown.text
    assert big.truncated and len(big.text) < 8200


def test_safe_names():
    assert safe_tool_name("tech nova", "get.order") == "tech_nova__get_order"
    assert len(safe_tool_name("s" * 50, "t" * 50)) == 64
