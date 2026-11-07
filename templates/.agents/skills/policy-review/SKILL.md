---
name: policy-review
description: Review an OpenSpec change or branch diff for security and personal-data concerns before planning or opening a PR. Use after openspec-propose, before gh pr create, or when asked for a policy or privacy review.
---

# Policy review

This review flags concerns for the repo owner to decide; it does not change code. Fill in the `<placeholders>` with where these things live in your codebase, so the review checks real files instead of guessing.

## Input

- An OpenSpec change folder (`openspec/changes/<name>/`). If none is given, use the folder changed on the current branch.
- The branch diff: `git diff $(git merge-base HEAD origin/main)` plus untracked files.

Review whatever exists: only the spec before planning, the spec and diff before a PR.

## Check

1. **Personal data.** Does the change store, show, log, export or email personal data? In this codebase that includes <your personal-data types, e.g. user profile, email, payment customer ID, anything a user types>. For each: is it needed for the spec, who can see it, and is it scoped to the signed-in user (<how handlers get the current user ID>)? If your users include children, say so here and treat their data as the highest risk.
2. **Third parties.** Does any data go to an AI provider (<where provider calls live>), a payment provider, an email service or another external service? State which personal data, if any, may never be sent to AI providers.
3. **Access control.** New endpoints require authorisation; handlers check the user ID; queries filter by that user; anonymous or guest users can't reach other users' data or paid features.
4. **Input handling.** Values from requests are validated; nothing builds raw SQL, HTML or prompts from unchecked user input without a reason.
5. **Logging and errors.** No personal data or payment details in logs, exception messages or analytics events.
6. **Payments and subscriptions.** Changes to subscription checks, trial limits or payment flows keep paid features behind a valid subscription.
7. **Retention.** New stored data has an obvious reason to exist; note if nothing ever deletes it.

## Output

Write `policy-review.md` in the change folder, then summarise it in chat:

```markdown
# Policy review: <change>

Reviewed: spec | spec + diff (<base commit>..<head>)

| Severity | Area | Finding | Where | Suggested action |
|----------|------|---------|-------|------------------|
| High / Medium / Low | Personal data / Third parties / Access / Input / Logging / Payments / Retention | ... | `path:line` or spec section | ... |

## Needs the repo owner's decision
- ...

## No concerns found in
- <areas checked with nothing to report>
```

High means personal data could reach the wrong person or an external service, or a paid or authenticated feature becomes reachable without access. If there are High findings, say so first and recommend not opening the PR until the owner has decided.
