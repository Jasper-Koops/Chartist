from pathlib import Path

from django import template
from django.contrib.staticfiles import finders
from django.templatetags.static import static

register = template.Library()


@register.simple_tag
def asset(path: str) -> str:
    """
    The static URL with the file's modification time as version, so the
    browser fetches a changed file instead of using its cached copy.
    """
    url = static(path)
    found = finders.find(path)
    if not found:
        return url
    return f"{url}?v={int(Path(str(found)).stat().st_mtime)}"
