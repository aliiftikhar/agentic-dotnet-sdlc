---
name: create-usecase
description: Add a new <ApiProject> use case (MediatR handler, request, response, repository, endpoint and handler tests). Use when a spec or task adds a new API endpoint or use case.
---

# Create a use case

Follow `<ApiProject>/AGENTS.md` for the conventions. This skill is the order of work; the rules are in that file.

1. **Name it** `VerbNoun` (e.g. `GetOrders`). Check `<ApiProject>/UseCases/` for an existing use case that already does this; extend it instead if so.
2. **Create** `<ApiProject>/UseCases/<Name>/` with:
   - `<Name>Request.cs` implementing `IRequest<<Name>Response>` (or `IRequest` if nothing is returned)
   - `<Name>Response.cs` with only the fields the caller needs; never return EF models
   - `I<Name>Repository.cs` with literal database operations (`Get…`, `Insert…`, `Update…`, `Delete…`)
   - `<Name>Handler.cs`: validate the request, get the user ID when data is per user, then the business decisions, repository calls and response mapping in the handler
3. **Implement** `<ApiProject>/<RepositoriesFolder>/<Name>Repository.cs`: inject the `DbContext`, `AsNoTracking()` for reads, no business logic.
4. **Register** the repository in `Program.cs` and map the endpoint (`MapGet`/`MapPost`/`MapPut`) with `.RequireAuthorization()`.
5. **Supporting types** used only by this use case stay in its folder; move a type to `Models/` only when a second use case needs it. Never import from another use case's folder.
6. **Tests:** use the `handler-tests` skill to write `<TestProject>/UseCases/<Name>/<Name>HandlerTests.cs`.
7. **If the model or `DbContext` changes,** use the `model-change` skill.
8. **Verify:**
   ```bash
   dotnet build <TestProject> && dotnet test <TestProject>
   scripts/mutation-check.sh
   ```
   The architecture tests (part of the unit tests) check the folder rule, the matching test class and `.RequireAuthorization()`.

List every file above in `design.md` or `tasks.md` so `scripts/spec-check.sh` passes.
