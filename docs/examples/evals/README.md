# Example eval tasks

Three tasks in the same made-up shop domain as `../add-order-note/`, one of each kind. They show the format; the paths, code and tests are illustrative, so these patches won't apply to your repository. Write your own from your code and history, and check each with `scripts/eval-run.sh --check --tasks <id>`.

| Task | Kind | Setup | Answer key |
|------|------|-------|------------|
| [R01-get-order](R01-get-order.md) | remove | `remove-usecase GetOrder`: the use case, its tests, repository, registration and endpoint are deleted | The original `GetOrderHandlerTests` |
| [P01-orders-newest-first](P01-orders-newest-first.md) | replay | [patch](P01-orders-newest-first.patch) undoes a past change (newest orders first) and takes out the test it added | That test, plus the rest of the file |
| [B01-discount-ignored](B01-discount-ignored.md) | bugfix | [patch](B01-discount-ignored.patch) puts in a one-line bug and takes out exactly the test that catches it | That test, plus the rest of the file |

What makes a good task:

- **Remove:** the request names the public contract (types, constructor, repository interface, behaviour, validation), as an owner would in a ticket, because the hidden tests compile against it. Behaviour the tests check must be in the request.
- **Replay:** pick a past change whose tests would fail without it. If the tests pass either way, the task can't be scored, and you've found a weak test.
- **Bug fix:** the request is a bug report in the user's words, never the cause. Take out only the tests that fail with the bug in place. If no test fails, there's no answer key, and you've found a missing test.
