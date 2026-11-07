---
name: handler-tests
description: Write or update unit tests for a <ApiProject> use case handler and get the mutation check to 0 survived. Use whenever a handler in <ApiProject>/UseCases/ is added or changed.
---

# Handler tests

The test structure and conventions are in `<ApiProject>/AGENTS.md`. This skill is the order of work.

1. **File:** `<TestProject>/UseCases/<Name>/<Name>HandlerTests.cs`, class `<Name>HandlerTests`. Read a neighbouring test file first and match its style.
2. **List the branches** in the handler before writing tests: each validation rule, the auth check, each not-found path, each business decision, and every response field that is mapped.
3. **Write one test per branch**, covering every category that applies:
   happy path · null request · validation failures · authorisation failure (null or empty user ID) · not found · each business branch · mapping completeness (assert every response field).
   Name tests `Handle_<Condition>_<Expected>`. Mock every dependency; verify repository calls that matter (called once, never called).
4. **Changed handler:** update tests whose expected behaviour changed, and add tests for new branches. Don't delete a test unless its behaviour was removed by the spec.
5. **Run:**
   ```bash
   dotnet build <TestProject> && dotnet test <TestProject>
   scripts/mutation-check.sh
   ```
6. **Surviving mutants:** read each one (file, line, mutation) and add or tighten the assertion that would catch it. Don't weaken production code to kill a mutant. If a mutant truly has no observable effect, use `// Stryker disable once <mutator> : <reason>` and mention it in the PR.
