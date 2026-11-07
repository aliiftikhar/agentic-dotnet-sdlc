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
| Archive | `/opsx:archive` | `$openspec-archive-change` | Merges the change's specs into `openspec/specs/` and moves it to `openspec/changes/archive/` |

- Stop after propose and wait for the repo owner to approve before applying.
- Before opening the PR, run the `policy-review` skill on the change and the diff, then archive the change on the same branch as the code.
- Commit the artifacts with the code and link the archived change in the PR. `scripts/spec-check.sh` must pass.
- **no-spec:** only when the repo owner says a change is no-spec, skip OpenSpec for it and open the PR with `gh pr create --label no-spec`. Never add the label because the check failed. The other checks still apply.

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

If a mutant genuinely can't be killed (the change has no observable effect), disable it with a `// Stryker disable once <mutator> : <reason>` comment and call it out in the PR. Paste the script's final line into the PR template. In Claude Code, a hook runs it automatically before `gh pr create`.

## Git Workflow

- Never commit directly to `main`. Make each change on its own branch with a short, descriptive name (e.g. `fix/login-redirect`). Git hooks in `.githooks/` block commits on `main` and pushes to `main`; in a fresh clone, turn them on with `git config core.hooksPath .githooks`. Never bypass them with `--no-verify`.
- Keep a branch to one change. Use short commit messages that say what changed.
- When the change builds and the tests pass, push the branch and open a pull request against `main` (locally: `gh pr create`). Fill in the PR template, including which agent made the change, whether a migration is needed, and the **Deploy** section: which apps to deploy after merge and in which order (migration first, then the API before the apps that call it), or "Nothing to deploy".
- Don't merge pull requests. CI and the AI reviewer check every PR; the repo owner reviews and merges. Address review comments with new commits on the same branch.

## Review guidelines

- Don't flag missing OpenSpec artifacts or a failing `scripts/spec-check.sh`. The `spec-check` CI job enforces that, and the repo owner can exempt a PR with the `no-spec` label.

## Database Migrations

<Your rule, e.g.: Never add EF Core migration files or run migrations. Make the model and DbContext changes only; the repo owner generates and applies migrations.>
