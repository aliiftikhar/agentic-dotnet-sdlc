# <ProjectName> — Architecture Guide

> Reference for developers and AI agents. Copy this file into the project folder as `AGENTS.md` and add a `CLAUDE.md` next to it containing `@AGENTS.md`. General code style and build/test commands live in the root `AGENTS.md`.

## Project Structure

```
<ProjectName>/
├── <Folder>/      # <what goes here>
└── <Folder>/      # <what goes here>
```

## Conventions

<The rules an agent must follow in this project: where new classes go, naming, patterns to copy, patterns not to copy. Keep it to what is true in the code today, and point to existing files as examples.>

## Adding a New <Feature/Use Case> — Checklist

1. <step>
2. <step>
3. Add or update unit tests
4. Run the build and tests (see the root `AGENTS.md`)

## Code Review Rules

<!-- The AI reviewer (e.g. Codex) follows this section. It only posts serious (P0/P1) findings,
     so keep to a few rules that matter. Leave formatting and lint to CI. Examples: -->

- **Endpoint auth:** Every endpoint must require authorization unless it is explicitly listed as public.
- **Tests:** A changed <handler/use case> must come with matching changes to its tests.
- **Data access:** Repository methods must stay literal database operations. Flag business decisions hidden inside them (existence checks that decide an outcome, silent no-ops, swallowed exceptions).
- **Migrations:** Flag any added or changed migration file if migrations are owner-managed.
