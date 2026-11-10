# v2.5: stronger verification and guards

v2 makes the agent agree what it's building. v2.5 checks that it built that, with evidence: a **second agent** that didn't build the change checks it against the spec, bug fixes start with a **failing test**, UI changes come with a **mock-up before the code** and **screenshots after it**, and **guards** stop agents from changing the checks themselves.

| Piece | Where it runs | What it does | Files |
|---|---|---|---|
| Verifier agent | After apply, before policy review | A fresh-context agent checks every scenario, task and design decision against the diff and writes `verification.md` with a verdict | `.agents/agents/verifier.md`, `.claude/agents/verifier.md`, `.codex/agents/verifier.toml` |
| Failing-test-first bug fixes | `fix/` branches | The reproducing test is committed on its own and recorded in `failing-test.md` before any fix; a Claude hook blocks edits to it | `AGENTS.md` ("Bug fixes"), `.claude/hooks/protect-failing-test.sh` |
| UI mock-ups | With the proposal | HTML mock-ups styled with the app's own CSS, rendered to desktop and phone PNGs, shown to the owner before any code | `scripts/ui-mockups.sh`, `scripts/ui-mockup-template.html` |
| UI screenshots | After apply | Desktop and phone screenshots of the changed routes, signed in or as a guest, as evidence for the verifier and the PR | `scripts/ui-screenshots.sh` |
| Spec check, extended | Claude hook before `gh pr create`, and CI | Adds: a passing `verification.md`; for `fix/` branches, the failing-test order; for UI changes, a mock-up committed before the code and screenshots newer than the last UI change | `scripts/spec-check.sh` |
| Format check | Claude Stop hook and CI | `dotnet format whitespace` on changed projects, with the SDK pinned so local and CI agree | `.editorconfig`, `global.json`, `scripts/format-check.sh` |
| Deny rules | Claude Code | Agents can't merge PRs, start workflows, skip git hooks or change `core.hooksPath` | `.claude/settings.json` (`permissions.deny`) |
| Protected paths | Claude Code (ask first) and CI | Changes to CI, hooks, agent settings, scripts and migrations need the owner's `protected-ok` label | `.claude/settings.json` (`permissions.ask`), `scripts/protected-paths.sh`, `.github/workflows/protected-paths.yml` |

## Setup

