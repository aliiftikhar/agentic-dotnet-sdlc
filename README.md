# agentic-dotnet-sdlc

A starter kit for running an **agentic software development lifecycle** in a .NET repository: coding agents (Codex, Claude Code) work on branches and open pull requests, CI checks every PR, an AI reviewer comments, and a human merges.

Everything here has been used on a real production .NET SaaS before being added. The kit grows one tested step at a time.

## What's in v0

| Path | What it is |
|------|------------|
| `templates/AGENTS.md` | Root instructions for every coding agent: code style, build/test/verify, git workflow, migrations |
| `templates/project-AGENTS.md` | Per-project conventions (one per project folder), including **Code Review Rules** for the AI reviewer |
| `templates/CLAUDE.md` | One line (`@AGENTS.md`) so Claude Code reads the same instructions as Codex |
| `templates/.github/ISSUE_TEMPLATE/change-request.md` | Issue template for writing requirements with acceptance criteria |
| `templates/.github/pull_request_template.md` | PR template: what changed, which agent made it, how it was verified, migration needed? |
| `templates/.github/workflows/dotnet-pr.yml` | CI: build and run unit tests on every pull request |
| `docs/codex-review.md` | Setting up automatic Codex review on GitHub, and what to do when it doesn't respond |

## The loop

```
Issue (requirements) → agent works on a branch → PR (template) → CI builds + tests → AI review → you merge
```

## Using it today

1. Copy `templates/` into the root of your repository.
2. Replace the `<placeholders>` with your project names and commands, and **run every build and test command** to check it works.
3. Copy `project-AGENTS.md` into each project folder as `AGENTS.md`, with a `CLAUDE.md` next to it.
4. Set up the AI reviewer (see `docs/codex-review.md`).
5. Put the setup itself through the loop as your first PR.

## Roadmap

- **v1:** checks agents can't skip: architecture tests, CI for every project, mutation testing
- **v2:** spec-driven changes and reusable agent skills
- **v3:** agents picking up issues and opening draft PRs
- Install with an agent skill instead of copying files, a reusable CI workflow, and a NuGet package for the checks

## License

MIT
