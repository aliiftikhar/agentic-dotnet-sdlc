# Project Instructions

Always read `README.md` first to understand the solution structure and project types before making changes.

Projects with their own conventions have an `AGENTS.md` in their folder. Read it before changing files in that project:

- `<ApiProject>/AGENTS.md` — <what it covers, e.g. use cases, repositories, endpoints, unit tests>
- `<UiProject>/AGENTS.md` — <what it covers, e.g. pages, services, styling>

## Specs and Workflows (OpenSpec)

Every change, of any size, goes through OpenSpec. Claude Code invokes the steps as `/opsx:<step>`, Codex as `$openspec-<skill>`.

| Step | Claude Code | Codex | What it does |
|------|-------------|-------|--------------|
| Explore an idea (optional) | `/opsx:explore` | `$openspec-explore` | Thinks through options; changes nothing |
| Propose | `/opsx:propose` | `$openspec-propose` | Writes `proposal.md`, `specs/`, `design.md` and `tasks.md` in `openspec/changes/<name>/` |
| Revise the plan | `/opsx:update` | `$openspec-update-change` | Changes the plan files and keeps them consistent; never edits code |
| Apply | `/opsx:apply` | `$openspec-apply-change` | Implements `tasks.md` and ticks tasks off |
| Verify | `verifier` subagent | `verifier` custom agent | Checks the change against its spec, tasks and design with a fresh context; writes `verification.md` |
| Archive | `/opsx:archive` | `$openspec-archive-change` | Merges the change's specs into `openspec/specs/` and moves it to `openspec/changes/archive/` |

- Stop after propose and wait for the repo owner to approve before applying.
- After apply, start the `verifier` agent (`.claude/agents/verifier.md`, `.codex/agents/verifier.toml`; instructions in `.agents/agents/verifier.md`) and give it only the change name, not a summary of the work. If the verdict is `FAIL`, fix the gaps and start it again until it passes. Only the verifier writes `verification.md`. List any manual checks it reports in the PR.
- Then run the `policy-review` skill on the change and the diff, then archive the change on the same branch as the code.
- Commit the artifacts with the code and link the archived change in the PR. `scripts/spec-check.sh` must pass.
- **no-spec:** only when the repo owner says a change is no-spec, skip OpenSpec for it and open the PR with `gh pr create --label no-spec`. Never add the label because the check failed. The other checks still apply.

### UI changes

A change to UI files (`.razor` or `.css` in `<SharedUiProject>` or `<WebProject>`; the list is `UI_FILES` in `scripts/spec-check.sh`) comes with a mock-up drawn before the code, and screenshots of the pages it changes:

0. **Mock-up, with the proposal.** Run `scripts/ui-mockups.sh --new <change-name> <page>` for each page the change adds or reshapes, draw the page inside `<main>` with the app's existing classes and made-up data only (never a real user's details), then `scripts/ui-mockups.sh <change-name>` to render `mockups/<page>-desktop.png`, `-phone.png` and `mockups.md`. Show the images when asking the owner to approve the proposal, and commit them with the proposal, before any UI code. For a change with no new layout (a colour or spacing tweak, or a bug fix that restores the existing design), write `mockups.md` with `Mock-up: none` and a `Reason:` line instead.
1. In `tasks.md`, a task names the routes that show the change and whether they need a signed-in user.
2. After apply, commit the code, then run `scripts/ui-screenshots.sh <change-name> <route>...`. It starts the API and Web apps if needed and saves desktop and phone screenshots plus `screenshots.md` in the change folder. Add `--guest` for guest pages, and `--append` to add a second run (e.g. guest and signed in). Commit them before starting the verifier.
3. Signed-in screenshots use the session the repo owner saved with `--login` (`.auth/ui-user.json`, gitignored). Never run `--login`, sign in, or type credentials. If the session is missing or the screenshots show the guest view, ask the owner to run `--login`.
4. If no screenshot can show the change (e.g. only after an interaction), write `screenshots.md` with `Screenshots: none` and a `Reason:` line; the verifier lists it as a manual check.

