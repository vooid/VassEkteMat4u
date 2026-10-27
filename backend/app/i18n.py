"""Norwegian/English interface (decision 2026-10-27).

UI strings live in TEXTS; data is stored with _no/_en properties and picked with `tr()`.
"""
from flask import Flask, g, request, session

LANGUAGES = ("no", "en")
DEFAULT_LANGUAGE = "no"

TEXTS = {
    "no": {
        "site_title": "Ekte Mat – catering i Bergen",
        "menu_heading": "Menyer",
        "menu_intro": "Velg type arrangement for å se menyene. Alle priser er per person.",
        "min_guests": "Minst {n} gjester",
        "minimum_order": "Minstebestilling: {n}",
        "per_person": "kr / pers.",
        "allergens": "Allergener",
        "no_allergens": "Ingen merkepliktige allergener",
        "no_items": "Ingen retter for denne typen arrangement ennå.",
        "no_image": "Bilde kommer",
        "language": "Språk",
        "other_language": "English",
    },
    "en": {
        "site_title": "Ekte Mat – catering in Bergen",
        "menu_heading": "Menus",
        "menu_intro": "Choose a type of event to see its menus. All prices are per person.",
        "min_guests": "At least {n} guests",
        "minimum_order": "Minimum order: {n}",
        "per_person": "NOK / person",
        "allergens": "Allergens",
        "no_allergens": "No allergens to declare",
        "no_items": "No dishes for this type of event yet.",
        "no_image": "Photo coming soon",
        "language": "Language",
        "other_language": "Norsk",
    },
}


def current_language() -> str:
    return g.get("lang", DEFAULT_LANGUAGE)


def t(key: str, **kwargs) -> str:
    """Translate a UI string into the current language."""
    text = TEXTS[current_language()].get(key) or TEXTS[DEFAULT_LANGUAGE].get(key, key)
    return text.format(**kwargs) if kwargs else text


def tr(obj: dict, field: str) -> str:
    """Pick obj[field_no] or obj[field_en], falling back to Norwegian."""
    return obj.get(f"{field}_{current_language()}") or obj.get(f"{field}_{DEFAULT_LANGUAGE}") or ""


def init_app(app: Flask) -> None:
    @app.before_request
    def set_language():
        g.lang = session.get("lang") if session.get("lang") in LANGUAGES else DEFAULT_LANGUAGE
        # The <html lang> attribute uses "nb" (Norwegian Bokmål) for "no".
        g.html_lang = "nb" if g.lang == "no" else "en"

    app.jinja_env.globals.update(t=t, tr=tr, current_language=current_language)
