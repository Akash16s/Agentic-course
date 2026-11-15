# Chapter 16 — MCP (Model Context Protocol)

**Time: ~5 hours** (40 min reading · 30 min examples · 3 hrs exercises · 50 min review)
**Prerequisite:** Chapters 1–15 green.

---

## After this chapter you can

- Explain what MCP is, and what it is not
- Read and write JSON-RPC 2.0 by hand
- Build an MCP server exposing tools, resources and prompts
- Build a client, and bridge remote tools into your Chapter 2 registry
- Point at the three mistakes that break stdio servers in practice

---

## 1. The one idea

**MCP is a standard way for an agent to discover and use tools it did not ship with.**

Without it, every integration is bespoke: your agent needs code for GitHub, code for
Postgres, code for Slack. With it, anyone can publish a server and any client can use
it.

```
   M clients x N integrations  =  M x N pieces of glue
   with a protocol             =  M + N
```

That is the entire value proposition, and it is the same one USB had.

### What it actually is

**JSON-RPC 2.0 plus an agreed list of method names.** That is it. Roughly:

```json
{"jsonrpc": "2.0", "id": 1, "method": "tools/call",
 "params": {"name": "add", "arguments": {"a": 2, "b": 3}}}
```

There is no new transport, no new serialisation, no magic. Once you see that, most of
the mystique goes.

### What it is not

- **Not required.** A tool in your own codebase should stay a Python function. MCP is
  for crossing a process or an organisation boundary.
- **Not a security model.** An MCP server runs code with whatever permissions you gave
  it. Chapter 14 applies unchanged, and a third-party MCP server is third-party code
  running on your machine.
- **Not free.** A subprocess, a handshake, serialisation, and a tool description
  written by someone who has never seen your agent.

**Use it when:** you want tools from someone else's codebase, you want your tools
usable by other people's clients, or you want tools in a different language or a
separate process with separate permissions.

## 2. JSON-RPC in ten minutes

Three message shapes:

**Request** — has `method` and an `id`, expects a reply.
**Response** — has that `id`, plus **exactly one** of `result` or `error`.
**Notification** — has `method` and **no `id`**. Fire and forget, no reply, ever.

> **The notification rule is the one people get wrong.** Replying to a notification
> confuses strict clients; failing to reply to a request hangs them. If you take one
> thing from this section, take that `id` is what distinguishes them.

Error codes are standard: `-32700` parse error, `-32600` invalid request, `-32601`
method not found, `-32602` invalid params, `-32603` internal error.

### Framing

Over stdio: **one JSON object per line, newline-terminated.** It works because
`json.dumps` escapes newlines inside strings, so a raw newline unambiguously ends a
message.

## 3. The handshake

```
client -> initialize                    (request: protocol version, client info)
server -> { protocolVersion, capabilities, serverInfo }
client -> notifications/initialized     (notification: no reply)
```

Two steps because the client may need to do work between learning what the server can
do and declaring itself ready. Skip the second and strict servers wait forever.

## 4. The three things a server offers

| | What | Controlled by | Analogy |
|---|---|---|---|
| **Tools** | Functions with side effects | the **model** | POST |
| **Resources** | Read-only context, addressed by URI | the **client** | GET |
| **Prompts** | Reusable templates | the **user** | a saved query |

The distinction is about *who decides to use it*. Tools are chosen by the model
mid-loop. Resources are attached by the client before the loop. Prompts are picked by
a human from a menu.

Most servers only implement tools, and that is fine.

### Tool failures are not protocol errors

```json
{"result": {"content": [{"type": "text", "text": "file not found"}],
            "isError": true}}
```

A tool that failed is a **successful call** that returned a failure. A JSON-RPC
`error` means "your request was malformed" — a different thing, and one the model
cannot act on. This is Chapter 2's rule, restated at the protocol level.

### One naming trap

MCP calls a tool's JSON Schema **`inputSchema`**. The OpenAI API calls the same object
**`parameters`**. Same schema, different key. That one-line rename is essentially the
whole of `bridge_tools`.

## 5. The bridge — why any of this matters

```python
client = MCPClient(subprocess_transport(["python", "my_server.py"]))
client.initialize()
registry = ToolRegistry(bridge_tools(client, prefix="calc_"))

agent = Agent(llm, tools=registry)     # Chapter 3, entirely unchanged
```

After `bridge_tools`, a remote tool is an ordinary `Tool`. Your loop, your registry,
your traces (Chapter 12), your permissions (Chapter 14) and your evals (Chapter 10)
all work on it without knowing a protocol exists.

**Use `prefix`.** The moment you connect two servers that both offer `search`, an
unprefixed registry raises on the duplicate — or worse, silently shadows one.

## 6. Three mistakes that break stdio servers

**1. Printing to stdout.** One stray `print()` — or a library that logs to stdout —
corrupts the JSON-RPC stream. The client reports a parse error that points nowhere
near the cause. **Log to stderr. Always.**

**2. Not flushing.** Buffered output means the client waits for a message that is
sitting in your process. `flush()` after every write, or run unbuffered.

**3. Dying on a malformed line.** Skip and log. A server that crashes on one bad line
is a server one stray byte can kill.

## 7. Security, briefly but seriously

Everything in Chapter 14 applies, plus:

- **A third-party MCP server is third-party code on your machine**, with your
  filesystem and your network. Read it, or run it in a container.
- **Tool descriptions come from the server**, and they go into your model's context.
  A malicious server can write whatever it likes there.