`scripts/spec-check.sh` fails if a UI change has no `mockups.md` committed before the first UI code commit, no `screenshots.md`, or if UI files changed after the screenshots were taken. The verifier compares the screenshots with the mock-ups. Embed both in the PR's Screenshots section.

### Bug fixes

A bug fix proves the bug with a failing test before fixing it:

1. Name the branch `fix/<short-name>`. `scripts/spec-check.sh` applies the rules below to `fix/` branches.
2. After approval, the first task writes a test that reproduces the bug and runs it. It must fail because of the bug, not because it doesn't compile or its setup is broken.
3. Commit the test on its own, with no production code. Then record it in `failing-test.md` in the change folder (format below), with that commit's sha in `Commit:`.
4. Fix the production code until the test passes. Never change the recorded test files; a Claude hook blocks edits to them and the spec check fails if they change. If the test turns out to be wrong, stop and ask the repo owner.
5. Other tests may still be added or changed.

When no test project covers the code with the bug (e.g. UI without component tests), write `failing-test.md` with `Commit: none`, a `Reason:` line and the steps to reproduce, and fix the bug directly. The verifier lists those steps as a manual check.

```markdown
# Failing test: <bug>

Commit: <sha of the commit that adds the test> | none

Test files:
- `<TestProject>/<path>/<Name>Tests.cs`

Tests:
- `<TestName>`

Command: `dotnet test <TestProject> --filter <TestName>`

Failing output:
(the assertion failure from the run before the fix)

Reason: (only with Commit: none) why no automated test is possible

Reproduce: (only with Commit: none)
1. ...
```

## Code Style

- Write self-explanatory code. Use names (classes, variables, methods) that make sense without comments, and only add a comment when it is really needed.
- Prefer the simplest logic that satisfies the current requirement. Do not add defensive branches, abstractions, metadata, persistence, or service calls unless the current behavior needs them.
- Do not make code more complex because a future rule or event might need it. Add that complexity when the second real use case appears.
- Keep code explicit and readable. If a shorter version is just as clear and efficient, prefer it.

## Build, Test, Verify

<Say what NOT to build, e.g. "Do not build the .sln: the mobile project needs workloads that aren't installed.">

Build only the projects you changed:

| Changed | Build command |
|---------|---------------|
| `<ApiProject>` | `dotnet build <ApiProject>` |
| `<UiProject>` | `dotnet build <UiProject>` |

The .NET SDK is pinned in `global.json` so local and CI formatting agree; install it if `dotnet` says no compatible SDK was found. Before committing C# changes, run `scripts/format-check.sh --fix` (whitespace rules from `.editorconfig`; `.razor` files and migrations aren't covered). CI and Claude's Stop hook run the check.

### Unit Tests

When you add or change <a handler / service / use case>, you **must** add or update its tests in `<TestProject>/<path>`. Never skip error and edge-case tests; happy-path-only coverage is not enough.

```bash
dotnet build <TestProject> && dotnet test <TestProject>
```

### Integration Tests

<If you have them: what they need (e.g. Docker), when to run them, and the command. If Docker is not running, say so instead of silently skipping them.>

### Mutation Tests — Required Before Opening a PR

When a branch adds or changes code in `<ApiProject>/UseCases/`, `Services/` or `Models/`, run the mutation check before opening the PR:

```bash
scripts/mutation-check.sh
```

