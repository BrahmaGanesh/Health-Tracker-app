# ============================================================
# AUTH ROUTES — FIXED VERSION (NO 400 ERRORS / ROBUST INPUT)
# ============================================================

from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from datetime import datetime

from extensions import db
from models import User, UserHealthProfile, UserGoal, seed_health_conditions

auth_bp = Blueprint("auth", __name__)


# ============================================================
# REGISTER
# ============================================================

@auth_bp.route("/register", methods=["GET", "POST"])
def register():

    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    if request.method == "POST":

        # SAFE INPUT HANDLING (fixes 400 issues)
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")

        print("REGISTER FORM:", request.form)  # DEBUG (keep for now)

        errors = []

        # Validation
        if len(name) < 2:
            errors.append("Name must be at least 2 characters.")

        if "@" not in email:
            errors.append("Invalid email address.")

        if User.query.filter_by(email=email).first():
            errors.append("Email already exists.")

        if len(password) < 6:
            errors.append("Password must be at least 6 characters.")

        if password != confirm:
            errors.append("Passwords do not match.")

        if errors:
            for e in errors:
                flash(e, "danger")
            return render_template("auth/register.html", name=name, email=email)

        try:
            user = User(name=name, email=email)
            user.set_password(password)

            db.session.add(user)
            db.session.flush()

            # create related records
            db.session.add(UserHealthProfile(user_id=user.id))
            db.session.add(UserGoal(user_id=user.id))

            db.session.commit()

            seed_health_conditions()

            login_user(user, remember=True)
            user.last_login = datetime.utcnow()
            db.session.commit()

            flash("Account created successfully!", "success")
            return redirect(url_for("profile.onboarding_step1"))

        except Exception as e:
            db.session.rollback()
            print("REGISTER ERROR:", e)
            flash("Server error. Try again.", "danger")
            return render_template("auth/register.html", name=name, email=email)

    return render_template("auth/register.html")


# ============================================================
# LOGIN
# ============================================================

@auth_bp.route("/login", methods=["GET", "POST"])
def login():

    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    if request.method == "POST":

        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        remember = request.form.get("remember_me") == "on"

        if not email or not password:
            flash("Enter email and password.", "danger")
            return render_template("auth/login.html", email=email)

        user = User.query.filter_by(email=email).first()

        if not user or not user.check_password(password):
            flash("Invalid credentials.", "danger")
            return render_template("auth/login.html", email=email)

        if not user.is_active:
            flash("Account disabled.", "danger")
            return render_template("auth/login.html", email=email)

        login_user(user, remember=remember)
        user.last_login = datetime.utcnow()
        db.session.commit()

        next_page = request.args.get("next")
        if next_page and next_page.startswith("/"):
            return redirect(next_page)

        flash(f"Welcome back {user.name}", "success")
        return redirect(url_for("main.dashboard"))

    return render_template("auth/login.html")


# ============================================================
# LOGOUT
# ============================================================

@auth_bp.route("/logout")
@login_required
def logout():
    name = current_user.name
    logout_user()
    flash(f"Logged out {name}", "info")
    return redirect(url_for("auth.login"))


# ============================================================
# EMAIL CHECK (FIXED - NO 400)
# ============================================================

@auth_bp.route("/check-email", methods=["POST"])
def check_email():

    # SAFE INPUT (FIX YOUR 400 HERE)
    data = request.get_json(silent=True)

    if data and "email" in data:
        email = data["email"]
    else:
        email = request.form.get("email", "")

    email = email.strip().lower()

    if not email:
        return jsonify({"available": False, "message": "Invalid email"}), 200

    exists = User.query.filter_by(email=email).first() is not None

    return jsonify({
        "available": not exists,
        "message": "Email already registered." if exists else "Email available."
    })


# ============================================================
# DARK MODE TOGGLE
# ============================================================

@auth_bp.route("/toggle-dark-mode", methods=["POST"])
@login_required
def toggle_dark_mode():

    current_user.dark_mode = not current_user.dark_mode
    db.session.commit()

    return jsonify({
        "success": True,
        "dark_mode": current_user.dark_mode
    })


# ============================================================
# DELETE ACCOUNT
# ============================================================

@auth_bp.route("/delete-account", methods=["POST"])
@login_required
def delete_account():

    password = request.form.get("password", "")

    if not current_user.check_password(password):
        flash("Wrong password", "danger")
        return redirect(url_for("profile.index"))

    try:
        user = current_user._get_current_object()
        logout_user()
        db.session.delete(user)
        db.session.commit()

        flash("Account deleted", "info")
        return redirect(url_for("auth.register"))

    except Exception as e:
        db.session.rollback()
        print("DELETE ERROR:", e)
        flash("Delete failed", "danger")
        return redirect(url_for("profile.index"))