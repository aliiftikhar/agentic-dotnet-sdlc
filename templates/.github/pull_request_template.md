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
- [ ] `policy-review` skill run on the change and the diff; findings resolved or listed under "Notes for the reviewer"

## How it was verified
- [ ] Changed projects build (see "Build, Test, Verify" in `AGENTS.md`)
- [ ] Unit tests pass
- [ ] Tests added or updated for changed code
- [ ] Integration tests run, if affected

## Mutation check
<!-- Required if mutation-tested folders changed: run scripts/mutation-check.sh and paste its last line -->
- [ ] Not applicable (no changes in mutation-tested folders)
- [ ] `scripts/mutation-check.sh` passed: 

## Migration needed?
- [ ] No
- [ ] Yes: the model changed, and the owner needs to generate the migration

## Deploy
<!-- What to deploy after merge, in order: the migration first if one is needed, then the API before the apps that call it. Deployable apps: <list your deployable apps, e.g. API, Web>. Write "Nothing to deploy" for docs, harness or CI-only changes. -->
1. 

## Notes for the reviewer
<!-- Risks, decisions made, follow-ups. -->
