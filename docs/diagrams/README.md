# Diagrams

UML and process diagrams as text source (PlantUML `.puml`, Mermaid `.md`, or generator scripts), so they can be diffed and reviewed in pull requests.
Name files by type, e.g. `use-case_overview.puml`, `activity_as-is-order.puml`, `class_domain.puml`, `state_order.puml`.

## Colour-coded process flowcharts (to-be)

Source requirements: [`../requirements/basic_desc.txt`](../requirements/basic_desc.txt).

| Diagram | What it shows |
|---|---|
| [`flow_1_customer_journey`](flow_1_customer_journey.svg) ([PNG](flow_1_customer_journey.png)) | The customer's journey from browsing menus to a delivered order, including a change in guest count after the 7-day reminder, the 5-day lock, and the "too late, ask a question" path. |
| [`flow_2_admin_order_lanes`](flow_2_admin_order_lanes.svg) ([PNG](flow_2_admin_order_lanes.png)) | One order moving between the Customer, System, Admin/coordinator, Kitchen and Delivery lanes, with status badges where the order status changes. |

**Colour code:** lane colour = who does the step (task borders match their lane) · yellow diamond = decision · purple clock = automatic timer · red = reject / refuse / cancel path · status badges = order status change (Submitted, Approved, In preparation, Delivered, Rejected, Cancelled).

**Assumptions** (not settled in `basic_desc.txt`; confirm with the product owner):
- Minimum guests per event type (example values, admin can set 1–265): corporate lunch 8, birthday 10, confirmation 15, christmas party 20, conference 30, wedding 50. The minimum in force when the order is placed is saved on the order, so later changes to the minimum don't invalidate it.
- Changes and cancellation are allowed until 5 days before the event; a reminder goes out 7 days before.
- Payment is not integrated: the customer picks a payment option on the order and the admin updates payment status by hand.
- Lanes follow the case interviews (coordinator, kitchen, driver), although `basic_desc.txt` only names "admin".

## State diagrams

[`state_order.md`](state_order.md) holds two UML state machine diagrams in Mermaid (GitHub renders them), with PNG copies:

| Diagram | What it shows |
|---|---|
| [Order status](state_order.md#order-status) ([PNG](state_order.png)) | Every status an order can have and the events and guards that move it, plus a table of allowed transitions the backend should enforce. |
| [Payment status](state_order.md#payment-status-draft) ([PNG](state_payment.png)) | Draft: manual payment status alongside the order status. |

Open questions for the product owner are listed at the bottom of `state_order.md`.

### Regenerating

```sh
python3 docs/diagrams/src/make_flowcharts.py   # writes the SVGs
sh docs/diagrams/src/make_png.sh               # SVG -> PNG with headless Google Chrome (macOS)
sh docs/diagrams/src/make_state_png.sh         # Mermaid state diagrams -> PNG (needs internet)
```

Edit the node and edge lists in `src/make_flowcharts.py` to change a diagram.
