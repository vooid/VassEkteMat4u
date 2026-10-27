"""Creates constraints and sample data. Safe to run more than once.

Run from the backend folder:  python -m scripts.seed

Event-type minimums are placeholder values (decision 2026-10-27). Food items are SAMPLE DATA: the first four come
from Mateo's autumn lunch menu draft (docs/context/05_reference), the rest are invented so every event type has dishes.
Existing nodes are never overwritten (ON CREATE), so changes made by the admin survive re-seeding.
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

# Allergens to label, from the lunch menu draft, plus egg.
ALLERGENS = [
    ("fish", "Fisk", "Fish"),
    ("milk", "Melk", "Milk"),
    ("gluten", "Gluten", "Gluten"),
    ("nuts", "Nøtter", "Nuts"),
    ("celery", "Selleri", "Celery"),
    ("mustard", "Sennep", "Mustard"),
    ("egg", "Egg", "Egg"),
]

DIETS = [
    ("vegetarian", "Vegetar", "Vegetarian"),
    ("vegan", "Vegansk", "Vegan"),
    ("gluten-free", "Glutenfri", "Gluten-free"),
    ("lactose-free", "Laktosefri", "Lactose-free"),
]

# id, name_no, name_en, description_no, description_en, price_nok, min_order_qty, event types, allergens, diets
FOOD_ITEMS = [
    ("fish-soup", "Fiskesuppe med Bergen-torsk", "Fish soup with Bergen cod",
     "Med rotgrønnsaker og surdeigsbrød.", "With root vegetables and sourdough bread.",
     189, 10, ["corporate-lunch", "conference"], ["fish", "milk", "gluten", "celery"], []),
    ("voss-lamb", "Saktekokt lam fra Voss", "Slow-cooked lamb from Voss",
     "Med byggotto.", "With barley risotto.",
     245, 10, ["conference", "confirmation", "christmas-party", "wedding"], ["milk", "gluten", "celery"], []),
    ("beetroot-salad", "Rødbete- og kikertsalat", "Beetroot and chickpea salad",
     "Med geitost fra Hardanger.", "With goat cheese from Hardanger.",
     165, 8, ["corporate-lunch", "birthday", "conference", "confirmation"], ["milk", "mustard"],
     ["vegetarian", "gluten-free"]),
    ("rakfisk", "Rakfisk-smaking", "Rakfisk tasting",
     "Sesongrett, kun i november.", "Seasonal, November only.",
     210, 10, ["christmas-party"], ["fish", "milk", "gluten"], []),
    ("pinnekjott", "Pinnekjøtt med kålrabistappe", "Pinnekjøtt with mashed swede",
     "Tradisjonell julemat.", "Traditional Norwegian Christmas dish.",
     295, 15, ["christmas-party"], ["milk", "celery"], ["gluten-free"]),
    ("layer-cake", "Bløtkake med bær", "Cream layer cake with berries",
     "Hjemmelaget, med sesongens bær.", "Home-made, with berries of the season.",
     85, 10, ["birthday", "confirmation", "wedding"], ["milk", "egg", "gluten"], ["vegetarian"]),
    ("wedding-menu", "Tre-retters bryllupsmeny", "Three-course wedding menu",
     "Forrett, hovedrett og dessert, servert.", "Starter, main course and dessert, served.",
     695, 40, ["wedding"], ["fish", "milk", "gluten", "nuts", "celery"], []),
    ("lentil-stew", "Vegansk linsegryte", "Vegan lentil stew",
     "Med urter og ris.", "With herbs and rice.",
     155, 8, ["corporate-lunch", "birthday", "conference"], ["celery"],
     ["vegan", "vegetarian", "gluten-free", "lactose-free"]),
    ("sandwich-platter", "Smørbrødfat", "Open sandwich platter",
     "Utvalg av påsmurt brød.", "A selection of open sandwiches.",
     129, 10, ["corporate-lunch", "conference", "confirmation"], ["fish", "milk", "egg", "gluten", "mustard"], []),
]

CONSTRAINTS = [
    "CREATE CONSTRAINT event_type_id IF NOT EXISTS FOR (e:EventType) REQUIRE e.id IS UNIQUE",
    "CREATE CONSTRAINT food_item_id IF NOT EXISTS FOR (f:FoodItem) REQUIRE f.id IS UNIQUE",
    "CREATE CONSTRAINT customer_email IF NOT EXISTS FOR (c:Customer) REQUIRE c.email IS UNIQUE",
    "CREATE CONSTRAINT staff_email IF NOT EXISTS FOR (s:Staff) REQUIRE s.email IS UNIQUE",
    "CREATE CONSTRAINT question_id IF NOT EXISTS FOR (q:Question) REQUIRE q.id IS UNIQUE",
    "CREATE CONSTRAINT order_id IF NOT EXISTS FOR (o:Order) REQUIRE o.id IS UNIQUE",
    "CREATE CONSTRAINT allergen_code IF NOT EXISTS FOR (a:Allergen) REQUIRE a.code IS UNIQUE",
    "CREATE CONSTRAINT diet_code IF NOT EXISTS FOR (d:Diet) REQUIRE d.code IS UNIQUE",
    "CREATE CONSTRAINT image_id IF NOT EXISTS FOR (i:Image) REQUIRE i.id IS UNIQUE",
    "CREATE CONSTRAINT pin_device_token IF NOT EXISTS FOR (d:PinDevice) REQUIRE d.token_hash IS UNIQUE",
    # Not a constraint, but created the same way: the admin list and the kitchen and driver screens filter on these.
    "CREATE INDEX order_status_date IF NOT EXISTS FOR (o:Order) ON (o.status, o.event_date)",
]


def seed() -> None:
    for c in CONSTRAINTS:
        run(c)
    for id_, name_no, name_en, minimum in EVENT_TYPES:
        run(
            "MERGE (e:EventType {id: $id}) "
            "ON CREATE SET e.name_no = $no, e.name_en = $en, e.min_guests = $min",
            id=id_, no=name_no, en=name_en, min=minimum,
        )
    for label, rows in (("Allergen", ALLERGENS), ("Diet", DIETS)):
        for code, name_no, name_en in rows:
            run(
                f"MERGE (n:{label} {{code: $code}}) ON CREATE SET n.name_no = $no, n.name_en = $en",
                code=code, no=name_no, en=name_en,
            )
    for (id_, name_no, name_en, desc_no, desc_en, price, min_qty,
         event_types, allergens, diets) in FOOD_ITEMS:
        run(
            """
            MERGE (f:FoodItem {id: $id})
            ON CREATE SET f.name_no = $name_no, f.name_en = $name_en,
                          f.description_no = $desc_no, f.description_en = $desc_en,
                          f.price_nok = $price, f.min_order_qty = $min_qty, f.published = true,
                          f.just_created = true
            // Link only new items, so links the admin has changed aren't re-added.
            WITH f WHERE f.just_created
            REMOVE f.just_created
            FOREACH (eid IN $event_types |
                MERGE (e:EventType {id: eid}) MERGE (f)-[:SUITS]->(e))
            FOREACH (code IN $allergens |
                MERGE (a:Allergen {code: code}) MERGE (f)-[:CONTAINS_ALLERGEN]->(a))
            FOREACH (code IN $diets |
                MERGE (d:Diet {code: code}) MERGE (f)-[:FITS_DIET]->(d))
            """,
            id=id_, name_no=name_no, name_en=name_en, desc_no=desc_no, desc_en=desc_en,
            price=price, min_qty=min_qty, event_types=event_types, allergens=allergens, diets=diets,
        )


def main() -> None:
    with create_app().app_context():
        seed()
    print(f"Seeded {len(EVENT_TYPES)} event types, {len(ALLERGENS)} allergens, {len(DIETS)} diets "
          f"and {len(FOOD_ITEMS)} sample food items.")


if __name__ == "__main__":
    main()
