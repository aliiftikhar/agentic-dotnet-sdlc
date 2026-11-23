## Your task: plan issue #{{ISSUE}}

You are on `{{PLAN_BRANCH}}`, which was just made from `{{BUILD_BRANCH}}` (a fresh copy of `main`).
If `openspec/changes/{{CHANGE}}/` already has commits (a rerun of a run that stopped), continue from
them, and if the plan PR already exists, update it instead of opening another.

1. Read the issue: `gh issue view {{ISSUE}} --comments`.
2. Write the OpenSpec proposal for change `{{CHANGE}}` with the `openspec-propose` skill: proposal.md,
   design.md, tasks.md and the spec deltas. Keep to the issue's scope and its "Out of scope" section.
   For a UI change, draw the mock-ups as AGENTS.md "UI changes" says (`scripts/ui-mockups.sh`) and commit
   them in the change folder.
3. `openspec validate {{CHANGE}} --strict` must pass.
4. Record the cost (see the rules), commit everything in `openspec/changes/{{CHANGE}}/` and push
   `{{PLAN_BRANCH}}`.
5. Open the plan PR:
   `gh pr create --base {{BUILD_BRANCH}} --head {{PLAN_BRANCH}} --title "Plan: <issue title> (#{{ISSUE}})" --body-file <file>`
   with this body:
   - `Plan for #{{ISSUE}}.` and a link to the change folder on the branch.
   - **Summary:** what will change and why, in a few lines.
   - **Mock-ups:** for UI changes, the images linked by commit SHA (see AGENTS.md); else "No UI change".
   - **Open questions:** numbered, each with the option you'd pick if nobody answers. "None" if none.
   - **Confidence:** high, medium or low, and why (unclear requirements, risky areas, missing tests).
   - **Risks and what's out of scope.**
   - The cost table: `python3 scripts/cost_report.py {{CHANGE}} --print --branch {{PLAN_BRANCH}}`.
   - Last line: `Comment to change the plan. Squash-merge this PR to approve it and start the build.`

Don't write any code in this run.
