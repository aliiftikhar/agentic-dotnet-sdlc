# Automatic Codex review on GitHub

Codex reviews pull requests in OpenAI's cloud, so nothing needs to run on your machine.

## Setup

1. In Codex settings, connect GitHub and make sure the repository has a **Codex cloud environment**.
2. Open the repository's code review settings and turn on **Automatic review**.
3. Set **Review** to cover your own PRs ("Follow personal preferences" for a solo repo; "Team PRs" may only cover members of a ChatGPT workspace).
4. Set **Trigger** to **On PR open**. New commits pushed later aren't reviewed automatically; comment `@codex review` for another pass.
5. Add `## Code Review Rules` sections to your `AGENTS.md` files (see `templates/project-AGENTS.md`). Codex applies the root rules plus the rules in the `AGENTS.md` closest to each changed file.

Codex only posts high-priority (P0/P1) findings, so keep the rules few and serious. When it finds nothing, it reacts with 👍 and posts "Didn't find any major issues".

## If Codex doesn't respond

Symptom: no 👀 reaction and no comment, even after commenting `@codex review`.

What fixed it for us: **recreating the Codex cloud environment for the repository and reconnecting GitHub.** Other things to check:

- Your ChatGPT account is linked to your GitHub account (ChatGPT → Settings → Connectors → GitHub). This is separate from the Codex app being installed on the repo.
- The Codex GitHub app has access to the repository and has no pending permissions request.
- The review settings actually saved (reload the page after changing them).

## Testing it

Open a throwaway PR that breaks your rules on purpose (e.g. an endpoint without auth, a changed handler without tests) while keeping CI green. In our test, the automatic review flagged all three planted violations as P1 with concrete fixes. Close the PR without merging.

An AI reviewer is probabilistic: it can miss things in larger PRs. Treat it as a second layer, not the only check.
