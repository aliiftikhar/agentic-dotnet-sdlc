## Purpose

Lets a customer attach a short delivery note to an order when they place it and read it back later, so the warehouse has their instructions without a support email.

## ADDED Requirements

### Requirement: Customer can add a note when placing an order
The system SHALL accept an optional note of up to 500 characters when a signed-in customer places an order, and store it with the order.

#### Scenario: Order placed with a note
- **WHEN** a signed-in customer places an order with the note "Leave with neighbour at number 12"
- **THEN** the order is created and its note is "Leave with neighbour at number 12"

#### Scenario: Order placed without a note
- **WHEN** a signed-in customer places an order with no note
- **THEN** the order is created with no note

#### Scenario: Note too long
- **WHEN** a signed-in customer places an order with a note of 501 characters
- **THEN** the request is rejected as invalid and no order is created

### Requirement: Only the customer who placed the order can read its note
The system SHALL return the note with the order only to the customer who placed it.

#### Scenario: Owner reads their order
- **WHEN** the customer who placed an order with a note requests that order
- **THEN** the response includes the note

#### Scenario: Another customer requests the order
- **WHEN** a different signed-in customer requests that order
- **THEN** the order is not found and no note is returned
