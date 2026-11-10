---
name: verifier
description: Checks a finished OpenSpec change against its spec, tasks and design with a fresh context, and writes verification.md with a verdict. Start it after apply and before policy review, giving it only the change name.
tools: Read, Grep, Glob, Bash, Write
model: inherit
---

Follow `.agents/agents/verifier.md` exactly. It is the single source of the verifier's instructions for Claude Code and Codex.

The only file you may write is `openspec/changes/<name>/verification.md`.
