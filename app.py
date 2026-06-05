# ============================================================
# ADAPTIVE HEALTH MANAGEMENT PLATFORM
# app.py — Flask Application Factory (PRODUCTION SAFE)
# ============================================================

import os
from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_bcrypt import Bcrypt
from flask_migrate import Migrate
from flask_mail import Mail
from flask_caching import Cache

from config import get_config
from extensions import db, bcrypt, login_manager, migrate, mail, cache


def create_app(config_class=None):
    app = Flask(__name__)

    # ── CONFIG ───────────────────────────────────────────────
    if config_class is None:
        config_class = get_config()
    app.config.from_object(config_class)

    # ── INIT EXTENSIONS ──────────────────────────────────────
    db.init_app(app)
    bcrypt.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    mail.init_app(app)
    cache.init_app(app)

    # ── LOGIN CONFIG ─────────────────────────────────────────
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Please log in to access this page."
    login_manager.login_message_category = "info"
    login_manager.session_protection = "strong"

    # IMPORTANT: safe import (avoid crash at startup)
    @login_manager.user_loader
    def load_user(user_id):
        from models import User
        return User.query.get(int(user_id))

    # ── BLUEPRINTS ───────────────────────────────────────────
    from routes.auth_routes import auth_bp
    from routes.main_routes import main_bp
    from routes.profile_routes import profile_bp
    from routes.bp_routes import bp_bp
    from routes.meal_routes import meal_bp
    from routes.nutrition_routes import nutrition_bp
    from routes.tracker_routes import tracker_bp
    from routes.analytics_routes import analytics_bp
    from routes.alert_routes import alert_bp

    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(main_bp, url_prefix="/")
    app.register_blueprint(profile_bp, url_prefix="/profile")
    app.register_blueprint(bp_bp, url_prefix="/bp")
    app.register_blueprint(meal_bp, url_prefix="/meal")
    app.register_blueprint(nutrition_bp, url_prefix="/nutrition")
    app.register_blueprint(tracker_bp, url_prefix="/tracker")
    app.register_blueprint(analytics_bp, url_prefix="/analytics")
    app.register_blueprint(alert_bp, url_prefix="/alerts")

    # ── CONTEXT PROCESSOR ───────────────────────────────────
    @app.context_processor
    def inject_globals():
        from flask_login import current_user

        unread_alerts = 0
        if current_user.is_authenticated:
            try:
                from models import Alert
                unread_alerts = Alert.query.filter_by(
                    user_id=current_user.id,
                    is_read=False
                ).count()
            except Exception:
                unread_alerts = 0

        return {
            "app_name": app.config.get("APP_NAME", "HealthTrack"),
            "app_version": app.config.get("APP_VERSION", "1.0.0"),
            "unread_alerts": unread_alerts,
        }

    # ── TEMPLATE FILTERS ─────────────────────────────────────
    @app.template_filter("datetime_format")
    def datetime_format(value, fmt="%d %b %Y"):
        return value.strftime(fmt) if value else "—"

    @app.template_filter("time_format")
    def time_format(value):
        return value.strftime("%I:%M %p") if value else "—"

    @app.template_filter("round2")
    def round2(value):
        try:
            return round(float(value), 1)
        except:
            return 0

    @app.template_filter("bmi_status")
    def bmi_status(bmi):
        if bmi is None:
            return "Unknown"
        bmi = float(bmi)
        if bmi < 18.5:
            return "Underweight"
        elif bmi < 25:
            return "Normal"
        elif bmi < 30:
            return "Overweight"
        elif bmi < 35:
            return "Obese I"
        elif bmi < 40:
            return "Obese II"
        return "Obese III"

    @app.template_filter("bp_status")
    def bp_status(sys, dia=None):
        if dia is None:
            return "Unknown"

        s, d = int(sys), int(dia)

        if s < 120 and d < 80:
            return "Normal"
        elif s < 130 and d < 80:
            return "Elevated"
        elif s < 140 or d < 90:
            return "High Stage 1"
        elif s < 180 or d < 120:
            return "High Stage 2"
        return "Crisis"

    # ── ERROR HANDLERS ───────────────────────────────────────
    @app.errorhandler(404)
    def not_found(e):
        return render_template("errors/404.html"), 404

    @app.errorhandler(403)
    def forbidden(e):
        return render_template("errors/403.html"), 403

    @app.errorhandler(500)
    def server_error(e):
        return render_template("errors/500.html"), 500

    @app.route("/favicon.ico")
    def favicon():
        return "", 204

    # ❌ IMPORTANT: DO NOT use db.create_all() in production

    return app


# ── ENTRY POINT ─────────────────────────────────────────────
app = create_app()

# if __name__ == "__main__":
#     port = int(os.environ.get("PORT", 10000))
#     app.run(debug=True, host="0.0.0.0", port=port)