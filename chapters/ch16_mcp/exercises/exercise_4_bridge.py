"""EXERCISE 4 — The bridge. This is the payoff of the whole chapter.

    pytest chapters/ch16_mcp/tests -q -k bridge
"""

from __future__ import annotations

from typing import Any, Callable

from .exercise_1_protocol import Request, encode, parse_message
from .exercise_3_client import MCPClient


def in_memory_transport(server: Any) -> Callable[[str], str | None]:
    """Wire a client straight to a server object. No process, no sockets.

    Spec:
        parse the line; not a Request -> None
        response = server.handle(request)
        return encode(response) if response is not None else None

    Returning None for notifications is not a shortcut — it is the protocol.
    """
    # TODO: implement
    raise NotImplementedError


def bridge_tools(client: MCPClient, *, prefix: str = "") -> list[Any]:
    """Turn a remote server's tools into ordinary `agentlib` Tools.

    Spec — for each spec from `client.list_tools()`:
        Tool(
            name        = f"{prefix}{spec['name']}",
            description = spec.get("description", ""),
            parameters  = spec.get("inputSchema") or
                          {"type": "object", "properties": {}},
            func        = a callable that does client.call_tool(remote_name, kwargs),
        )

    TWO THINGS TO GET RIGHT:

    1. `inputSchema` -> `parameters`. That rename is essentially the entire
       translation between MCP and the OpenAI tool format. Same JSON Schema.

    2. THE CLOSURE. Build the callable in a factory function:

           def make_caller(remote_name):
               def call(**arguments):
                   return client.call_tool(remote_name, arguments)
               return call

       Writing `lambda **kw: client.call_tool(name, kw)` inside the loop captures
       the VARIABLE `name`, not its value — every bridged tool ends up calling
       whichever tool happened to be last. It is the classic Python late-binding
       bug and it produces an agent that mysteriously always calls the same thing.

    AFTER THIS, your Chapter 3 agent uses remote tools with no idea a protocol,
    a subprocess or a network is involved. Registry, loop, traces, permissions and
    evals all work unchanged. That is the whole point of MCP.

    `prefix` namespaces them. The moment you connect two servers that both offer
    a `search`, an unprefixed registry raises on the duplicate — which is the good
    outcome; silently shadowing one would be worse.
    """
    # TODO: implement
    raise NotImplementedError
