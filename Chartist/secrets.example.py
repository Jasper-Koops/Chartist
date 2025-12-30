from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY: str = "SET-VALUE-HERE"

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG: bool = True
ALLOWED_HOSTS: list[str] = []

# Database
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases

DATABASES: dict[str, dict[str, str | Path]] = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR.parent / "db.sqlite3",
    }
}
