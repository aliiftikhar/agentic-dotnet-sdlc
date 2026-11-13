---
id: B01-discount-ignored
kind: bugfix
size: small
setup: patch
hidden_tests: [Shop.Api.UnitTests/UseCases/PlaceOrder/PlaceOrderHandlerTests.cs]
---
Bug: discount codes are accepted at checkout but customers are charged the full price. The code shows as applied, but the order total doesn't change.
