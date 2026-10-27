# State diagrams: order status and payment status

UML state machine diagrams for one order. GitHub renders the Mermaid blocks below; PNG versions are in this folder
([order](state_order.png), [payment](state_payment.png)).

Sources: [`basic_desc.txt`](../requirements/basic_desc.txt) (statuses, 5-day change/cancel limit, read-only history),
[flowcharts](README.md#colour-coded-process-flowcharts-to-be) (admin releases the order to the kitchen after the lock).

**How to read them:** boxes are states (an order is in exactly one at a time), arrows are transitions labelled
`event [guard] / action`, `[*]` is start or end. "> 5 days left" means more than 5 days before the event. Anything not drawn is not allowed, and the API should refuse it.

## Order status

```mermaid
stateDiagram-v2
    direction TB
    state "In preparation" as InPreparation

    [*] --> Submitted : customer submits / save minimum in force
    Submitted --> Submitted : customer changes [> 5 days left, guests ≥ saved min]
    Submitted --> Approved : admin approves
    Submitted --> Rejected : admin rejects / e-mail reason
    Approved --> Approved : customer changes [> 5 days left, guests ≥ saved min] / notify admin
    Approved --> Cancelled : customer cancels [> 5 days left]
    Approved --> InPreparation : admin releases to kitchen [order locked, ≤ 5 days left]
    InPreparation --> Delivered : driver confirms delivery / make read-only
    Rejected --> [*]
    Cancelled --> [*]
    Delivered --> [*]

```

### Allowed transitions (for the backend)

| From | To | Triggered by | Guard |
|---|---|---|---|
| (new) | `submitted` | customer | guests ≥ event-type minimum in force; minimum saved on order |
| `submitted` | `submitted` | customer (change) | > 5 days before event; guests ≥ saved minimum |
| `submitted` | `approved` | admin | – |
| `submitted` | `rejected` | admin | reason required |
| `approved` | `approved` | customer (change) | > 5 days before event; guests ≥ saved minimum |
| `approved` | `cancelled` | customer | > 5 days before event |
| `approved` | `in_preparation` | admin | order locked (≤ 5 days before event) |
| `in_preparation` | `delivered` | driver / admin | – |

`rejected`, `cancelled` and `delivered` are final: no changes, no new transitions (history is immutable).

## Payment status (draft)

Payment isn't integrated in this version: the customer picks a payment option on the order and the admin updates the
payment status by hand. This is a separate state machine that runs alongside the order status.

```mermaid
stateDiagram-v2
    direction LR
    state "Not paid" as NotPaid
    state "Deposit paid" as DepositPaid

    [*] --> NotPaid : order submitted / payment option chosen
    NotPaid --> DepositPaid : admin registers deposit
    NotPaid --> Invoiced : admin sends invoice
    DepositPaid --> Invoiced : admin sends final invoice
    DepositPaid --> Paid : admin registers remaining payment
    Invoiced --> Paid : admin registers payment
    NotPaid --> Paid : admin registers full payment (e.g. Vipps)
    Paid --> [*]

```

## Open questions for the product owner

The diagrams show only what is decided. These gaps need an answer before the backend enforces the transitions:

1. Can a customer cancel a **submitted** order before it's approved?
2. What happens to a **submitted** order that nobody approves before the 5-day lock?
3. Can the **admin** cancel an approved order, and how is the customer told?
4. **Deposit:** for which customer groups, how large, and is it refunded on cancellation? (Ingrid vs Sunniva/Fjordtek interviews.)
5. Who confirms **delivery** in the system: the driver (own screen) or the admin?
