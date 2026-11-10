"""Configurações do site de conferência de pedidos."""
import os
import sys
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent
RAIZ = BASE_DIR.parent
# Permite `import conferencia` (regras de negócio na raiz do repositório).
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

DEBUG = os.environ.get("DEBUG", "False").strip().lower() in ("1", "true", "sim", "yes")

SECRET_KEY = os.environ.get("SECRET_KEY", "")
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = "chave-insegura-somente-para-desenvolvimento"
    else:
        raise ImproperlyConfigured("A variável de ambiente SECRET_KEY é obrigatória.")

ALLOWED_HOSTS = [h.strip() for h in os.environ.get("ALLOWED_HOSTS", "").split(",") if h.strip()]
if DEBUG and not ALLOWED_HOSTS:
    ALLOWED_HOSTS = ["localhost", "127.0.0.1", "testserver"]

INSTALLED_APPS = [
    "pedidos.apps_admin.AdminSomenteSuperusuario",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "whitenoise.runserver_nostatic",
    "django.contrib.staticfiles",
    "pedidos",
]

AUTHENTICATION_BACKENDS = ["pedidos.autenticacao.BackendComBloqueio"]

MIDDLEWARE = [
    "pedidos.middleware.SaudeMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "pedidos.middleware.LimiteTamanhoMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "pedidos.middleware.LimiteArquivosLoteMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "site_conferencia.urls"

TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [],
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
    ]},
}]

WSGI_APPLICATION = "site_conferencia.wsgi.application"

if not DEBUG and not os.environ.get("DATABASE_URL"):
    raise ImproperlyConfigured("A variável de ambiente DATABASE_URL é obrigatória em produção.")
DATABASES = {"default": dj_database_url.config(
    default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
    conn_max_age=60, conn_health_checks=True, ssl_require=not DEBUG)}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
if DEBUG:
    # O WhiteNoise avisa se a pasta não existir; em produção o collectstatic a cria.
    STATIC_ROOT.mkdir(exist_ok=True)
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": (
        "django.contrib.staticfiles.storage.StaticFilesStorage" if DEBUG
        else "whitenoise.storage.CompressedManifestStaticFilesStorage")},
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# URLs do app não têm barra final (/entrar, /sair); /admin/ continua funcionando.
APPEND_SLASH = False
LOGIN_URL = "entrar"
LOGIN_REDIRECT_URL = "/"

# Uploads: até 10 MB por arquivo, 30 planilhas por lote e 100 MB no lote inteiro
# (o corte pelo tamanho total está em pedidos/middleware.py).
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
DATA_UPLOAD_MAX_NUMBER_FILES = 30

# Sessão expira após 12 horas sem uso.
SESSION_COOKIE_AGE = 43200
SESSION_SAVE_EVERY_REQUEST = True

# Logs no stderr (o Render guarda). Sem corpo de requisição; 4xx do django.request ficam de fora.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"padrao": {"format": "%(asctime)s %(levelname)s %(name)s: %(message)s"}},
    "handlers": {"console": {
        "class": "logging.StreamHandler", "stream": "ext://sys.stderr", "formatter": "padrao"}},
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "django": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "django.request": {"level": "ERROR", "propagate": True},
        "pedidos": {"handlers": ["console"], "level": "INFO", "propagate": False},
    },
}

if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
