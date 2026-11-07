# Policy review: add-order-note

Reviewed: spec + diff

| Severity | Area | Finding | Where | Suggested action |
|----------|------|---------|-------|------------------|
| Low | Personal data | The note is free text and may contain a name or address. It is stored on the customer's own order only. | `MyApi/Models/Order.cs` | None; keep it out of logs and the order list response |
| Low | Retention | Notes are kept as long as the order. Nothing deletes them separately. | `MyApi/Models/Order.cs` | Owner to confirm the order retention period covers notes |

## Needs the repo owner's decision
- Whether the order retention period should also apply to notes.

## No concerns found in
- Third parties: the note is not sent anywhere.
- Access: `GetOrder` already filters by the current user; a test covers another user.
- Input: length validated in `ValidateRequest()`; no raw SQL or HTML.
- Logging: only the order ID is logged.
- Payments: not affected.
