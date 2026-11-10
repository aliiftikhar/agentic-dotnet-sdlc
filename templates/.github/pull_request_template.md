## What changed
<!-- A short summary of the change. -->

Closes #

## Made with
- [ ] Codex
- [ ] Claude Code
- [ ] By hand

## Spec
<!-- Link the OpenSpec change: openspec/changes/archive/<date>-<name>/. `scripts/spec-check.sh` must pass, or the PR has the `no-spec` label. -->
- Change folder: 
- [ ] Verifier verdict (from `verification.md`): 
- Manual checks the verifier listed for the owner: 
- Bug fix only: failing-test commit (from `failing-test.md`), or "none: <reason>": 
- [ ] `policy-review` skill run on the change and the diff; findings resolved or listed under "Notes for the reviewer"

## How it was verified
- [ ] Changed projects build (see "Build, Test, Verify" in `AGENTS.md`)
- [ ] Unit tests pass
- [ ] Tests added or updated for changed code
- [ ] Integration tests run, if affected

## Screenshots
<!-- Required if UI files changed (UI_FILES in scripts/spec-check.sh): embed the images listed in the change's mockups.md and screenshots.md side by side, e.g. ![Orders, desktop](https://github.com/<owner>/<repo>/blob/<branch>/openspec/changes/archive/<date>-<name>/screenshots/<file>.png?raw=true) -->
- [ ] Not applicable (no UI change)
- [ ] Mock-up drawn before the code / Mock-up: none, because: 

| Page | Mock-up | Built (signed in / guest) |
|------|---------|---------------------------|
|      |         |                           |

## Mutation check
<!-- Required if mutation-tested folders changed: run scripts/mutation-check.sh and paste its last line -->
- [ ] Not applicable (no changes in mutation-tested folders)
- [ ] `scripts/mutation-check.sh` passed: 

## Protected paths
<!-- .github/, .githooks/, .claude/settings.json, .claude/hooks/, .claude/agents/, .codex/, .agents/agents/, scripts/, <ApiProject>/Migrations/ -->
- [ ] None changed
- [ ] Changed at the owner's request (owner adds the `protected-ok` label): 

## Migration needed?
- [ ] No
- [ ] Yes: the model changed, and the owner needs to generate the migration

## Deploy
<!-- What to deploy after merge, in order: the migration first if one is needed, then the API before the apps that call it. Deployable apps: <list your deployable apps, e.g. API, Web>. Write "Nothing to deploy" for docs, harness or CI-only changes. -->
1. 

## Notes for the reviewer
<!-- Risks, decisions made, follow-ups. -->
