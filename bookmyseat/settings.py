"""
Django settings for bookmyseat project.
"""

from pathlib import Path
import os

import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent


def _load_local_env():
    env_path = BASE_DIR / '.env'
    if not env_path.exists():
        return
    for raw in env_path.read_text(encoding='utf-8').splitlines():
        line = raw.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, val = line.split('=', 1)
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        os.environ.setdefault(key, val)


def _env_clean(name, default=''):
    val = os.environ.get(name, default)
    if val is None:
        return default
    return str(val).strip().strip('"').strip("'")


_load_local_env()

SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'django-insecure-c8aetlj(=vp90n@#yoc^&d(_6ivp(d!bv-4-f!r$lawptjzrwu')

DEBUG = os.environ.get('DJANGO_DEBUG', 'True').lower() == 'true'

allowed_hosts_env = os.environ.get('DJANGO_ALLOWED_HOSTS', '')
if allowed_hosts_env:
    ALLOWED_HOSTS = [host.strip() for host in allowed_hosts_env.split(',') if host.strip()]
else:
    ALLOWED_HOSTS = ['127.0.0.1', 'localhost', '0.0.0.0', '[::1]', 'testserver']
if DEBUG and '*' not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append('*')

csrf_trusted_origins_env = os.environ.get('DJANGO_CSRF_TRUSTED_ORIGINS', '')
if csrf_trusted_origins_env:
    CSRF_TRUSTED_ORIGINS = [origin.strip() for origin in csrf_trusted_origins_env.split(',') if origin.strip()]

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'users',
    'movies.apps.MoviesConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'bookmyseat.urls'
LOGIN_URL = '/login/'
AUTH_USER_MODEL = 'auth.User'
EMAIL_BACKEND = os.environ.get('EMAIL_BACKEND', 'django.core.mail.backends.console.EmailBackend')
EMAIL_HOST = _env_clean('EMAIL_HOST', '')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', '587'))
EMAIL_HOST_USER = _env_clean('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = _env_clean('EMAIL_HOST_PASSWORD', '')
EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', 'True').lower() == 'true'
EMAIL_USE_SSL = os.environ.get('EMAIL_USE_SSL', 'False').lower() == 'true'
DEFAULT_FROM_EMAIL = _env_clean('DEFAULT_FROM_EMAIL', 'no-reply@bookmyseat.local')

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'bookmyseat.wsgi.application'

DATABASES = {
    'default': dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=600,
    )
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

SEAT_PRICE_INR = int(os.environ.get('SEAT_PRICE_INR', '200'))
RAZORPAY_KEY_ID = _env_clean('RAZORPAY_KEY_ID', '')
RAZORPAY_KEY_SECRET = _env_clean('RAZORPAY_KEY_SECRET', '')
RAZORPAY_WEBHOOK_SECRET = _env_clean('RAZORPAY_WEBHOOK_SECRET', '')
PAYMENT_MOCK_MODE = os.environ.get('PAYMENT_MOCK_MODE', 'False').lower() == 'true'

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'bookmyseat-admin-analytics',
        'TIMEOUT': int(os.environ.get('ANALYTICS_CACHE_TIMEOUT_SECONDS', '60')),
    }
}

# Session flags to reduce privilege escalation risk via script access or fixation.
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False
SESSION_COOKIE_SAMESITE = 'Lax'

if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        'movies.email': {
            'handlers': ['console'],
            'level': os.environ.get('EMAIL_LOG_LEVEL', 'INFO'),
            'propagate': False,
        },
    },
}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
