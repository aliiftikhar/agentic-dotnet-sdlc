# Eval tasks

One file per task, `<id>.md`, with simple front matter and the request the agent gets. Replay and bug-fix tasks also have `<id>.patch`. Worked examples: `docs/examples/evals/` in agentic-dotnet-sdlc.

```markdown
---
id: R01-get-order            # must match the file name
kind: remove                 # remove | replay | bugfix
size: small                  # small | medium (for picking a smoke set)
setup: remove-usecase GetOrder   # or: patch (applies <id>.patch)
hidden_tests: [<UnitTestProject>/UseCases/GetOrder/GetOrderHandlerTests.cs]
---
<the request, in the owner's words, naming the public contract the hidden tests need>
```

- **remove:** `remove-usecase <Name>` deletes the use case, its tests, its repository and its `Program.cs` registration and endpoint. The original tests are the answer key.
- **replay:** the patch undoes a past change in today's code and takes out the tests that change added. Those tests are the answer key.
- **bugfix:** the patch puts in a realistic one-line bug and takes out exactly the tests that catch it.

`hidden_tests` are read before setup and run after the agent finishes, in their own folder and namespace. Check every new task with `scripts/eval-run.sh --check --tasks <id>`: the answer key must pass on `main` and fail after setup (a bug fix must build and fail).
