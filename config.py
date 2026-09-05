import os
from dotenv import load_dotenv

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
env_path = os.path.join(BASE_DIR, '.env')
load_dotenv(env_path)

from datetime import timedelta
from urllib.parse import quote, unquote

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


def get_database_uri():
    database_url = os.environ.get('DATABASE_URL', '').strip()
    if not database_url:
        return f"sqlite:///{os.path.join(BASE_DIR, 'paprep.db')}"

    # Normalize older postgres:// URLs to the SQLAlchemy-compatible form.
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)

    # Safely handle special characters in password (such as '@' or '#')
    if database_url.startswith('postgresql://'):
        try:
            prefix, rest = database_url.split('://', 1)
            if '@' in rest:
                last_at = rest.rfind('@')
                user_pass = rest[:last_at]
                host_db = rest[last_at + 1:]
                if ':' in user_pass:
                    user, password = user_pass.split(':', 1)
                    unquoted_pass = unquote(password)
                    quoted_pass = quote(unquoted_pass, safe='')
                    database_url = f"{prefix}://{user}:{quoted_pass}@{host_db}"
        except Exception:
            pass

    return database_url



class Config:
    SECRET_KEY = os.environ.get(
        'SECRET_KEY',
        'paprep-dev-key-CHANGE-this-in-production-2024!'
    )
    
    # Gemini AI configuration
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
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