It needs the .NET 8 runtime (Stryker.NET 4.x runs on .NET 8; don't let it roll forward, which breaks its argument parsing). It runs Stryker.NET on the changed files only and passes only when **every mutant is killed: 0 survived and 0 uncovered**. If it fails, it lists each surviving change (file, line, original code, mutation). Add tests, or strengthen existing ones, until it passes. Don't weaken production code to make it pass.

If a mutant genuinely can't be killed (the change has no observable effect), disable it with a `// Stryker disable once <mutator> : <reason>` comment and call it out in the PR. Files whose change is whitespace only are skipped. Paste the script's final line into the PR template. In Claude Code, a hook runs it automatically before `gh pr create`.

### Evals — Testing the Harness Itself

`evals/tasks/` holds real tasks cut from this repo (a use case removed, a past change undone, a bug put in), each with hidden tests as the answer key. `scripts/eval-run.sh` gives them to an agent in a temporary, history-free copy of `main` with no remote, runs the normal flow (propose, an automatic approval, apply, verify, archive) and scores six checks: work committed on a branch, unit tests, spec check, mutation check, format check, and the hidden tests.

```bash
scripts/eval-run.sh --check                        # tasks still valid against main (no agent)
scripts/eval-run.sh --agent claude --tasks smoke   # the smoke set (evals/sets/smoke.txt)
scripts/eval-run.sh --agent codex                  # all tasks
scripts/eval-run.sh --agent claude --model <model> --effort high --tasks smoke   # another model or effort
```

- **Smoke set** (`evals/sets/smoke.txt`, about 5 tasks covering each kind and size): run it after each harness change. Run all tasks only for an occasional baseline or after a big change. `--tasks` also takes task ids, comma-separated.
- Only the repo owner starts a run: it uses their Claude and Codex plans. Suggest one after a change to `AGENTS.md`, skills, hooks, `.agents/agents/` or the check scripts, and when `--check` fails after a change to code a task uses.
- Defaults (model per agent, effort `medium`) are set at the top of `scripts/eval_run.py`; compare runs only at the same model and effort. Results go to `evals/results/<date>-<agent>-<model>-<effort>.jsonl` (committed); the summary compares the run with the previous one for the same agent, model and effort.
- Never edit `evals/tasks/` or results to make a run pass, and never read `evals/` while working on a normal change. If a task no longer fits the code, fix or replace it in its own change.

## Git Workflow

- Never commit directly to `main`. Make each change on its own branch with a short, descriptive name (e.g. `fix/login-redirect`). Git hooks in `.githooks/` block commits on `main` and pushes to `main`; in a fresh clone, turn them on with `git config core.hooksPath .githooks`. Never bypass them with `--no-verify`.
- Keep a branch to one change. Use short commit messages that say what changed.
- When the change builds and the tests pass, push the branch and open a pull request against `main` (locally: `gh pr create`). Fill in the PR template, including which agent made the change, whether a migration is needed, and the **Deploy** section: which apps to deploy after merge and in which order (migration first, then the API before the apps that call it), or "Nothing to deploy".
- Don't merge pull requests. CI and the AI reviewer check every PR; the repo owner reviews and merges. Address review comments with new commits on the same branch.
- Never merge pull requests (`gh pr merge`), start workflows (`gh workflow run`, `gh run rerun`; deploys may run from these), skip git hooks (`--no-verify`, `git commit -n`) or change `core.hooksPath`. Claude Code denies these in `.claude/settings.json`; Codex follows this rule.
- **Protected paths:** `.github/`, `.githooks/`, `.claude/settings.json`, `.claude/hooks/`, `.claude/agents/`, `.codex/`, `.agents/agents/`, `scripts/` and `<ApiProject>/Migrations/`. Change them only when the repo owner asked for that change, never to get a failing check to pass, and say so in the PR. The `protected-paths` CI job fails on any PR that changes them until the owner adds the `protected-ok` label; never add that label yourself. The list lives in `scripts/protected-paths.sh` and the `ask` rules in `.claude/settings.json`; keep them the same.

## Review guidelines

- Don't flag missing OpenSpec artifacts or a failing `scripts/spec-check.sh`. The `spec-check` CI job enforces that, and the repo owner can exempt a PR with the `no-spec` label.
- Don't flag a failing `scripts/protected-paths.sh`. The `protected-paths` CI job reports it, and the repo owner approves with the `protected-ok` label. Do flag a change to a protected path that loosens a check without the PR saying why.

## Database Migrations

<Your rule, e.g.: Never add EF Core migration files or run migrations. Make the model and DbContext changes only; the repo owner generates and applies migrations.>
