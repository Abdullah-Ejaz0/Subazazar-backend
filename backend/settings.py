"""
Django settings for backend project — Supabase architecture.

All database logic lives in Supabase stored procedures.
Django has NO ORM models. DATABASES is intentionally empty.
"""

from pathlib import Path
from dotenv import load_dotenv
import os

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv('DJANGO_SECRET_KEY')

DEBUG = os.getenv('DEBUG', 'False') == 'True'

ALLOWED_HOSTS = ['*']

INSTALLED_APPS = [
    'rest_framework',
    'drf_spectacular',
    'api',
]

MIDDLEWARE = [
    'django.middleware.common.CommonMiddleware',
]

ROOT_URLCONF = 'backend.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [],
        },
    },
]

WSGI_APPLICATION = 'backend.wsgi.application'

# Intentionally empty — Django does NOT manage the database.
# All DB operations go through Supabase Python client.
DATABASES = {}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [],
    'DEFAULT_PERMISSION_CLASSES': [],
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'UNAUTHENTICATED_USER': None,
    'UNAUTHENTICATED_TOKEN': None,
}

SPECTACULAR_SETTINGS = {
    "COMPONENT_SPLIT_REQUEST": True,
    'TITLE': 'Sabzazaar API',
    'DESCRIPTION': 'Backend API for Sabzazaar (Supabase-backed).',
    'VERSION': '1.0.0',
    # Work around Windows stderr issues that raise OSError in drf-spectacular.
    'DISABLE_ERRORS_AND_WARNINGS': True,
}
