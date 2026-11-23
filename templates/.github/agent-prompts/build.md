## Your task: build issue #{{ISSUE}}

The owner approved the plan by merging plan PR #{{PR}} into `{{BUILD_BRANCH}}`; that merge is the
approval to build. You are on `{{BUILD_BRANCH}}`, already updated from `main`. The plan PR's
conversation may hold answers to its open questions: read it with `gh pr view {{PR}} --comments`.

Follow the flow in AGENTS.md from apply onwards, exactly as in a local session:

1. Implement the change with the `openspec-apply-change` skill, task by task, with the tests AGENTS.md
   asks for. Build and run the tests (see "Build, Test, Verify").
2. For UI changes: commit the code, then take screenshots with `scripts/ui-screenshots.sh` and commit
   them, as AGENTS.md "UI changes" says. CI has no saved session, so signed-in pages show the guest view:
   take guest screenshots where they show the change, else write `screenshots.md` with a reason. The verifier
   compares them with the mock-ups, so they come first.
3. Run the `verifier` subagent; fix what it finds until it passes. If a fix changes UI files, take the
   screenshots again.
4. Run the `policy-review` skill on the change and the diff; fix or list its findings.
5. Archive the change with the `openspec-archive-change` skill.
6. Record the cost (see the rules, step "Build"), then `scripts/cost-report.sh {{CHANGE}}` and commit
   `ci-usage.jsonl` and `cost.md`. Push `{{BUILD_BRANCH}}`.
7. Open the PR into `main`: `gh pr create --base main --head {{BUILD_BRANCH}} --body-file <file>`, with
   the PR template filled in, "Closes #{{ISSUE}}", "Plan: #{{PR}}", "Made with: Claude Code (CI agent run)",
   and the cost table.
   Don't comment `@codex review`: the workflow asks Codex from the owner's account after this run.

If you can't finish (failing tests you can't fix, a question the plan doesn't answer, a check that
needs the owner), still push and open the PR, as a draft (`--draft`), with what's done, what's left
and why under "Notes for the reviewer".
