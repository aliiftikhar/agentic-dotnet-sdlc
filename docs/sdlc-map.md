# The agentic SDLC map

How a change moves through this kit, one column per stage. Every stage has the same six rows:

- **Who** does the work.
- **Produces:** the files or artifacts that come out.
- **Rules:** the instructions the agent follows at this stage.
- **Fed by:** the context those rules draw on.
- **Checks:** what is actually verified at this stage, by tools or agents: tests, mutation testing, the verifier, policy review, AI code review.
- **Gates:** what stops a change from moving on: approvals, hooks, deny rules, scripts that must pass.

![Agentic SDLC map: six stages (Request, Plan, Build, Check, PR and review, Merge and release) with who, produces, rules, fed by, checks and gates for each](sdlc-map.svg)

Everything on the map is in the kit as of v2.5. When the source project gets ahead of the kit again, amber lines mark what comes in the next release and grey dashed lines what is planned but not built yet.

## Escape hatches

- **`no-spec`:** the owner exempts a small harness or config change from Plan and Check. Every other check still runs.
- **`protected-ok`:** the owner approves a change to CI, hooks, agent settings, scripts or migrations.
- Agents never add either label.

## Keeping it up to date

The map is drawn from [`sdlc-map.json`](sdlc-map.json). To change it, edit the JSON, then regenerate the SVG:

```bash
python3 tools/render-sdlc-map.py
```

- Start a line with `+` to mark it as arriving in the next release (drawn in amber).
- Start a line with `~` to mark it as planned (grey, dashed). Change it to `+` once it works on the source project.
- When a release ships, remove the `+` from its lines and add a row to the changelog below.
- Commit the JSON and the SVG together.

## Changelog

| Release | What the map gained |
|---------|---------------------|
| v0 | Request, build on a branch, PR, AI review, owner merges |
| v1 | Git hooks, Stop hook, architecture tests, mutation check, CI |
| v2 | Plan stage (OpenSpec), skills, policy review, spec check, Deploy section in the PR |
| v2.5 | Verifier and the Check stage's verdict, failing-test-first bug fixes, deny rules, protected paths, format check, UI mock-ups and screenshots |
