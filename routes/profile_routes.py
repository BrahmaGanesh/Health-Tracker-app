# ============================================================
# ADAPTIVE HEALTH MANAGEMENT PLATFORM
# routes/profile_routes.py — Health Profile & Onboarding
# ============================================================

from flask import (
    Blueprint, render_template, redirect,
    url_for, flash, request, jsonify
)
from flask_login import login_required, current_user
from datetime import date, datetime

# from app import db
from extensions import db
from models import (
    User, UserHealthProfile, UserGoal,
    UserCondition, HealthCondition
)

profile_bp = Blueprint("profile", __name__)


# ============================================================
# ONBOARDING — STEP 1: Personal Details
# ============================================================

@profile_bp.route("/onboarding/step1", methods=["GET", "POST"])
@login_required
def onboarding_step1():
    """Screen 1: Name + Gender + Date of Birth."""

    if request.method == "POST":
        name  = request.form.get("name", "").strip()
        gender = request.form.get("gender", "")
        dob_str = request.form.get("date_of_birth", "")

        errors = []
        if not name or len(name) < 2:
            errors.append("Please enter your full name.")
        if not gender:
            errors.append("Please select your gender.")
        if not dob_str:
            errors.append("Please enter your date of birth.")

        dob = None
        if dob_str:
            try:
                dob = datetime.strptime(dob_str, "%Y-%m-%d").date()
                if dob >= date.today():
                    errors.append("Date of birth must be in the past.")
                age = (date.today() - dob).days // 365
                if age < 10 or age > 110:
                    errors.append("Please enter a valid date of birth.")
            except ValueError:
                errors.append("Invalid date format.")

        if errors:
            for e in errors:
                flash(e, "danger")
            return render_template(
                "auth/onboarding/step1.html",
                name=name, gender=gender, dob=dob_str
            )

        # Save
        current_user.name = name
        profile = current_user.health_profile
        if not profile:
            profile = UserHealthProfile(user_id=current_user.id)
            db.session.add(profile)

        profile.gender        = gender
        profile.date_of_birth = dob
        profile.onboarding_step = 2
        db.session.commit()

        return redirect(url_for("profile.onboarding_step2"))

    return render_template(
        "auth/onboarding/step1.html",
        name=current_user.name,
        gender=current_user.health_profile.gender if current_user.health_profile else "",
        dob=current_user.health_profile.date_of_birth.strftime("%Y-%m-%d")
             if current_user.health_profile and current_user.health_profile.date_of_birth else ""
    )


# ============================================================
# ONBOARDING — STEP 2: Body Measurements
# ============================================================

@profile_bp.route("/onboarding/step2", methods=["GET", "POST"])
@login_required
def onboarding_step2():
    """Screen 2: Height + Weight."""

    if request.method == "POST":
        height_str = request.form.get("height_cm", "")
        weight_str = request.form.get("weight_kg", "")

        errors = []

        height = None
        try:
            height = float(height_str)
            if not (100 <= height <= 250):
                errors.append("Height must be between 100cm and 250cm.")
        except (ValueError, TypeError):
            errors.append("Please enter a valid height in cm.")

        weight = None
        try:
            weight = float(weight_str)
            if not (20 <= weight <= 300):
                errors.append("Weight must be between 20kg and 300kg.")
        except (ValueError, TypeError):
            errors.append("Please enter a valid weight in kg.")

        if errors:
            for e in errors:
                flash(e, "danger")
            return render_template(
                "auth/onboarding/step2.html",
                height=height_str, weight=weight_str
            )

        profile = current_user.health_profile
        profile.height_cm         = height
        profile.current_weight_kg = weight
        profile.onboarding_step   = 3

        # Set start weight in goals
        goals = current_user.goals
        if not goals:
            goals = UserGoal(user_id=current_user.id)
            db.session.add(goals)
        goals.start_weight_kg = weight

        db.session.commit()
        return redirect(url_for("profile.onboarding_step3"))

    p = current_user.health_profile
    return render_template(
        "auth/onboarding/step2.html",
        height=p.height_cm if p else "",
        weight=p.current_weight_kg if p else ""
    )


