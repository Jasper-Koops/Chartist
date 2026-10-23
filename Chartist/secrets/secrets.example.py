from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
SECRET_KEY = "replace-with-a-generated-local-secret-key"
DEBUG = True
ALLOWED_HOSTS = ["127.0.0.1", "localhost", "[::1]"]
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}
