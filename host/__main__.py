"""CLI.

    python -m host demo                                  # scenariu scriptat (fără cheie API) pe serverul de exemplu
    python -m host chat --config examples/servers.json   # chat cu Claude; cere ANTHROPIC_API_KEY

Config-ul are același format ca la Claude Desktop: {"mcpServers": {"nume": {"command", "args", "env"}}}.
Tool-urile care nu sunt read-only cer confirmare în terminal ([d]a / [n]u).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from contextlib import AsyncExitStack
from pathlib import Path

from mcp import Client
from mcp.client.stdio import StdioServerParameters

from host.agent import Agent, Budget, ToolCall
from host.bridge import Bridge, ToolInfo

ROOT = Path(__file__).resolve().parent.parent


def load_config(path: str | Path) -> dict[str, StdioServerParameters]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    out = {}
    for name, spec in data["mcpServers"].items():
        command = sys.executable if spec["command"] in ("python", "python3") else spec["command"]
        out[name] = StdioServerParameters(command=command, args=spec.get("args", []),
                                          env={**os.environ, **spec.get("env", {})}, cwd=str(ROOT))
    return out


async def terminal_approver(info: ToolInfo, call: ToolCall) -> bool:
    kind = "DISTRUCTIV" if info.destructive else "scrie date"
    answer = await asyncio.to_thread(input, f"\n⚠️  {info.name} ({kind}) cu {json.dumps(call.input, ensure_ascii=False)}. Permiți? [d/N] ")
    return answer.strip().lower() in {"d", "da", "y", "yes"}


async def connect_all(stack: AsyncExitStack, config: dict[str, StdioServerParameters]) -> Bridge:
    bridge = Bridge()
    for name, params in config.items():
        client = await stack.enter_async_context(Client(params))
        tools = await bridge.add_server(name, client)
        print(f"🔌 {name}: {', '.join(t.remote_name + ('' if t.read_only else '*') for t in tools)}")
    print("   (* = cere aprobare)\n")
    return bridge


async def chat(config_path: str, model: str) -> None:  # pragma: no cover - interactiv
    from host.brains import ClaudeBrain
    async with AsyncExitStack() as stack:
        bridge = await connect_all(stack, load_config(config_path))
        agent = Agent(ClaudeBrain(model), bridge, approver=terminal_approver, budget=Budget())
        while True:
            try:
                question = await asyncio.to_thread(input, "tu › ")
            except (EOFError, KeyboardInterrupt):
                return
            if question.strip() in {"", "exit", "quit"}:
                return
            result = await agent.ask(question)
            for e in result.events:
                if e.kind != "final":
                    print(f"   · {e.kind} {e.tool} {e.detail[:80]}")
            print(f"agent › {result.answer}\n")


async def demo(approve: bool) -> int:
    from host.brains import ScriptedBrain, say, use

    async def scripted_approver(info, call):
        print(f"⚠️  aprobare cerută pentru {info.name} {call.input} → {'DA' if approve else 'NU'}")
        return approve

    async with AsyncExitStack() as stack:
        bridge = await connect_all(stack, load_config(ROOT / "examples/servers.json"))
        brain = ScriptedBrain([
            use(("notes__search_notes", {"query": "promo"}), text="Caut notița cu promoția."),
            use(("notes__delete_note", {"note_id": "promo-vechi"}), text="Promoția a expirat, o șterg."),
            lambda msgs: say("Am șters notița expirată." if "ștearsă" in json.dumps(msgs[-1], ensure_ascii=False)
                             else "Operatorul nu a aprobat ștergerea; notița rămâne."),
        ])
        agent = Agent(brain, bridge, approver=scripted_approver)
        result = await agent.ask("Curăță notițele expirate.")
        for e in result.events:
            print(f"· {e.kind:<10} {e.tool:<22} {e.detail[:70]}")
        print(f"\nagent › {result.answer}")
        return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="host")
    sub = p.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("demo")
    d.add_argument("--deny", action="store_true", help="operatorul refuză ștergerea")
    c = sub.add_parser("chat")
    c.add_argument("--config", default=str(ROOT / "examples/servers.json"))
    c.add_argument("--model", default="claude-opus-5-5")
    a = p.parse_args(argv)
    if a.cmd == "demo":
        return asyncio.run(demo(approve=not a.deny))
    asyncio.run(chat(a.config, a.model))
    return 0


if __name__ == "__main__":
    sys.exit(main())
