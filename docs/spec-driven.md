# v2: spec-driven changes with OpenSpec

v1 checks the code. v2 makes the agent agree **what** it is building before it writes code, and checks the result against that agreement. Every change goes through [OpenSpec](https://github.com/Fission-AI/OpenSpec): the agent proposes, the repo owner approves, the agent applies, and the change is archived into living specs that describe how the system behaves now.

| Piece | Where it runs | What it does | Files |
|---|---|---|---|
| OpenSpec | Claude Code (`/opsx:*`) and Codex (`$openspec-*`) | propose → apply → archive, with `explore` and `update` for thinking and revising | created by `openspec init` |
| Workflow rule | Every agent session | Every change goes through OpenSpec; stop after propose for approval; policy review and archive before the PR | `AGENTS.md` ("Specs and Workflows") |
| Project rules | Every proposal | Context and per-artifact rules OpenSpec adds to the agent's instructions | `openspec/config.yaml` |
| Policy review | Before the PR | Flags security and personal-data concerns for the owner | `.agents/skills/policy-review/` |
| Use-case skills | During apply | The order of work for a new use case, a model change and handler tests | `.agents/skills/create-usecase/`, `model-change/`, `handler-tests/` |
| Spec check | Claude hook before `gh pr create`, and CI on every PR | The branch has an OpenSpec change, and every changed file is named in its `design.md` or `tasks.md` (**plan matches diff**) | `scripts/spec-check.sh`, `.claude/hooks/spec-check-before-pr.sh`, `.github/workflows/spec-check.yml` |
| `no-spec` label | Hook and CI | The owner's way to skip the spec check for a change they say doesn't need a spec | label on the PR |

## Setup

1. **Install OpenSpec** (Node.js 22.12 or later) and set it up for both agents with the default profile:
   ```bash
   npm install -g @fission-ai/openspec
   openspec init --tools claude,codex
   ```
   OpenSpec collects anonymous usage data by default; set `OPENSPEC_TELEMETRY=0` to turn it off.
2. **Project rules:** copy the `context` and `rules` from `templates/openspec/config.yaml` into the `openspec/config.yaml` that `init` created, and fill in the placeholders.
3. **Instructions:** copy the "Specs and Workflows (OpenSpec)" section of `templates/AGENTS.md` into your `AGENTS.md`, and the Claude hook notes from `templates/CLAUDE.md`.
4. **Skills:** copy `.agents/skills/` (Codex reads it) and `.claude/skills/` (symlinks to the same folders, for Claude Code). Use `cp -R` so the symlinks stay symlinks. Fill in the `<placeholders>`, especially the personal-data list in `policy-review`.
5. **Spec check:** copy `scripts/spec-check.sh`, `.claude/hooks/spec-check-before-pr.sh`, the extra hook in `.claude/settings.json` and `.github/workflows/spec-check.yml`. Create a `no-spec` label in GitHub.
6. **PR template:** copy the "Spec" section from `templates/.github/pull_request_template.md`.
7. **Prove it fails** before trusting it: open a PR that changes code with no OpenSpec change, then one that changes a file the plan doesn't name. Both should fail.
8. Open the setup itself as a PR with the `no-spec` label.

## How a change goes through

1. Ask the agent for a feature or a fix in plain words. The `AGENTS.md` rule makes it start with **propose**, which writes `openspec/changes/<name>/`: `proposal.md` (why and what), `specs/` (requirements with scenarios), `design.md` (how) and `tasks.md` (steps, naming every file).
2. The agent stops. Review the files, ask questions, or have it revise them with `/opsx:update`. Nothing is built yet.
3. Approve, and it **applies** the tasks. The v1 checks (Stop hook, architecture tests, mutation check) still run.
4. Before the PR it runs **policy-review**, which writes `policy-review.md` into the change folder, then **archives** the change on the same branch, so the living spec in `openspec/specs/` lands with the code.
5. `gh pr create` runs the spec check and the mutation check. CI runs the spec check again with the build and tests.

See [`examples/add-order-note/`](examples/add-order-note/) for a complete change: proposal, spec, design, tasks and policy review.

## How the spec check works

`scripts/spec-check.sh` compares the branch with `origin/main`:

- **No code changed** (only OpenSpec files): passes.
- **Code changed, no OpenSpec change** on the branch, active or archived: fails.
- **A change folder is missing** `proposal.md`, `design.md`, `tasks.md` or a `specs/**/spec.md`: fails.
- **A changed file isn't named** in `design.md` or `tasks.md`: fails. A full path counts whatever the file type; a bare name like `Program.cs` matches any folder.
- **A file is named but not changed:** warning only, since plans often mention files they only read.

It is a cheap text match, not a review. It catches the agent quietly changing files it never planned to change, and changes with no plan at all. Whether the plan was good is still your call at the approval stop.

### Skipping it: `no-spec`

Some changes don't need a spec: a config tweak, a harness change, a typo. The owner says "this is a no-spec change", and the agent opens the PR with `gh pr create --label no-spec`. The Claude hook and CI both skip the spec check for that label; every other check still runs, and the skip stays visible on the PR. `AGENTS.md` tells agents never to add the label because the check failed.

Use `--label no-spec` as its own flag (`--label bug --label no-spec`, not `--label bug,no-spec`), or the hook won't see it. `gh` may add the label just after creating the PR, so CI can show one failed run before the labelled run replaces it.

An AI reviewer that reads `AGENTS.md` but not PR labels (such as Codex review) will flag a `no-spec` PR for having no OpenSpec change. The "Review guidelines" section in `templates/AGENTS.md` tells it to leave that to CI.

## Lessons from using this on a real codebase

- **Try the tool as designed first.** The same codebase shipped one feature with GitHub Spec Kit and one with OpenSpec, both with their default setups, before choosing. Spec Kit gives separate workflows for ideas, features and bugs with two approval stops; OpenSpec has one propose → apply → archive flow with one approval stop, and keeps living specs that archive updates. Customisation came after the choice, not before.
- **Instructions were enough to start the flow.** On the first change after setup, a plain "we need to work on a new feature…" led the agent through propose, the approval stop, apply, policy review and archive without OpenSpec being mentioned. The spec check is there for the times it doesn't.
- **Plan-matches-diff needs full paths.** The first version only recognised planned files with known extensions, so a planned `Dockerfile` or `.svg` failed with no way to fix it. The AI reviewer found it before it reached a real change.
- **On a private repo, CI checks can't block a merge** without GitHub Pro branch protection. The Claude hook blocks Claude; for Codex and manual PRs, a red spec check is a signal to the person merging, not a gate.