# ============================================================
# ONBOARDING — STEP 3: Health Conditions
# ============================================================

@profile_bp.route("/onboarding/step3", methods=["GET", "POST"])
@login_required
def onboarding_step3():
    """Screen 3: Select all health conditions."""

    all_conditions = HealthCondition.query.order_by(
        HealthCondition.category, HealthCondition.name
    ).all()

    if request.method == "POST":
        selected_ids = request.form.getlist("conditions")

        # Remove existing conditions
        UserCondition.query.filter_by(user_id=current_user.id).delete()

        # Add selected
        for cid in selected_ids:
            try:
                cond = HealthCondition.query.get(int(cid))
                if cond:
                    uc = UserCondition(
                        user_id=current_user.id,
                        condition_id=cond.id
                    )
                    db.session.add(uc)
            except (ValueError, TypeError):
                continue

        current_user.health_profile.onboarding_step = 4
        db.session.commit()
        return redirect(url_for("profile.onboarding_step4"))

    # Pre-select existing
    existing_ids = [uc.condition_id for uc in current_user.conditions]

    return render_template(
        "auth/onboarding/step3.html",
        all_conditions=all_conditions,
        existing_ids=existing_ids
    )


# ============================================================
# ONBOARDING — STEP 4: Goals
# ============================================================

@profile_bp.route("/onboarding/step4", methods=["GET", "POST"])
@login_required
def onboarding_step4():
    """Screen 4: Target weight, goal speed, primary goal."""

    if request.method == "POST":
        target_weight_str = request.form.get("target_weight", "")
        goal_speed        = request.form.get("goal_speed", "normal")
        primary_goal      = request.form.get("primary_goal", "healthy_lifestyle")

        errors = []

        target_weight = None
        if target_weight_str:
            try:
                target_weight = float(target_weight_str)
                if not (20 <= target_weight <= 300):
                    errors.append("Target weight must be between 20kg and 300kg.")
            except (ValueError, TypeError):
                errors.append("Please enter a valid target weight.")

        if errors:
            for e in errors:
                flash(e, "danger")
            return render_template(
                "auth/onboarding/step4.html",
                target_weight=target_weight_str,
                goal_speed=goal_speed,
                primary_goal=primary_goal
            )

        goals = current_user.goals
        if not goals:
            goals = UserGoal(user_id=current_user.id)
            db.session.add(goals)

        if target_weight:
            goals.target_weight_kg = target_weight
        goals.goal_speed    = goal_speed
        goals.primary_goal  = primary_goal
        goals.goal_start_date = date.today()

        current_user.health_profile.onboarding_step = 5
        db.session.commit()
        return redirect(url_for("profile.onboarding_step5"))

    g = current_user.goals
    p = current_user.health_profile
    return render_template(
        "auth/onboarding/step4.html",
        current_weight=p.current_weight_kg if p else "",
        target_weight=g.target_weight_kg if g else "",
        goal_speed=g.goal_speed if g else "normal",
        primary_goal=g.primary_goal if g else "healthy_lifestyle",
        conditions=current_user.condition_names
    )


# ============================================================
# ONBOARDING — STEP 5: Lifestyle Preferences
# ============================================================

@profile_bp.route("/onboarding/step5", methods=["GET", "POST"])
@login_required
def onboarding_step5():
    """Screen 5: Diet type + Activity level."""

    if request.method == "POST":
        diet_pref      = request.form.get("diet_preference", "vegetarian")
        activity_level = request.form.get("activity_level", "sedentary")

        errors = []
        valid_diets      = ["vegetarian", "non_vegetarian", "vegan", "eggetarian"]
        valid_activities = ["sedentary", "light", "moderate", "active", "very_active"]

        if diet_pref not in valid_diets:
            errors.append("Please select a valid diet type.")
        if activity_level not in valid_activities:
            errors.append("Please select a valid activity level.")

        if errors:
            for e in errors:
                flash(e, "danger")
            return render_template(
                "auth/onboarding/step5.html",
                diet_pref=diet_pref,
                activity_level=activity_level
            )

        profile = current_user.health_profile
        profile.diet_preference  = diet_pref
        profile.activity_level   = activity_level
        profile.onboarding_step  = 5

        # Mark onboarding complete
        current_user.onboarding_done = True
        db.session.commit()

        flash(f"Welcome to HealthTrack, {current_user.name}! Your personalised health plan is ready. 🎉", "success")
        return redirect(url_for("main.dashboard"))

    p = current_user.health_profile
    return render_template(
        "auth/onboarding/step5.html",
        diet_pref=p.diet_preference if p else "vegetarian",
        activity_level=p.activity_level if p else "sedentary",
        calorie_preview=current_user.daily_calorie_target,
        protein_preview=current_user.daily_protein_target
    )


