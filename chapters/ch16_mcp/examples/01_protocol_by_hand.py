"""MCP on the wire, and the bridge that makes it invisible. Free and offline.

    python chapters/ch16_mcp/examples/01_protocol_by_hand.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from agentlib.agent import Agent
from agentlib.mcp.client import MCPClient, bridge_tools, in_memory_transport
from agentlib.mcp.protocol import Request, encode, parse_message
from agentlib.mcp.server import MCPServer, Resource
from agentlib.testing import FakeLLMClient, tool_call, tool_response
from agentlib.tools import ToolRegistry, tool


@tool
def add(a: int, b: int) -> int:
    """Add two numbers together.

    Args:
        a: The first number.
        b: The second number.
    """
    return a + b


@tool
def divide(a: float, b: float) -> float:
    """Divide a by b.

    Args:
        a: Numerator.
        b: Denominator.
    """
    return a / b


server = MCPServer("calculator", version="1.0.0")
server.add_tool(add)
server.add_tool(divide)
server.add_resource(Resource(uri="calc://readme", name="readme",
                             read=lambda: "A calculator server."))

print("=" * 76)
print("1. EVERY BYTE OF A SESSION")
print("=" * 76)

conversation = [
    Request("initialize", {"protocolVersion": "2025-06-18",
                           "clientInfo": {"name": "demo"}}, id=1),
    Request("notifications/initialized"),                    # no id -> no reply
    Request("tools/list", id=2),
    Request("tools/call", {"name": "add", "arguments": {"a": 2, "b": 3}}, id=3),
    Request("tools/call", {"name": "divide", "arguments": {"a": 1, "b": 0}}, id=4),
    Request("tools/call", {"name": "imaginary"}, id=5),
]

for request in conversation:
    line = encode(request).strip()
    print(f"\n  -> {line[:104]}")
    response = server.handle(request)
    if response is None:
        print("  <- (nothing: it was a notification, and replying would be a "
              "protocol violation)")
        continue
    print(f"  <- {encode(response).strip()[:104]}")

print("\n" + "=" * 76)
print("2. THE TWO FAILURE KINDS, SIDE BY SIDE")
print("=" * 76)

divide_by_zero = server.handle(
    Request("tools/call", {"name": "divide", "arguments": {"a": 1, "b": 0}}, id=1))
unknown_tool = server.handle(
    Request("tools/call", {"name": "imaginary"}, id=2))

print(f"  tool raised     : ok={divide_by_zero.ok}   "
      f"isError={divide_by_zero.result['isError']}")
print(f"                    text={divide_by_zero.result['content'][0]['text']!r}")
print(f"  unknown tool    : ok={unknown_tool.ok}  "
      f"error={unknown_tool.error['message']!r}")
print("""
  A tool that RAISED is a SUCCESSFUL call that returned a failure — the model
  reads it and recovers, exactly as in Chapter 2. A JSON-RPC error means "your
  request was malformed", which is a different thing and one the model cannot
  act on. Returning the wrong one of these is a common MCP bug and it makes an
  agent brittle for no reason.""")

print("\n" + "=" * 76)
print("3. inputSchema vs parameters — the whole translation")
print("=" * 76)

client = MCPClient(in_memory_transport(server))
client.initialize()
mcp_spec = client.list_tools()[0]
print("  MCP says:")
print("   ", json.dumps({k: mcp_spec[k] for k in ("name", "description")})[:70])
print("    inputSchema:", json.dumps(mcp_spec["inputSchema"])[:70], "...")

bridged = bridge_tools(client, prefix="calc_")
openai_spec = bridged[0].spec()
print("\n  The OpenAI API wants:")
print("    parameters :", json.dumps(openai_spec["function"]["parameters"])[:70], "...")
print("\n  Same JSON Schema, different key. That rename IS bridge_tools.")

print("\n" + "=" * 76)
print("4. THE PAYOFF: the agent never finds out")
print("=" * 76)

registry = ToolRegistry(bridged)
fake = FakeLLMClient([
    tool_response(tool_call("calc_add", {"a": 7, "b": 8})),
    "The answer is 15.",
])
result = Agent(fake, tools=registry).run("what is 7 plus 8?")

print(f"  registry      : {registry.names}")
print(f"  agent output  : {result.output}")
print(f"  tool sequence : {result.tool_sequence}")
print("""
  That tool call crossed a protocol boundary, was serialised to JSON-RPC,
  dispatched by a server, executed, and serialised back. Your Chapter 3 loop,
  your registry, your traces, your permissions and your evals all worked
  unchanged and none of them know.

  That is the entire value proposition, and it is why `prefix` matters: connect
  two servers that both offer `search` and an unprefixed registry raises on the
  duplicate. Which is the GOOD outcome — silently shadowing one would be worse.""")
