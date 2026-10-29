"""„Creierele”: Claude (real) și un model scriptat pentru teste."""

from __future__ import annotations

from typing import Any, Callable

from host.agent import ToolCall, Turn


class ClaudeBrain:  # pragma: no cover - cere cheie API
    def __init__(self, model: str = "claude-opus-5-5", client: Any = None, effort: str = "medium") -> None:
        import anthropic
        self.client = client or anthropic.AsyncAnthropic()
        self.model = model
        self.effort = effort

    async def next(self, system, messages, tools) -> Turn:
        msg = await self.client.messages.create(
            model=self.model, max_tokens=16000, system=system, tools=tools, messages=messages,
            output_config={"effort": self.effort},
        )
        text = "".join(b.text for b in msg.content if b.type == "text")
        calls = [ToolCall(b.id, b.name, dict(b.input)) for b in msg.content if b.type == "tool_use"]
        # conținutul se trimite înapoi neschimbat (inclusiv thinking), ca istoricul să rămână append-only
        raw = [b.to_dict() for b in msg.content]
        return Turn(text, calls, msg.stop_reason, raw, msg.usage.output_tokens)


class ScriptedBrain:
    """Primește o listă de pași; fiecare pas e un Turn sau o funcție (messages) -> Turn."""

    def __init__(self, steps: list[Turn | Callable[[list[dict[str, Any]]], Turn]]) -> None:
        self.steps = list(steps)
        self.seen: list[list[dict[str, Any]]] = []

    async def next(self, system, messages, tools) -> Turn:
        self.seen.append(messages)
        if not self.steps:
            raise AssertionError("ScriptedBrain: nu mai sunt pași")
        step = self.steps.pop(0)
        return step(messages) if callable(step) else step


def say(text: str, tokens: int = 50) -> Turn:
    return Turn(text, [], "end_turn", [{"type": "text", "text": text}], tokens)


def use(*calls: tuple[str, dict[str, Any]], text: str = "", tokens: int = 50) -> Turn:
    tool_calls = [ToolCall(f"tu_{i}_{name}", name, args) for i, (name, args) in enumerate(calls)]
    raw = ([{"type": "text", "text": text}] if text else []) + [
        {"type": "tool_use", "id": c.id, "name": c.name, "input": c.input} for c in tool_calls]
    return Turn(text, tool_calls, "tool_use", raw, tokens)
