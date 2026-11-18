"""Settings for the NYC distressed property finder. Values come from .env."""
import os
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-change-me")
DEBUG = os.environ.get("DEBUG", "1") == "1"
ALLOWED_HOSTS = [h for h in os.environ.get("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if h]

# Production (behind nginx with HTTPS): set CSRF_TRUSTED_ORIGINS=https://your-domain
CSRF_TRUSTED_ORIGINS = [o for o in os.environ.get("CSRF_TRUSTED_ORIGINS", "").split(",") if o]
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "leads",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# Postgres by default (see docker-compose.yml). Override with DATABASE_URL.
DATABASES = {
    "default": dj_database_url.parse(
        os.environ.get("DATABASE_URL", "postgres://nycleads:nycleads@localhost:5432/nycleads")
    )
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "America/New_York"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "lead_list"
LOGOUT_REDIRECT_URL = "login"

# NYC Open Data
SOCRATA_BASE_URL = "https://data.cityofnewyork.us/resource"
SOCRATA_APP_TOKEN = os.environ.get("SOCRATA_APP_TOKEN", "")
CLASS_B_LIST_FILE = os.environ.get("CLASS_B_LIST_FILE", "")
TARGET_ZIP_CODES = [z.strip() for z in os.environ.get("TARGET_ZIP_CODES", "").split(",") if z.strip()]

# Target building rule from the client: 0-1 Class A units, 1-15 Class B units.
MAX_CLASS_A_UNITS = int(os.environ.get("MAX_CLASS_A_UNITS", "1"))
MIN_CLASS_B_UNITS = int(os.environ.get("MIN_CLASS_B_UNITS", "1"))
MAX_CLASS_B_UNITS = int(os.environ.get("MAX_CLASS_B_UNITS", "15"))
