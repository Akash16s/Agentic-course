# Chapter 14 — Security & Safety

**Prerequisite:** Chapters 1–13 green.

---

## After this chapter you can

- Explain why prompt injection is a structural property, not a fixable bug
- Build a default-deny permission layer over your tools
- Write a path sandbox that holds up against real traversal attempts
- Delimit untrusted content, and say honestly what that does and doesn't buy
- Design a human-in-the-loop gate a human can actually make a decision at
- Reason about **blast radius** instead of about detection

---

## 1. The one idea

**A model cannot reliably distinguish your instructions from instructions that arrive
inside data it reads.**

That is not a bug in a particular model. It is what a language model *is*: a function
over one undifferentiated sequence of tokens. Your system prompt and the contents of a
web page occupy the same space, and "which of these should I obey" is a judgement the
architecture does not support making reliably.

The consequence, and the single most important sentence in this chapter:

> **You cannot detect your way out of this. Design so that a successful injection
> cannot do much.**

**Blast radius, not detection.** That framing is what separates people who have
thought about this from people who added a regex and moved on.

## 2. The threat model

Two shapes, and the second is the one that matters.

**Direct.** The user types something adversarial into their own session. Mostly a
nuisance — they are attacking themselves. Relevant if your system prompt is a trade
secret, or if their session can touch other people's data.

**Indirect.** The adversarial text arrives inside *content the agent reads*: a web
page, a PDF, a support ticket, a code comment, a calendar invite, a filename, a commit
message. The user is not attacking you; a third party is, through them.

This is the real risk because it composes badly with everything you have built:

```
   agent reads untrusted content  →  content influences the agent
        →  agent calls a tool  →  tool has real-world effect
```

An agent that can read the public internet *and* send email *and* read your database
is one hostile document away from being a data exfiltration service. None of the three
capabilities is dangerous alone.

**The lethal trifecta** to watch for in any design review:

1. access to private data, **and**
2. exposure to untrusted content, **and**
3. the ability to communicate outward.

Remove any one and the exfiltration path closes. That is usually far cheaper than
trying to make the model robust.

## 3. Defence 1 — permissions (the one that actually works)

Default deny. The agent may do exactly what you listed, and nothing else.

```python
policy = (PermissionPolicy()
    .deny("read_file", when=lambda a: "secret" in str(a.get("path", "")))
    .allow("read_*")
    .allow("list_*")
    .ask("send_email")
    .deny("delete_*"))
```

Four things to get right:

- **Default deny, not default allow.** With default-allow, every tool anyone adds
  later is live in production the moment it is registered — including the one written
  in a hurry on a Friday.
- **First match wins, so order matters.** The specific `deny` goes *before* the broad
  `allow`, which is how "all reads except secrets" becomes expressible.
- **Predicates on arguments, not just names.** `send_email` to a colleague and
  `send_email` to an arbitrary external address are different operations.
- **A denial is a tool result, not an exception.** The model should see
  `permission denied` and route around it — exactly like any other tool failure from
  Chapter 2. Crashing the run tells the user nothing and loses the trace.

**Scope permissions per context.** The agent handling untrusted input should have a
smaller toolset than the one handling your own. This is the practical form of the
trifecta rule, and it is usually a ten-line change.

## 4. Defence 2 — sandboxing

Any tool taking a path, a URL, a query or a command needs a boundary.

### Paths

```python
def sandbox_path(root, candidate) -> Path:
    root_path = Path(root).resolve()
    target = (root_path / candidate).resolve()
    if target != root_path and root_path not in target.parents:
        raise PathEscape(...)
    return target
```

**`.resolve()` before comparing is the whole trick.** It collapses `..`, expands
symlinks and normalises separators, so you are comparing real locations rather than
strings. String-based checks ("does it contain `..`?") are bypassable and everyone who
has tried has eventually found out how.

Note that `Path(root) / "/absolute/path"` yields the absolute path — pathlib lets an
absolute component win. Resolving and then checking containment catches that too.

### Everything else, same shape

- **Shell:** don't. Call the program directly with an argument list, never a string
  through a shell. If you must have a shell, that agent gets its own container.
- **SQL:** parameterised queries and a read-only role. Never string interpolation.
- **HTTP:** an allowlist of hosts. Block private address ranges and the cloud metadata
  endpoint — an agent that fetches URLs is otherwise a request forgery primitive.
- **Code execution:** a real sandbox (container, gVisor, Firecracker, WASM), no
  network, a memory cap, a wall-clock cap. `exec()` in your own process is not a
  sandbox, and neither is a blocklist of dangerous builtins.

### Bound the output too

A tool that can return 500MB can exhaust your context, your memory and your budget
without any adversary involved. Chapter 4's `middle_out` belongs on every tool result.

## 5. Defence 3 — delimiting untrusted content

Mark data as data:

```python
wrap_untrusted(page_text, source="example.com")
```

which produces a clearly-fenced block stating that the contents are retrieved data,
not instructions, and should not be obeyed.

