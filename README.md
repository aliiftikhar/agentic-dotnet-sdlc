# agentic-dotnet-sdlc

A starter kit for running an **agentic software development lifecycle** in a .NET repository: coding agents (Codex, Claude Code) work on branches and open pull requests, checks run at every step, an AI reviewer comments, and a human merges.

Everything here has been used on a real production .NET SaaS before being added. The kit grows one tested step at a time.

## The loop

```
Request → agent proposes a spec → you approve → agent builds on a branch → checks (hooks, tests, mutation, spec matches diff) → PR → CI → AI review → you merge
```

## What's in it

### v0: the loop

| Path | What it is |
|------|------------|
| `templates/AGENTS.md` | Root instructions for every coding agent: code style, build/test/verify, mutation check, git workflow, migrations |
| `templates/project-AGENTS.md` | Per-project conventions, architecture tests and **Code Review Rules** for the AI reviewer |
| `templates/CLAUDE.md` | `@AGENTS.md`, so Claude Code reads the same instructions as Codex, plus Claude hook notes |
| `templates/.github/ISSUE_TEMPLATE/change-request.md` | Issue template for requirements with acceptance criteria |
| `templates/.github/pull_request_template.md` | PR template: what changed, which agent made it, verification, mutation check, migration needed? |
| `docs/codex-review.md` | Setting up automatic Codex review on GitHub, and what to do when it doesn't respond |

### v1: rules that are checked, not just written

| Path | What it is |
|------|------------|
| `templates/.githooks/` | Block commits, merge commits and pushes to `main` |
| `templates/.github/workflows/ci.yml` | Build every deployable project and run the unit tests on every PR |
| `templates/.claude/` | Claude Code hooks: build and test before finishing; mutation check before `gh pr create` |
| `templates/tests/ArchitectureTests.cs` | Use cases don't import each other, every handler has tests, every endpoint requires auth |
| `templates/scripts/mutation-check.sh`, `templates/tests/stryker-config.json`, `templates/.config/dotnet-tools.json` | Stryker.NET on changed code only; 0 surviving mutants required before a PR |
| `docs/enforced-checks.md` | How the layers fit together, setup steps, and lessons learned |

### v2: spec-driven changes and skills

| Path | What it is |
|------|------------|
| `templates/AGENTS.md` ("Specs and Workflows") | Every change goes through [OpenSpec](https://github.com/Fission-AI/OpenSpec): propose, owner approval, apply, policy review, archive; `no-spec` for changes the owner exempts |
| `templates/openspec/config.yaml` | Project context and rules OpenSpec adds to every proposal, design and task list |
| `templates/.agents/skills/` | Skills for Codex and Claude Code: `policy-review` (security and personal data), `create-usecase`, `model-change`, `handler-tests` |
| `templates/.claude/skills/` | Symlinks to the same skills, so Claude Code reads them too |
| `templates/scripts/spec-check.sh`, `templates/.claude/hooks/spec-check-before-pr.sh`, `templates/.github/workflows/spec-check.yml` | Spec check: code changes need an OpenSpec change, and every changed file must be named in its plan |
| `docs/spec-driven.md` | Setup, how a change goes through, how the spec check works, and lessons learned |
| `docs/examples/add-order-note/` | A complete worked change: proposal, spec, design, tasks and policy review |

## Using it today

1. Copy `templates/` into the root of your repository (put `tests/` files into your unit test project).
2. Replace the `<placeholders>` with your project names and commands, and **run every build, test and check** to make sure it works.
3. Copy `project-AGENTS.md` into each project folder as `AGENTS.md`, with a `CLAUDE.md` next to it.
4. Set up the AI reviewer (`docs/codex-review.md`), the checks (`docs/enforced-checks.md`) and OpenSpec (`docs/spec-driven.md`).
5. Put the setup itself through the loop as your first PR.

## Roadmap

- **v3:** agents picking up issues and opening draft PRs
- Install with an agent skill instead of copying files, a reusable CI workflow, and a NuGet package for the architecture checks

## License

MIT
