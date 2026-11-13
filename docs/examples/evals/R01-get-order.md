---
id: R01-get-order
kind: remove
size: small
setup: remove-usecase GetOrder
hidden_tests: [Shop.Api.UnitTests/UseCases/GetOrder/GetOrderHandlerTests.cs]
---
Customers need to see one of their orders.

- Endpoint: `GET /orders/{id}` returning `GetOrderResponse`, signed-in only.
- Handler: `GetOrderHandler(IGetOrderRepository repository, IAuthService authService)`.
- `IGetOrderRepository`: `Task<Order?> GetOrder(Guid id, string userId)`.
- `GetOrderResponse`: `Id`, `PlacedAt`, `Total`, `Note`, and `Lines` (each `ProductName`, `Quantity`, `LineTotal`).
- Behaviour: use `GetCurrentUserId()`; no id means `UnauthorizedAccessException`. An order that doesn't exist or belongs to someone else throws `KeyNotFoundException`. Lines keep the order they were added in.
- Validation: null request throws `ArgumentNullException`; an empty `Id` throws `ArgumentException`.

The use case goes in `Shop.Api/UseCases/GetOrder/` (namespace `Shop.Api.UseCases.GetOrder`), like the existing ones.