**What this buys you:** measurably fewer successful injections, for a handful of
tokens. Worth doing on every piece of retrieved content.

**What it does not buy you:** safety. The model can still be persuaded, and content
can contain the closing marker (strip it — a one-line `re.sub` defeats the cheapest
version). This raises the bar. It does not close the hole, and if you find yourself
relying on it, go back to section 3.

## 6. Detection: telemetry, never a control

`detect_injection` scans for known-suspicious patterns — instruction-override phrasing,
role reassignment, fake conversation turns, delimiter breaking, exfiltration shapes,
requests for secrets — after folding unicode tricks with NFKC.

Be clear-eyed about what that is worth. Every one of those patterns fails against
rephrasing, translation, encoding, or splitting the text across a document. It catches
the careless and misses the deliberate.

**So use it for:**
- alerting and dashboards ("injection attempts tripled this week")
- deciding when to escalate a call to a human
- logging, so you have evidence after an incident

**Never for:** being the thing that stands between an attacker and your database. The
controls are permissions and sandboxing. Detection is a smoke alarm, not a fire door.

## 7. Human in the loop

For anything irreversible: money, deletion, outbound communication, production
changes.

The design failure is almost never "we forgot to ask". It is **asking in a way nobody
can answer**:

```
BAD    Approve send_email? [y/N]
GOOD   Send an email to 412 recipients
         subject: "Your account has been closed"
         from:    billing@acme.com
       Approve? [y/N]
```

A human approving the first one has not made a decision, they have pressed a key. If
you ask forty times an hour, they will approve everything by reflex — so **ask rarely
and make each one count**: approve a *plan*, not each step; batch related actions;
remember a decision for the session.

## 8. Other things that will bite

- **Secrets in prompts.** Never put a key in a system prompt "so the agent can use
  it". Tools hold credentials; the agent names a tool.
- **PII in logs and traces.** Chapter 9's `RedactPII` belongs on the tracing path
  (Chapter 12), not just on the output path.
- **Tool results are untrusted too.** An API response is data from outside. Wrap it.
- **Denial of wallet.** A loop that costs money *is* an availability attack. Chapter
  13's budget guard is a security control, not just a finance one.
- **Confused deputy.** Your agent has permissions the user doesn't. Check what *the
  user* may do, not only what the agent may do.
- **Multi-agent trust.** One agent's output is another's untrusted input. Chapter 8's
  boundaries are also security boundaries.

## 9. Common mistakes

1. **Trying to detect your way to safety.** Design for blast radius.
2. **Default-allow permissions.** Every future tool ships enabled.
3. **Broad `allow` before specific `deny`.** First match wins; your exception never
   fires.
4. **Permissions on tool names only.** The arguments are where the damage lives.
5. **A denial that crashes the run** instead of becoming a tool result.
6. **String-based path checks.** Resolve, then compare.
7. **Building a shell tool.** Call programs directly, with an argument list.
8. **`exec()` as a "sandbox".**
9. **Unbounded tool output.**
10. **An HTTP tool with no allowlist.** Now you have request forgery.
11. **Treating tool results as trusted.**
12. **Approval prompts nobody can evaluate**, asked often enough to be reflexive.
13. **Secrets in the system prompt.**
14. **All three of the trifecta in one agent** because splitting it felt like effort.

## 10. Exercises

| # | File | Builds |
|---|---|---|
| 1 | `exercise_1_permissions.py` | `Decision`, `Rule`, `PermissionPolicy`, `GuardedRegistry` |
| 2 | `exercise_2_sandbox.py` | `sandbox_path`, `safe_join` |
| 3 | `exercise_3_detection.py` | `normalise_for_detection`, `detect_injection`, `wrap_untrusted` |
| 4 | `exercise_4_approval.py` | `ApprovalQueue` — and a description a human can judge |
| 5 | `exercise_5_redteam.py` | **Integration:** attack your own agent, then fix the design |

```bash
pytest chapters/ch14_security/tests -q
```

## 11. Check yourself

1. Why is prompt injection structural rather than a bug to be patched?
2. What does "blast radius, not detection" mean in practice?
3. Name the three capabilities of the lethal trifecta. Why is removing one enough?
4. Why default deny? What happens six months later with default allow?
5. Why does rule ORDER matter, and which way round do specific rules go?
6. Why must a permission denial be a tool result rather than an exception?
7. What does `.resolve()` do, and why is a string check on `..` not enough?
8. Why is `Path(root) / "/etc/passwd"` a problem, and what catches it?
9. What does delimiting untrusted content buy you, and what does it not?
10. Three legitimate uses for injection detection, and the one illegitimate one.
11. What makes an approval prompt useless? Give a good and a bad example.
12. Why is a runaway cost loop a security issue?
13. Your agent can read the web, read your database, and send email. What do you change?

---

**Next:** Chapter 15 — putting all of this behind an HTTP API that more than one
person can use at once.