- **Namespace, and keep a permission policy per server.** The GitHub server should not
  inherit the filesystem server's permissions.
- **Tool results are untrusted input.** Wrap them (Chapter 14, §5).

## 7b. Beyond stdio: remote servers, auth, and A2A

You built the stdio transport, where the server is a subprocess on your machine. Most
real MCP servers people connect to today are **remote**: a URL, hosted by the vendor.
The JSON-RPC messages are exactly the same. What changes is how they travel and who
is allowed to send them.

### Streamable HTTP

The current remote transport is called **Streamable HTTP**. It uses one endpoint, for
example `https://example.com/mcp`:

- The client **POSTs** each JSON-RPC message to it.
- The server replies with either plain JSON (one response) or an **SSE stream**
  (Chapter 15) when it wants to send progress updates or several messages before the
  final result.
- The server can hand out a session id in a header (`Mcp-Session-Id`), and the client
  sends it back on every later request.

An older "HTTP + SSE" transport that used two endpoints has been replaced by this
one. You will still find it in older servers and tutorials. Your `MCPClient` does not
care which one is used: only the `transport` function changes, the protocol doesn't.

### Authorization

A stdio server runs as you, so it doesn't need to log you in. A remote server has to
know who is calling. The MCP spec uses **OAuth 2.1** for this: the client finds the
server's authorization server, the user logs in and agrees in a browser, and the
client gets a token it sends as `Authorization: Bearer ...`. Two rules worth knowing
even if a library does the OAuth dance for you:

- **No token passthrough.** A server must not accept a token that was issued for some
  other service and forward it upstream. That turns the server into a confused deputy.
  It should only accept tokens issued for itself.
- **Scope tokens narrowly.** A token that can read *and* delete a whole GitHub org is
  the blast radius from Chapter 14, now sitting on someone else's server.

### The rest of the protocol, briefly

Besides tools, resources and prompts, a few features go the **other way**, from
server to client:

| Feature | What it means |
|---|---|
| **Sampling** | The server asks the *client* to run an LLM call for it, so the server needs no model key of its own |
| **Elicitation** | The server asks the client to ask the *user* something, like "which repo?" |
| **Roots** | The client tells the server which directories it may work in |

Your client can say it doesn't support these. That's the point of the capabilities
you swap in the handshake (§3).

### A2A: agents talking to agents

MCP connects an agent to **tools and data**. **A2A** (Agent2Agent, started by Google
and now run under the Linux Foundation) connects an agent to **another agent**, often
one run by a different company, that you can't see inside. The core ideas:

- An **Agent Card**: a JSON document at a well-known URL that describes what the agent
  can do and how to authenticate. It works like `tools/list` for a whole agent.
- **Tasks** with a lifecycle (submitted → working → input-required → completed or
  failed), because a remote agent's work can take minutes and may need to ask
  questions along the way.
- **Messages and artifacts** for passing results back.

It is still JSON-RPC over HTTP, with SSE for streaming. Look at the shape: you have
built every piece already. The same advice as Chapter 8 applies: **if you control
both agents, a function call is simpler.** A2A only earns its place when the other
agent belongs to another team or another company.

## 8. Common mistakes

1. **Using MCP for your own in-process tools.** A function is simpler.
2. **Replying to a notification, or not replying to a request.**
3. **Returning a JSON-RPC error for a tool failure.** The model cannot act on it.
4. **Forgetting `inputSchema` vs `parameters`.**
5. **`print()` in a stdio server.**
6. **Not flushing stdout.**
7. **Crashing on a malformed line.**
8. **No prefix, then two servers with a `search`.**
9. **Trusting a third-party server's descriptions and results.**
10. **Assuming MCP adds security.** It adds surface.
11. **Forwarding a user's upstream token through your server.** Confused deputy.
12. **Reaching for A2A between two agents you own.** A function call is simpler.

## 9. Exercises

| # | File | Builds |
|---|---|---|
| 1 | `exercise_1_protocol.py` | `Request`, `Response`, `parse_message`, `encode`, `read_messages` |
| 2 | `exercise_2_server.py` | `MCPServer` — handshake, tools, resources, prompts |
| 3 | `exercise_3_client.py` | `MCPClient` — handshake and the method wrappers |
| 4 | `exercise_4_bridge.py` | `bridge_tools`, `in_memory_transport` |
| 5 | `exercise_5_real_mcp.py` | **Integration:** a real subprocess server, and a real third-party one |

```bash
pytest chapters/ch16_mcp/tests -q
```

## 10. Check yourself

1. What problem does MCP solve? State it as a multiplication.
2. What IS MCP, underneath?
3. What distinguishes a notification from a request, and what breaks if you confuse them?
4. Why is the handshake two steps?
5. Tools vs resources vs prompts — what is the real distinction?
6. A tool raises. What goes on the wire, and why not a JSON-RPC error?
7. What is the one-line translation between MCP and the OpenAI tool format?
8. After `bridge_tools`, what does your agent know about MCP?
9. Why does `prefix` matter?
10. Three ways to break a stdio server.
11. Name two security properties MCP does NOT give you.
12. When should you NOT use MCP?
13. What changes between stdio and Streamable HTTP, and what stays exactly the same?
14. MCP vs A2A: what does each one connect, and when do you need A2A at all?

---

**Next:** Chapter 17 — the frameworks, and the moment you realise you have already
written all of it.
