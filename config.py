# ============================================================
# ADAPTIVE HEALTH MANAGEMENT PLATFORM
# config.py — Application Configuration
# ============================================================

import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Base configuration shared across all environments."""

    # ── CORE ─────────────────────────────────────────────────
    SECRET_KEY              = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")
    APP_NAME                = os.environ.get("APP_NAME", "HealthTrack")
    APP_TAGLINE             = os.environ.get("APP_TAGLINE", "Your Adaptive Health Recovery Platform")
    APP_VERSION             = os.environ.get("APP_VERSION", "1.0.0")

    # ── DATABASE ─────────────────────────────────────────────
    SQLALCHEMY_DATABASE_URI         = os.environ.get("DATABASE_URL", "sqlite:///health_tracker.db")
    SQLALCHEMY_TRACK_MODIFICATIONS  = False
    SQLALCHEMY_ECHO                 = False

    # ── SECURITY ─────────────────────────────────────────────
    WTF_CSRF_ENABLED                = True
    SESSION_COOKIE_SECURE           = False
    SESSION_COOKIE_HTTPONLY         = True
    SESSION_COOKIE_SAMESITE         = "Lax"
    PERMANENT_SESSION_LIFETIME      = timedelta(days=30)
    REMEMBER_COOKIE_DURATION        = timedelta(days=30)
    REMEMBER_COOKIE_HTTPONLY        = True

    # ── MAIL ─────────────────────────────────────────────────
    MAIL_SERVER         = os.environ.get("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT           = int(os.environ.get("MAIL_PORT", 587))
    MAIL_USE_TLS        = os.environ.get("MAIL_USE_TLS", "True") == "True"
    MAIL_USERNAME       = os.environ.get("MAIL_USERNAME", "")
    MAIL_PASSWORD       = os.environ.get("MAIL_PASSWORD", "")
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER", "")

    # ── UPLOADS ──────────────────────────────────────────────
    UPLOAD_FOLDER       = os.environ.get("UPLOAD_FOLDER", "static/uploads")
    MAX_CONTENT_LENGTH  = int(os.environ.get("MAX_CONTENT_LENGTH", 5 * 1024 * 1024))  # 5MB
    ALLOWED_EXTENSIONS  = {"png", "jpg", "jpeg", "gif", "webp"}

    # ── CACHE ────────────────────────────────────────────────
    CACHE_TYPE              = os.environ.get("CACHE_TYPE", "SimpleCache")
    CACHE_DEFAULT_TIMEOUT   = int(os.environ.get("CACHE_DEFAULT_TIMEOUT", 300))

    # ── PAGINATION ───────────────────────────────────────────
    RECORDS_PER_PAGE    = 20
    RECIPES_PER_PAGE    = 12

    # ── HEALTH CONSTANTS ─────────────────────────────────────
    # BP thresholds (mmHg)
    BP_NORMAL_SYS       = 120
    BP_NORMAL_DIA       = 80
    BP_ELEVATED_SYS     = 130
    BP_ELEVATED_DIA     = 85
    BP_HIGH_SYS         = 140
    BP_HIGH_DIA         = 90
    BP_CRISIS_SYS       = 180
    BP_CRISIS_DIA       = 120

    # Sugar thresholds (mg/dL)
    SUGAR_NORMAL_FASTING    = 100
    SUGAR_PREDIABETES       = 126
    SUGAR_DIABETES          = 126

    # BMI thresholds
    BMI_UNDERWEIGHT     = 18.5
    BMI_NORMAL_MAX      = 24.9
    BMI_OVERWEIGHT_MAX  = 29.9
    BMI_OBESE_1_MAX     = 34.9
    BMI_OBESE_2_MAX     = 39.9

    # Daily targets (defaults)
    DEFAULT_CALORIES    = 2000
    DEFAULT_PROTEIN     = 80
    DEFAULT_CARBS       = 250
    DEFAULT_FATS        = 65
    DEFAULT_FIBER       = 30
    DEFAULT_SODIUM      = 2000      # mg — WHO recommendation
    DEFAULT_WATER       = 2.5       # litres
    DEFAULT_STEPS       = 8000

    # ── SCHEDULER ────────────────────────────────────────────
    SCHEDULER_API_ENABLED   = False
    JOBS = [
        {
            "id":       "daily_aggregation",
            "func":     "utils.scheduler:run_daily_aggregation",
            "trigger":  "cron",
            "hour":     0,
            "minute":   5,
        },
        {
            "id":       "weekly_insights",
            "func":     "utils.scheduler:run_weekly_insights",
            "trigger":  "cron",
            "day_of_week": "sun",
            "hour":     6,
        },
    ]


class DevelopmentConfig(Config):
    """Development-specific configuration."""
    DEBUG               = True
    TESTING             = False
    SQLALCHEMY_ECHO     = False


class ProductionConfig(Config):
    """Production-specific configuration."""
    DEBUG                       = False
    TESTING                     = False
    SESSION_COOKIE_SECURE       = True
    SQLALCHEMY_ECHO             = False
    WTF_CSRF_SSL_STRICT         = True


class TestingConfig(Config):
    """Testing-specific configuration."""
    TESTING                         = True
    DEBUG                           = True
    SQLALCHEMY_DATABASE_URI         = "sqlite:///:memory:"
    WTF_CSRF_ENABLED                = False


# ── CONFIG SELECTOR ──────────────────────────────────────────
config = {
    "development":  DevelopmentConfig,
    "production":   ProductionConfig,
    "testing":      TestingConfig,
    "default":      DevelopmentConfig,
}


def get_config():
    env = os.environ.get("FLASK_ENV", "development")
    return config.get(env, DevelopmentConfig)