1. **Verifier:** copy `.agents/agents/verifier.md` (the instructions), `.claude/agents/verifier.md` and `.codex/agents/verifier.toml` (both point to it). Copy the Verify row and step from "Specs and Workflows" in `templates/AGENTS.md`, and the verifier lines in the PR template.
2. **Bug fixes:** copy the "Bug fixes" section of `templates/AGENTS.md`, `.claude/hooks/protect-failing-test.sh` and its hook in `.claude/settings.json`, and the bug-fix rule in `templates/openspec/config.yaml`.
3. **Spec check:** replace `scripts/spec-check.sh` with the v2.5 version and set `UI_FILES` (shell patterns for your `.razor` and `.css` files) and `UI_SKIP` (vendored CSS) at the top.
4. **UI screenshots and mock-ups** (skip if you have no web UI):
   - copy `scripts/ui-screenshots.sh`, `scripts/ui-mockups.sh` and `scripts/ui-mockup-template.html`, and fill in the configuration block at the top of each script (ports, projects, sign-in path, UI paths);
   - add `.auth/` to `.gitignore`;
   - install Chromium for Playwright once: `npx playwright@<version> install chromium`;
   - make the template look like your app: link your stylesheets (the global CSS and the layout's scoped `.razor.css` files), paste your layout's rendered markup with made-up names and an empty `<main>`, then draw one existing page and compare it with a real screenshot;
   - if the app has sign-in, the owner runs `scripts/ui-screenshots.sh --login` once and signs in with a test account; `--setup-guest` saves a guest past any first-visit prompt;
   - copy the "UI changes" section of `templates/AGENTS.md`, the UI rules in `templates/openspec/config.yaml` and the Screenshots section of the PR template.
5. **Format check:** copy `.editorconfig`, `global.json` (pin the SDK you use; different SDK versions format differently), `scripts/format-check.sh` (list your projects at the top), the format step in `.claude/hooks/verify-changes.sh` and in `.github/workflows/ci.yml`. Run `scripts/format-check.sh --fix --all` once and commit the result on its own, so later diffs stay clean.
6. **Guards:** copy the `permissions` block of `templates/.claude/settings.json`, `scripts/protected-paths.sh` (same list as the `ask` rules), `.github/workflows/protected-paths.yml`, and the deny and protected-path rules under "Git Workflow" in `templates/AGENTS.md`. Create a `protected-ok` label in GitHub.
7. **Prove each one fails** before trusting it: a change with no `verification.md`; a `fix/` branch whose test comes after the fix; a `.razor` change with no mock-up, or with the mock-up in the same commit; a PR that touches `scripts/`.
8. Open the setup as a PR. It changes protected paths, so it needs `protected-ok` too.

## How a change goes through now

1. **Propose.** As in v2. For a UI change, the agent also draws the pages with `scripts/ui-mockups.sh --new` and renders them, and shows you the images with the proposal. Approve the layout here, while it's cheap to change.
2. **Apply.** On a `fix/` branch, the first commit is the failing test alone, recorded in `failing-test.md`. For a UI change, the agent commits the code, then runs `scripts/ui-screenshots.sh` for the routes in `tasks.md`.
3. **Verify.** The agent starts the verifier with only the change name. The verifier reads the change files and the diff, runs the cited tests, opens the screenshots and mock-ups, and writes `verification.md`: `PASS`, `PASS WITH MANUAL CHECKS` or `FAIL` with the gaps. The building agent fixes the gaps and starts it again.
4. **Policy review, archive, PR.** As in v2. The PR lists the verdict, the manual checks, and the mock-ups next to the screenshots.

See [`examples/add-order-note/verification.md`](examples/add-order-note/verification.md) for a verifier report.

## Why each piece is shaped this way

- **The verifier gets only the change name.** Given a summary of the work, it agrees with the summary. With only the files and the diff, it checks the change the way a reviewer would. It may write one file and run read-only commands, so it can't fix what it finds.
- **The failing test is its own commit.** The spec check can then prove the order (test commit before any production change, touching only tests) and that the recorded test files never changed afterwards. Code with no test project (e.g. UI) records `Commit: none` with reproduce steps, which the verifier lists as manual checks.
- **Agents never sign in.** Many sign-in pages are a live identity provider, so the owner signs in once in a real browser window and the session is saved to a gitignored file; screenshots reuse it and save it back, which keeps sliding sessions alive. Agents never run `--login` or type credentials.
- **Screenshots record the commit they show.** The script refuses uncommitted UI files and running apps older than their source, and the spec check fails if a UI file changes after the recorded commit.
- **Mock-ups are HTML with the app's real CSS,** not a design tool, so any agent can draw one from files and a script, and the owner sees something close to the app. The script inlines the stylesheets and icons into a temporary copy, so links stay repo-relative and still work after the change is archived. Opening a mock-up's HTML directly shows it unstyled; the PNGs are what people look at.
- **Guards are about the checks, not the code.** Agents could otherwise "fix" a failing check by editing the hook, the workflow or the script. Deny rules block the commands that bypass checks outright; protected paths let the owner approve real harness changes with a label.

## Lessons from using this on a real codebase

- **The second agent finds real gaps.** On the first changes it checked, the verifier found gaps that the building agent's own summary didn't mention.
- **Pin the SDK before adding a format check.** The first CI run disagreed with local runs because CI used a different SDK, which formats differently. `global.json` with the same SDK in both fixed it.
- **The AI reviewer catches holes in the checks themselves.** It found that a running app older than its source would screenshot old code while recording the new commit, and that a placeholder `mockups.md` with no images passed the mock-up rule. Both are fixed in these scripts.
- **Full-page screenshots miss content when the layout scrolls inside an element** rather than the page. A tall viewport (2000px) shows it.
- **A first-visit prompt covered every guest screenshot,** because each headless browser is a new visitor. A saved guest session (`--setup-guest`) fixed it.
- **`git log --follow` didn't find a file's first commit after its folder was archived.** The spec check also searches the change's original path.
- **Use made-up data in mock-ups and a test account for screenshots.** Both are committed, so they stay in history.
- **On a private repo without branch protection, CI checks and labels are signals, not gates.** Claude's deny rules and hooks block Claude; for Codex and people, a red check is a message to the person merging.
