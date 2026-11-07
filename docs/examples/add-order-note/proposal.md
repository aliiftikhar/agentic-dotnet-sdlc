## Why

Customers want to leave a short note for the warehouse when they place an order (for example "leave with neighbour at number 12"). Today they email support, who copy it into the order by hand.

## What Changes

- An order can carry an optional note of up to 500 characters, set when the order is placed.
- The customer who placed the order can read it back with the order.
- No change to how orders are priced, paid for or shipped.

## Capabilities

### New Capabilities
- `order-notes`: an optional free-text note attached to an order by the customer who placed it.

### Modified Capabilities
- None.

## Impact

- **Personal data:** yes. The note is free text a customer types and may contain an address or a name. It is stored on the order, shown only to the customer who placed it, and not logged or sent to any third party.
- **Authentication/authorisation:** the existing order endpoints already require sign-in and scope orders to the current user; the note follows the same rule.
- **Payments:** no.
- **Third-party AI providers:** no.
- **Migration needed:** yes, one nullable column on `Order`.
