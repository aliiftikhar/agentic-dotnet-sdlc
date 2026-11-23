## Your task: revise the plan for issue #{{ISSUE}}

You are on `{{PLAN_BRANCH}}`. Plan PR #{{PR}} got feedback: {{TRIGGER}}.

1. Read the feedback that started this run, and also any other feedback on the PR from reviewers or
   Codex that came after your last reply and has no reply yet: GitHub keeps only one waiting run per
   issue, so a run that was waiting may have been replaced by this one. Address all of it. For a comment: `gh api repos/{{REPO}}/issues/comments/<id>`. For a review:
   `gh api repos/{{REPO}}/pulls/{{PR}}/reviews/<id>` and its inline comments
   `gh api repos/{{REPO}}/pulls/{{PR}}/reviews/<id>/comments`. Read the rest of the PR's conversation
   (`gh pr view {{PR}} --comments`) for context.
2. Update the change with the `openspec-update-change` skill. If you disagree with a point, or it
   conflicts with the issue, don't change the plan for it: explain why in your reply.
3. `openspec validate {{CHANGE}} --strict` must pass.
4. Record the cost (see the rules), commit and push `{{PLAN_BRANCH}}`.
5. Update the PR body if the summary, open questions, confidence or mock-ups changed
   (`gh pr edit {{PR}} --body-file <file>`).
6. Reply: one comment on the PR listing what changed, or, for inline comments, a reply on each thread
   (`gh api repos/{{REPO}}/pulls/{{PR}}/comments/<comment id>/replies -f body=...`).

Don't write any code in this run.
