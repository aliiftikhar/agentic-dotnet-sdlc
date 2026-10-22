# v1: rules that are checked, not just written

Instructions in `AGENTS.md` are advice; agents usually follow them, but not always. v1 adds layers that check the important rules every time, from cheapest and earliest to slowest and latest.

| Layer | Where it runs | What it enforces | Files |
|---|---|---|---|
| Git hooks | Every local commit, merge and push | Nothing reaches `main` except through a pull request | `.githooks/` |
| Claude Code Stop hook | When Claude finishes a turn | Changed projects build and unit tests pass; blocks once with the errors | `.claude/hooks/verify-changes.sh` |
| Architecture tests | Every test run, locally and in CI | Use cases don't import each other; every handler has tests; every endpoint requires auth | `tests/ArchitectureTests.cs` |
| CI | Every PR and push to `main` | Every deployable project builds; unit tests (including architecture tests) pass | `.github/workflows/ci.yml` |
| Mutation check | Locally, before opening a PR | Every mutant in changed code is killed (0 survived, 0 uncovered) | `scripts/mutation-check.sh`, `.claude/hooks/mutation-check-before-pr.sh` |
| AI review | Every PR | The rules in `## Code Review Rules`, with judgement | `AGENTS.md` files (see `codex-review.md`) |

## Setup

1. **Git hooks:** copy `.githooks/` and run `git config core.hooksPath .githooks` once per clone. Hooks can be skipped with `--no-verify` and don't cover edits in GitHub's web UI. On a private repo, only GitHub Pro branch protection closes those gaps.
2. **Claude Code hooks:** copy `.claude/settings.json` and `.claude/hooks/`, then set the build rules at the top of `verify-changes.sh`. The PR hook uses `onFailure: block`, so a failed or timed-out check blocks the PR instead of letting it through.
3. **Architecture tests:** copy `tests/ArchitectureTests.cs` into your unit test project (`Architecture/` folder), add the `NetArchTest.Rules` and `Microsoft.CodeAnalysis.CSharp` packages, and fill in the constants at the top. Run the tests once and fix (or, with approval, allow-list) what they find.
4. **CI:** adapt `.github/workflows/ci.yml` with one build step per deployable project. If a deployment workflow gates on CI by workflow file name, update it whenever you rename this file.
5. **Mutation check:** copy `.config/dotnet-tools.json`, put `tests/stryker-config.json` in your unit test project, copy `scripts/mutation-check.sh` and set the three values at its top. Stryker.NET 4.x needs the .NET 8 runtime; keep `rollForward` off.

## Lessons from using this on a real codebase

- **Prove every check fails.** Plant a violation (an endpoint without auth, a handler without tests, an untested rule) and make sure the check catches it before trusting it. The first version of the use-case test missed a real violation because namespace prefix matching was too loose.
- **Don't build for patterns you don't use.** The endpoint check covers direct `app.Map*` calls and fails loudly if `MapGroup` appears, rather than half-supporting route groups.
- **Measure before putting slow checks in CI.** A full mutation run took about 3.5 minutes locally but 22–25 minutes on GitHub-hosted runners. Running it locally on changed code only takes about a minute.
- **The AI reviewer earns its place.** Across a dozen PRs it caught real problems the author missed, including a CI rename that would have blocked every API deployment and a hook gap that let merge commits onto `main`.
