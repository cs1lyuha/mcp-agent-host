import asyncio

from mcp import Client

from host.agent import Agent, Budget
from host.bridge import Bridge
from host.brains import ScriptedBrain, say, use


def run_agent(server, steps, question="?", approver=None, budget=None):
    async def go():
        async with Client(server) as c:
            bridge = Bridge()
            await bridge.add_server("notes", c)
            brain = ScriptedBrain(steps)
            kw = {"approver": approver} if approver else {}
            agent = Agent(brain, bridge, budget=budget, **kw)
            return await agent.ask(question), brain, agent
    return asyncio.run(go())


def test_read_only_tool_runs_without_approval(notes_server):
    res, brain, _ = run_agent(notes_server, [use(("notes__search_notes", {"query": "lei"})), say("Costă 50 de lei.")])
    assert res.answer == "Costă 50 de lei." and res.steps == 2
    tool_msg = brain.seen[1][-1]
    assert tool_msg["role"] == "user" and "<tool_output>" in tool_msg["content"][0]["content"]
    assert [e.kind for e in res.events] == ["tool_ok", "final"]


def test_destructive_tool_denied_by_default(notes_server):
    res, brain, _ = run_agent(notes_server, [use(("notes__delete_note", {"note_id": "n1"})), say("Nu am putut șterge.")])
    assert "n1" in notes_server.notes
    assert res.events[0].kind == "denied"
    assert brain.seen[1][-1]["content"][0]["is_error"] is True


def test_destructive_tool_with_approval(notes_server):
    asked = []

    async def approve(info, call):
        asked.append((info.name, call.input))
        return True

    res, _, _ = run_agent(notes_server, [use(("notes__delete_note", {"note_id": "n1"})), say("Șters.")],
                          approver=approve)
    assert "n1" not in notes_server.notes and asked == [("notes__delete_note", {"note_id": "n1"})]


def test_parallel_calls_one_user_message(notes_server):
    res, brain, _ = run_agent(notes_server, [use(("notes__search_notes", {"query": "lei"}),
                                                 ("notes__search_notes", {"query": "zile"})), say("Gata")])
    results = brain.seen[1][-1]["content"]
    assert [r["tool_use_id"] for r in results] == ["tu_0_notes__search_notes", "tu_1_notes__search_notes"]


def test_tool_error_goes_back_to_model(notes_server):
    async def approve(info, call):
        return True
    res, brain, _ = run_agent(notes_server, [use(("notes__delete_note", {"note_id": "n9"})), say("Nu există.")],
                              approver=approve)
    assert res.events[0].kind == "tool_error" and brain.seen[1][-1]["content"][0]["is_error"]


def test_max_steps_stops_a_looping_model(notes_server):
    loop = [use(("notes__search_notes", {"query": "x"})) for _ in range(10)]
    res, _, _ = run_agent(notes_server, loop, budget=Budget(max_steps=3))
    assert res.stop == "max_steps" and res.steps == 3


def test_max_tool_calls(notes_server):
    steps = [use(("notes__search_notes", {"query": "a"}), ("notes__search_notes", {"query": "b"})),
             use(("notes__search_notes", {"query": "c"}))]
    res, _, _ = run_agent(notes_server, steps, budget=Budget(max_tool_calls=2))
    assert res.stop == "max_tool_calls"


def test_output_token_budget(notes_server):
    res, _, _ = run_agent(notes_server, [use(("notes__search_notes", {"query": "a"}), tokens=900), say("x", tokens=900)],
                          budget=Budget(max_output_tokens=1000))
    assert res.stop == "max_output_tokens"


def test_history_is_append_only_across_questions(notes_server):
    async def go():
        async with Client(notes_server) as c:
            bridge = Bridge()
            await bridge.add_server("notes", c)
            brain = ScriptedBrain([say("Bună!"), say("Tot eu.")])
            agent = Agent(brain, bridge)
            await agent.ask("salut")
            first = [dict(m) for m in agent.history]
            await agent.ask("ce faci?")
            return first, agent.history
    first, after = asyncio.run(go())
    assert after[:len(first)] == first and len(after) == 4
