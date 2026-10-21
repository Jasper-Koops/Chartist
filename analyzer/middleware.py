from collections.abc import Callable

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.utils import translation


class LanguageMiddleware:
    """
    Show the site in the language picked in the header (kept in a cookie by
    Django's set_language), and in Dutch otherwise. Unlike Django's
    LocaleMiddleware, it does not follow the browser's language: Dutch is
    the default for everyone.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        picked = request.COOKIES.get(settings.LANGUAGE_COOKIE_NAME)
        language = (
            picked
            if picked in dict(settings.LANGUAGES)
            else settings.LANGUAGE_CODE
        )
        translation.activate(language)
        request.LANGUAGE_CODE = language
        response = self.get_response(request)
        response.headers.setdefault("Content-Language", language)
        translation.deactivate()
        return response
