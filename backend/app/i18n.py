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
        "cart": "Handlekurv",
        "portions": "Porsjoner",
        "add_to_cart": "Legg i handlekurv",
        "added_to_cart": "{qty} porsjoner lagt i handlekurven.",
        "invalid_quantity": "Skriv et helt tall fra 1 til {max}.",
        "cart_other_event_type": "Handlekurven gjelder et annet arrangement. Tøm handlekurven for å bestille til dette.",
        "dish_unavailable": "Retten er ikke tilgjengelig for dette arrangementet.",
        "cart_unavailable_removed": "Noen retter er ikke lenger tilgjengelige og er fjernet fra handlekurven.",
        "cart_empty": "Handlekurven er tom.",
        "back_to_menu": "Til menyene",
        "cart_for_event": "Bestilling til: {event}",
        "number_of_guests": "Antall gjester",
        "dish": "Rett",
        "price": "Pris (kr)",
        "line_total": "Sum (kr)",
        "remove": "Fjern",
        "total": "Totalt",
        "update_cart": "Oppdater handlekurv",
        "cart_updated": "Handlekurven er oppdatert.",
        "clear_cart": "Tøm handlekurven",
        "cannot_order_yet": "Kan ikke bestilles ennå",
        "guests_missing": "Skriv inn antall gjester.",
        "guests_below_minimum": "Dette arrangementet krever minst {n} gjester.",
        "dish_below_minimum": "{dish}: minst {n} porsjoner.",
        "cart_ok": "Handlekurven oppfyller minstekravene.",
        "continue_to_order": "Gå videre til bestilling",
        "order_coming": "Bestilling kommer i neste versjon.",
        "log_in": "Logg inn",
        "log_out": "Logg ut",
        "register": "Registrer deg",
        "name": "Navn",
        "email": "E-post",
        "phone": "Telefon",
        "optional": "valgfritt",
        "password": "Passord",
        "password_repeat": "Gjenta passordet",
        "name_required": "Skriv inn navnet ditt.",
        "email_invalid": "Skriv inn en gyldig e-postadresse.",
        "email_taken": "Det finnes allerede en konto med denne e-postadressen. Logg inn i stedet.",
        "password_length": "Passordet må ha {min}–{max} tegn.",
        "passwords_differ": "Passordene er ikke like.",
        "welcome": "Velkommen, {name}! Kontoen er opprettet.",
        "logged_in": "Du er logget inn som {name}.",
        "logged_out": "Du er logget ut.",
        "login_failed": "Feil e-post eller passord.",
        "have_account": "Har du allerede en konto?",
        "no_account": "Ny kunde?",
        "forgot_password_hint": "Glemt passordet? Kontakt Ekte Mat, så hjelper vi deg.",
        "log_in_to_order": "Logg inn for å bestille",
        "cart_kept_on_login": "Handlekurven blir tatt vare på når du logger inn.",
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
        "cart": "Cart",
        "portions": "Portions",
        "add_to_cart": "Add to cart",
        "added_to_cart": "{qty} portions added to your cart.",
        "invalid_quantity": "Enter a whole number from 1 to {max}.",
        "cart_other_event_type": "Your cart is for another event. Empty the cart to order for this one.",
        "dish_unavailable": "This dish isn't available for this event.",
        "cart_unavailable_removed": "Some dishes are no longer available and were removed from your cart.",
        "cart_empty": "Your cart is empty.",
        "back_to_menu": "Back to the menus",
        "cart_for_event": "Order for: {event}",
        "number_of_guests": "Number of guests",
        "dish": "Dish",
        "price": "Price (NOK)",
        "line_total": "Total (NOK)",
        "remove": "Remove",
        "total": "Total",
        "update_cart": "Update cart",
        "cart_updated": "Your cart is updated.",
        "clear_cart": "Empty the cart",
        "cannot_order_yet": "Can't be ordered yet",
        "guests_missing": "Enter the number of guests.",
        "guests_below_minimum": "This event needs at least {n} guests.",
        "dish_below_minimum": "{dish}: at least {n} portions.",
        "cart_ok": "Your cart meets the minimums.",
        "continue_to_order": "Continue to order",
        "order_coming": "Ordering comes in the next version.",
        "log_in": "Log in",
        "log_out": "Log out",
        "register": "Register",
        "name": "Name",
        "email": "E-mail",
        "phone": "Phone",
        "optional": "optional",
        "password": "Password",
        "password_repeat": "Repeat password",
        "name_required": "Enter your name.",
        "email_invalid": "Enter a valid e-mail address.",
        "email_taken": "There's already an account with this e-mail address. Log in instead.",
        "password_length": "The password must be {min}–{max} characters.",
        "passwords_differ": "The passwords don't match.",
        "welcome": "Welcome, {name}! Your account is created.",
        "logged_in": "You're logged in as {name}.",
        "logged_out": "You're logged out.",
        "login_failed": "Wrong e-mail or password.",
        "have_account": "Already have an account?",
        "no_account": "New customer?",
        "forgot_password_hint": "Forgot your password? Contact Ekte Mat and we'll help you.",
        "log_in_to_order": "Log in to order",
        "cart_kept_on_login": "Your cart is kept when you log in.",
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
