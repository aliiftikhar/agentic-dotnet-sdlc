## Context

Orders are placed through the `PlaceOrder` use case and read through `GetOrder`. Both already require sign-in, and `GetOrder` filters by the current user's ID.

## Decisions

- **Store the note on `Order`** as a nullable `Note` column (`nvarchar(500)`). A separate table would only be needed if orders could have several notes, which no one has asked for.
- **Validate length in `PlaceOrderHandler.ValidateRequest()`**, the same place as the other request checks. Empty or whitespace-only notes are stored as no note.
- **Return the note in `GetOrderResponse`** only. It is not added to the order list response, which the warehouse dashboard also reads.
- **No logging of the note.** The handler logs the order ID only, as it does today.

## Files

- `MyApi/Models/Order.cs`: add `Note`
- `MyApi/Providers/AppDbContext.cs`: column length 500
- `MyApi/UseCases/PlaceOrder/PlaceOrderRequest.cs`: add `Note`
- `MyApi/UseCases/PlaceOrder/PlaceOrderHandler.cs`: validate and save the note
- `MyApi/UseCases/GetOrder/GetOrderResponse.cs`: add `Note`
- `MyApi/UseCases/GetOrder/GetOrderHandler.cs`: map the note

Migration needed: nullable `Note` column on `Order`.

## Risks

- A customer could type personal data into the note. It stays on their own order and is never logged; see `policy-review.md`.
