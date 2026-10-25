"""Creates constraints and the example event types. Safe to run more than once.

Run from the backend folder:  python -m scripts.seed
Minimums match docs/diagrams/README.md (example values, not confirmed with the product owner).
"""
from app import create_app
from app.db import run

EVENT_TYPES = [
    ("corporate-lunch", "Firmalunsj", "Corporate lunch", 8),
    ("birthday", "Bursdag", "Birthday", 10),
    ("confirmation", "Konfirmasjon", "Confirmation", 15),
    ("christmas-party", "Julebord", "Christmas party", 20),
    ("conference", "Konferanse", "Conference", 30),
    ("wedding", "Bryllup", "Wedding", 50),
]

CONSTRAINTS = [
    "CREATE CONSTRAINT event_type_id IF NOT EXISTS FOR (e:EventType) REQUIRE e.id IS UNIQUE",
    "CREATE CONSTRAINT food_item_id IF NOT EXISTS FOR (f:FoodItem) REQUIRE f.id IS UNIQUE",
    "CREATE CONSTRAINT customer_email IF NOT EXISTS FOR (c:Customer) REQUIRE c.email IS UNIQUE",
    "CREATE CONSTRAINT order_id IF NOT EXISTS FOR (o:Order) REQUIRE o.id IS UNIQUE",
]


def main() -> None:
    with create_app().app_context():
        for c in CONSTRAINTS:
            run(c)
        for id_, name_no, name_en, minimum in EVENT_TYPES:
            # ON CREATE only: re-seeding must not overwrite minimums the admin has changed.
            run(
                "MERGE (e:EventType {id: $id}) "
                "ON CREATE SET e.name_no = $no, e.name_en = $en, e.min_guests = $min",
                id=id_, no=name_no, en=name_en, min=minimum,
            )
    print(f"Seeded {len(EVENT_TYPES)} event types and {len(CONSTRAINTS)} constraints.")


if __name__ == "__main__":
    main()
