# Project Instructions

Always read `README.md` first to understand the solution structure and project types before making changes.

Projects with their own conventions have an `AGENTS.md` in their folder. Read it before changing files in that project:

- `<ApiProject>/AGENTS.md` — <what it covers, e.g. use cases, repositories, endpoints, unit tests>
- `<UiProject>/AGENTS.md` — <what it covers, e.g. pages, services, styling>

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
- When the change builds and the tests pass, push the branch and open a pull request against `main` (locally: `gh pr create`). Fill in the PR template, including which agent made the change and whether a migration is needed.
- Don't merge pull requests. CI and the AI reviewer check every PR; the repo owner reviews and merges. Address review comments with new commits on the same branch.

## Database Migrations

<Your rule, e.g.: Never add EF Core migration files or run migrations. Make the model and DbContext changes only; the repo owner generates and applies migrations.>
