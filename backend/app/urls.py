"""URL helpers."""
from urllib.parse import urlparse

from flask import url_for


def safe_next(target: str | None, default_endpoint: str = "menu.index") -> str:
    """`target` if it's a path on this site, otherwise the default page. Prevents open redirects."""
    target = (target or "").strip()
    if not target.startswith("/") or target.startswith("//") or "\\" in target or urlparse(target).netloc:
        return url_for(default_endpoint)
    return target