# ============================================================
# PROFILE — VIEW
# ============================================================

@profile_bp.route("/")
@login_required
def index():
    """View full health profile, stats, and settings."""

    user  = current_user
    today = date.today()

    # Latest readings
    from models import HealthMetric
    latest_bp = HealthMetric.query.filter_by(
        user_id=user.id, metric_type="bp"
    ).order_by(HealthMetric.recorded_at.desc()).first()

    latest_weight = HealthMetric.query.filter_by(
        user_id=user.id, metric_type="weight"
    ).order_by(HealthMetric.recorded_at.desc()).first()

    # Counts
    from models import Favorite, MealPlan
    favorites_count = Favorite.query.filter_by(user_id=user.id).count()
    plans_count     = MealPlan.query.filter_by(user_id=user.id).count()

    all_conditions = HealthCondition.query.order_by(
        HealthCondition.category, HealthCondition.name
    ).all()

    return render_template(
        "profile/index.html",
        user=user,
        latest_bp=latest_bp,
        latest_weight=latest_weight,
        favorites_count=favorites_count,
        plans_count=plans_count,
        all_conditions=all_conditions,
        today=today
    )


# ============================================================
# PROFILE — EDIT
# ============================================================

@profile_bp.route("/edit", methods=["GET", "POST"])
@login_required
def edit():
    """Edit health profile — personal details, measurements, lifestyle."""

    if request.method == "POST":
        section = request.form.get("section", "")

        if section == "personal":
            name    = request.form.get("name", "").strip()
            gender  = request.form.get("gender", "")
            dob_str = request.form.get("date_of_birth", "")

            if name and len(name) >= 2:
                current_user.name = name
            if gender:
                current_user.health_profile.gender = gender
            if dob_str:
                try:
                    current_user.health_profile.date_of_birth = datetime.strptime(dob_str, "%Y-%m-%d").date()
                except ValueError:
                    flash("Invalid date format.", "danger")
                    return redirect(url_for("profile.edit"))

        elif section == "measurements":
            height_str = request.form.get("height_cm", "")
            weight_str = request.form.get("weight_kg", "")
            try:
                if height_str:
                    current_user.health_profile.height_cm = float(height_str)
                if weight_str:
                    new_weight = float(weight_str)
                    current_user.health_profile.current_weight_kg = new_weight
                    # Log weight entry
                    from models import HealthMetric
                    wm = HealthMetric(
                        user_id=current_user.id,
                        metric_type="weight",
                        value_1=new_weight,
                        unit="kg"
                    )
                    db.session.add(wm)
            except (ValueError, TypeError):
                flash("Invalid measurement values.", "danger")
                return redirect(url_for("profile.edit"))

        elif section == "lifestyle":
            diet_pref      = request.form.get("diet_preference", "")
            activity_level = request.form.get("activity_level", "")
            if diet_pref:
                current_user.health_profile.diet_preference = diet_pref
            if activity_level:
                current_user.health_profile.activity_level = activity_level

        elif section == "goals":
            target_weight = request.form.get("target_weight", "")
            goal_speed    = request.form.get("goal_speed", "")
            target_water  = request.form.get("target_water", "")
            target_steps  = request.form.get("target_steps", "")

            goals = current_user.goals
            if not goals:
                goals = UserGoal(user_id=current_user.id)
                db.session.add(goals)

            try:
                if target_weight: goals.target_weight_kg   = float(target_weight)
                if goal_speed:    goals.goal_speed         = goal_speed
                if target_water:  goals.target_water_litres= float(target_water)
                if target_steps:  goals.target_steps       = int(target_steps)
            except (ValueError, TypeError):
                flash("Invalid goal values.", "danger")
                return redirect(url_for("profile.edit"))

        elif section == "conditions":
            selected_ids = request.form.getlist("conditions")
            UserCondition.query.filter_by(user_id=current_user.id).delete()
            for cid in selected_ids:
                try:
                    cond = HealthCondition.query.get(int(cid))
                    if cond:
                        db.session.add(UserCondition(
                            user_id=current_user.id,
                            condition_id=cond.id
                        ))
                except (ValueError, TypeError):
                    continue

        db.session.commit()
        flash("Profile updated successfully.", "success")
        return redirect(url_for("profile.index"))

    all_conditions = HealthCondition.query.order_by(
        HealthCondition.category, HealthCondition.name
    ).all()
    existing_ids = [uc.condition_id for uc in current_user.conditions]

    return render_template(
        "profile/edit.html",
        user=current_user,
        all_conditions=all_conditions,
        existing_ids=existing_ids
    )


