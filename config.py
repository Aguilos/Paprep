import os
from datetime import timedelta

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


def get_database_uri():
    database_url = os.environ.get('DATABASE_URL', '').strip()
    if not database_url:
        return f"sqlite:///{os.path.join(BASE_DIR, 'paprep.db')}"

    # Normalize older postgres:// URLs to the SQLAlchemy-compatible form.
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)

    return database_url


class Config:
    SECRET_KEY = os.environ.get(
        'SECRET_KEY',
        'paprep-dev-key-CHANGE-this-in-production-2024!'
    )
    SQLALCHEMY_DATABASE_URI = get_database_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {}

    if SQLALCHEMY_DATABASE_URI.startswith('postgresql'):
        if 'sslmode=' not in SQLALCHEMY_DATABASE_URI:
            SQLALCHEMY_ENGINE_OPTIONS['connect_args'] = {'sslmode': 'require'}

    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = None
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads', 'modules')
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50 MB max upload
