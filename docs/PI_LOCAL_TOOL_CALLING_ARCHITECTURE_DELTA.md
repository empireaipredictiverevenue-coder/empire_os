# Architecture Delta — Pi Local Tool-Calling Compatibility

Date: 2026-09-25
Status: NOT PROMOTED / EVIDENCE CLOSED

## Problem

Pi runtime and sandbox execution are healthy, but the local qwen2.5-coder:1.5b lane
returned textual pseudo-tool calls instead of executing Pi built-in tools. Because
zero changed files were previously treated as COMPLETED_NO_CHANGES, implementation
jobs could appear successful without implementation.

## Architectural correction

1. llama.cpp must start with `--jinja` so compatible chat templates/tool calling
   are rendered by the local inference server.
2. Pi must run in JSON event mode.
3. Empire records real `tool_execution_start` events as execution evidence.
4. Mutating implementation jobs default to `require_changes=True`.
5. Zero changed files on a mutating implementation job becomes `NO_IMPLEMENTATION`.
6. Read-only smoke jobs may explicitly set `require_changes=False`.
7. No promotion occurs from textual pseudo-tool calls.
8. Existing lease, sandbox, secret stripping, localhost-only networking, changed-path
   enforcement, focused tests and independent proposal verification remain unchanged.

## Promotion rule

Pi may be considered an implementation-capable worker on the local model only after
a live mutation smoke proves at least one genuine Pi tool execution and a bounded
file change inside the disposable clone.

If the local model still cannot produce real tool calls after `--jinja`, it is
demoted to non-mutating analysis/boilerplate use and implementation work routes to
another eligible coding lane.


## Structured capability probe

Before any mutating Pi job is allowed to execute, Empire probes
`/v1/chat/completions` with one inert function schema and requires a real
`message.tool_calls` structure.

Textual JSON, fenced JSON, prose describing a tool call, or a zero-change result
does not count as tool-call capability.

The local llama.cpp service uses the documented `chatml` fallback template in
addition to `--jinja`. If the structured probe still fails, the local 1.5B model
is analysis-only and mutating work routes to another eligible builder.


## Qwen native tool-use template correction — 2026-09-25

Observed runtime evidence showed that `--jinja --chat-template chatml` allowed the
Qwen2.5-Coder model to emit JSON-looking tool requests as ordinary assistant text,
but llama.cpp did not surface OpenAI-compatible `message.tool_calls`.

Architecture correction:
- vendor the upstream Qwen 2.5 tool-use Jinja template in EmpireOS;
- start llama-server with `--jinja --chat-template-file ...Qwen...jinja`;
- require the direct structured tool-call probe to return a real
  `message.tool_calls[]` entry with valid JSON arguments;
- only after that probe passes may Pi run a mutation smoke;
- only after the mutation smoke changes exactly the permitted disposable path may
  Pi be promoted to bounded IMPLEMENT jobs;
- plain text containing JSON, XML, pseudo-tool syntax or tool names does not count
  as tool execution and must not be promoted.

The inference server remains loopback-only. This delta grants no production,
outbound, payment, revenue-recognition or authority-expansion capability.


## Live conclusion — 2026-09-25

The live qwen2.5-coder:1.5b lane repeatedly returned textual/pseudo tool calls
instead of OpenAI-compatible `message.tool_calls`. A custom Qwen tool-use Jinja
template did not change the direct structured capability result.

Therefore:
- Pi remains installed and healthy;
- Pi remains useful for non-mutating analysis/sandbox work;
- native Pi mutation is NOT promoted on this model;
- the active llama.cpp service uses the proven `chatml` runtime template;
- mutating work fails over only to a separately proven builder capability;
- the experimental Qwen tool-use template remains evidence/reference, not an
  active authority or production-capability claim.