# ============================================================
# PROFILE — ADD MEDICINE
# ============================================================

@profile_bp.route("/medicine/add", methods=["POST"])
@login_required
def add_medicine():
    """Add a new medicine reminder."""
    from models import Medicine

    name       = request.form.get("name", "").strip()
    dosage     = request.form.get("dosage", "").strip()
    timing     = request.form.get("timing", "08:00")
    frequency  = request.form.get("frequency", "daily")
    with_food  = request.form.get("with_food", "doesn't_matter")
    condition  = request.form.get("condition", "")

    if not name:
        flash("Medicine name is required.", "danger")
        return redirect(url_for("profile.index"))

    med = Medicine(
        user_id=current_user.id,
        name=name,
        dosage=dosage,
        timing=timing,
        frequency=frequency,
        with_food=with_food,
        condition=condition
    )
    db.session.add(med)
    db.session.commit()
    flash(f"Medicine '{name}' added successfully.", "success")
    return redirect(url_for("profile.index"))


# ============================================================
# PROFILE — DELETE MEDICINE
# ============================================================

@profile_bp.route("/medicine/delete/<int:med_id>")
@login_required
def delete_medicine(med_id):
    from models import Medicine
    med = Medicine.query.filter_by(id=med_id, user_id=current_user.id).first_or_404()
    db.session.delete(med)
    db.session.commit()
    flash("Medicine removed.", "info")
    return redirect(url_for("profile.index"))


# ============================================================
# PROFILE — LOG MEDICINE TAKEN
# ============================================================

@profile_bp.route("/medicine/log/<int:med_id>", methods=["POST"])
@login_required
def log_medicine(med_id):
    from models import Medicine, MedicineLog

    med = Medicine.query.filter_by(id=med_id, user_id=current_user.id).first_or_404()
    today = date.today()

    existing = MedicineLog.query.filter_by(
        medicine_id=med.id, log_date=today
    ).first()

    if existing:
        existing.taken    = not existing.taken
        existing.logged_at = datetime.utcnow()
    else:
        log = MedicineLog(
            medicine_id=med.id,
            user_id=current_user.id,
            taken=True,
            log_date=today
        )
        db.session.add(log)

    db.session.commit()
    return jsonify({"success": True, "taken": existing.taken if existing else True})


# ============================================================
# PROFILE — COMPUTED STATS (AJAX)
# ============================================================

@profile_bp.route("/stats")
@login_required
def stats():
    """Return computed stats as JSON for live preview during onboarding."""
    return jsonify({
        "bmi":             current_user.bmi,
        "bmi_status":      current_user.bmi_status,
        "calorie_target":  current_user.daily_calorie_target,
        "protein_target":  current_user.daily_protein_target,
        "conditions":      current_user.condition_names,
    })