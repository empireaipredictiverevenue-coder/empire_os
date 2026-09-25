# Architecture Delta — Pi Local Tool-Calling Compatibility

Date: 2026-09-25
Status: REQUIRED

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
