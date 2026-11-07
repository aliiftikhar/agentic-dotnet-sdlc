---
name: model-change
description: Change an EF Core entity or DbContext in <ApiProject> (add, rename or remove a property or entity). Use when a spec or task changes stored data. Agents never create migrations.
---

# Change the data model

Migrations are owner-managed (see "Database Migrations" in `AGENTS.md`). You change the model and `DbContext` only and flag that a migration is needed.

1. **Find every use.** Search for the entity and property across every project before changing it. Responses, repositories and UI models that copy the field need updating too.
2. **Change the entity** in `<ApiProject>/Models/<Entity>.cs`, following the conventions in `<ApiProject>/AGENTS.md` (keys, JSON columns, defaults).
3. **Change the `DbContext`** only if configuration is needed (keys, JSON columns, indexes, defaults).
4. **Keep it backward-compatible** where you can: a new column is nullable or has a default, so existing rows and the currently deployed app keep working. If the change can't be backward-compatible (rename, drop, type change), say so in the design as a risk for the owner.
5. **Personal data:** if the new field holds personal data, note it in the spec so the `policy-review` skill picks it up.
6. **Do not** run `dotnet ef migrations add`, add migration files, or run `dotnet ef database update`. If a migration was created by mistake, remove it with `dotnet ef migrations remove --project <ApiProject>`.
7. **Update** the repositories, handlers and their tests that use the changed field (`handler-tests` skill), and integration tests for changed repositories.
8. **Flag it:** tick "Migration needed? Yes" in the PR template and add one line to the design: "Migration needed: <what changed>".
