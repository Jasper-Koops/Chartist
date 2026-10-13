from django.conf import settings
from django.contrib import admin
from django.urls import URLPattern, URLResolver, path, include

urlpatterns: list[URLPattern | URLResolver] = [
    path("admin/", admin.site.urls),
    path("api/v1/", include("api.urls")),
    path("", include("analyzer.urls")),
]

if settings.DEBUG_TOOLBAR:
    from debug_toolbar.toolbar import debug_toolbar_urls

    urlpatterns += debug_toolbar_urls()
