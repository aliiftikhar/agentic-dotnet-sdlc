## 1. Model

- [x] 1.1 Add nullable `Note` to `MyApi/Models/Order.cs`
- [x] 1.2 Set the column length to 500 in `MyApi/Providers/AppDbContext.cs` (migration needed, not created)

## 2. Place an order with a note

- [x] 2.1 Add `Note` to `MyApi/UseCases/PlaceOrder/PlaceOrderRequest.cs`
- [x] 2.2 Validate the length and save the note in `MyApi/UseCases/PlaceOrder/PlaceOrderHandler.cs`
- [x] 2.3 Tests in `MyApi.UnitTests/UseCases/PlaceOrder/PlaceOrderHandlerTests.cs`: note saved, no note, whitespace note stored as none, 500 characters accepted, 501 rejected

## 3. Read the note back

- [x] 3.1 Add `Note` to `MyApi/UseCases/GetOrder/GetOrderResponse.cs`
- [x] 3.2 Map the note in `MyApi/UseCases/GetOrder/GetOrderHandler.cs`
- [x] 3.3 Tests in `MyApi.UnitTests/UseCases/GetOrder/GetOrderHandlerTests.cs`: note returned to the owner, order not found for another user

## 4. Verify

- [x] 4.1 `dotnet test MyApi.UnitTests` passes
- [x] 4.2 `scripts/mutation-check.sh` passes (0 survived, 0 uncovered)
- [x] 4.3 `policy-review` run on the change and the diff
