# ============================================================
# ADAPTIVE HEALTH MANAGEMENT PLATFORM
# routes/tracker_routes.py — Weight, Water, Sugar, Steps
# ============================================================

from flask import (
    Blueprint, render_template, redirect,
    url_for, flash, request, jsonify
)
from flask_login import login_required, current_user
from datetime import datetime, date, timedelta
from sqlalchemy import func

# from app import db
from extensions import db
from models import HealthMetric

tracker_bp = Blueprint("tracker", __name__)


# ── HELPER: get readings for chart ───────────────────────────
def get_metric_history(user_id, metric_type, days=30):
    since = datetime.utcnow() - timedelta(days=days)
    return HealthMetric.query.filter(
        HealthMetric.user_id    == user_id,
        HealthMetric.metric_type == metric_type,
        HealthMetric.recorded_at >= since
    ).order_by(HealthMetric.recorded_at.asc()).all()


def get_latest(user_id, metric_type):
    return HealthMetric.query.filter_by(
        user_id=user_id, metric_type=metric_type
    ).order_by(HealthMetric.recorded_at.desc()).first()


# ============================================================
# WEIGHT TRACKER
# ============================================================

@tracker_bp.route("/weight", methods=["GET", "POST"])
@login_required
def weight():
    user  = current_user
    today = date.today()

    if request.method == "POST":
        weight_str = request.form.get("weight_kg", "")
        notes      = request.form.get("notes", "")

        try:
            w = float(weight_str)
            if not (20 <= w <= 300):
                raise ValueError
        except (ValueError, TypeError):
            flash("Please enter a valid weight between 20–300 kg.", "danger")
            return redirect(url_for("tracker.weight"))

        # Save metric
        m = HealthMetric(
            user_id     = user.id,
            metric_type = "weight",
            value_1     = w,
            unit        = "kg",
            notes       = notes or None,
            source      = "manual"
        )
        db.session.add(m)

        # Update health profile
        if user.health_profile:
            user.health_profile.current_weight_kg = w

        db.session.commit()
        flash(f"Weight {w}kg logged successfully.", "success")
        return redirect(url_for("tracker.weight"))

    # ── Data for page ─────────────────────────────────────────
    latest  = get_latest(user.id, "weight")
    history = get_metric_history(user.id, "weight", days=90)

    chart_data = [
        {"day": r.recorded_at.strftime("%d %b"), "weight": r.value_1}
        for r in history
    ]

    # Stats
    goals          = user.goals
    target_weight  = goals.target_weight_kg if goals else None
    start_weight   = goals.start_weight_kg  if goals else None
    current_weight = latest.value_1         if latest else None

    lost_so_far = to_go = progress_pct = None
    if start_weight and current_weight and target_weight:
        lost_so_far  = round(start_weight - current_weight, 1)
        to_go        = round(current_weight - target_weight, 1)
        total_needed = start_weight - target_weight
        if total_needed > 0:
            progress_pct = max(0, min(100, int((start_weight - current_weight) / total_needed * 100)))

    # BMI
    bmi = user.bmi

    # 7-day change
    week_ago = HealthMetric.query.filter(
        HealthMetric.user_id     == user.id,
        HealthMetric.metric_type == "weight",
        HealthMetric.recorded_at <= datetime.utcnow() - timedelta(days=6)
    ).order_by(HealthMetric.recorded_at.desc()).first()

    weight_7d_change = None
    if latest and week_ago:
        weight_7d_change = round(latest.value_1 - week_ago.value_1, 1)

    return render_template(
        "tracker/weight.html",
        latest          = latest,
        chart_data      = chart_data,
        history         = history[-20:][::-1],
        current_weight  = current_weight,
        target_weight   = target_weight,
        start_weight    = start_weight,
        lost_so_far     = lost_so_far,
        to_go           = to_go,
        progress_pct    = progress_pct or 0,
        bmi             = bmi,
        bmi_status      = user.bmi_status,
        weight_7d_change= weight_7d_change,
        today           = today,
        goals           = goals,
    )


# ============================================================
# WATER TRACKER
# ============================================================

@tracker_bp.route("/water", methods=["GET", "POST"])
@login_required
def water():
    user  = current_user
    today = date.today()

    if request.method == "POST":
        amount_str = request.form.get("amount", "")
        try:
            amount = float(amount_str)
            if not (0.05 <= amount <= 5.0):
                raise ValueError
        except (ValueError, TypeError):
            flash("Please enter a valid amount between 0.05 and 5.0 litres.", "danger")
            return redirect(url_for("tracker.water"))

        m = HealthMetric(
            user_id     = user.id,
            metric_type = "water",
            value_1     = amount,
            unit        = "litres",
            source      = "manual"
        )
        db.session.add(m)
        db.session.commit()
        flash(f"✅ {amount}L water logged!", "success")
        return redirect(url_for("tracker.water"))

    # ── Today's total ─────────────────────────────────────────
    today_total = HealthMetric.query.filter(
        HealthMetric.user_id     == user.id,
        HealthMetric.metric_type == "water",
        func.date(HealthMetric.recorded_at) == today
    ).with_entities(func.sum(HealthMetric.value_1)).scalar() or 0

    today_total = round(today_total, 2)
    target      = user.goals.target_water_litres if user.goals else 2.5
    pct         = min(100, int((today_total / target) * 100)) if target else 0

    # Glasses (250ml each = 0.25L)
    glasses_done   = int(today_total / 0.25)
    glasses_target = int(target / 0.25)

    # ── 7-day history ─────────────────────────────────────────
    week_data = []
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        total = HealthMetric.query.filter(
            HealthMetric.user_id     == user.id,
            HealthMetric.metric_type == "water",
            func.date(HealthMetric.recorded_at) == d
        ).with_entities(func.sum(HealthMetric.value_1)).scalar() or 0
        week_data.append({"day": d.strftime("%a"), "litres": round(total, 2)})

    # ── Today's log entries ───────────────────────────────────
    today_logs = HealthMetric.query.filter(
        HealthMetric.user_id     == user.id,
        HealthMetric.metric_type == "water",
        func.date(HealthMetric.recorded_at) == today
    ).order_by(HealthMetric.recorded_at.desc()).all()

    return render_template(
        "tracker/water.html",
        today_total    = today_total,
        target         = target,
        pct            = pct,
        glasses_done   = glasses_done,
        glasses_target = glasses_target,
        week_data      = week_data,
        today_logs     = today_logs,
        today          = today,
    )


# ============================================================
# SUGAR TRACKER
# ============================================================

@tracker_bp.route("/sugar", methods=["GET", "POST"])
@login_required
def sugar():
    user  = current_user
    today = date.today()

    if request.method == "POST":
        fasting_str   = request.form.get("fasting", "")
        postmeal_str  = request.form.get("post_meal", "")
        notes         = request.form.get("notes", "")

        errors  = []
        fasting = post_meal = None

        if fasting_str:
            try:
                fasting = float(fasting_str)
                if not (20 <= fasting <= 600):
                    errors.append("Fasting sugar must be between 20–600 mg/dL.")
            except (ValueError, TypeError):
                errors.append("Invalid fasting sugar value.")

        if postmeal_str:
            try:
                post_meal = float(postmeal_str)
                if not (20 <= post_meal <= 800):
                    errors.append("Post-meal sugar must be between 20–800 mg/dL.")
            except (ValueError, TypeError):
                errors.append("Invalid post-meal sugar value.")

        if not fasting and not post_meal:
            errors.append("Please enter at least one sugar reading.")

        if errors:
            for e in errors:
                flash(e, "danger")
            return redirect(url_for("tracker.sugar"))

        m = HealthMetric(
            user_id     = user.id,
            metric_type = "sugar",
            value_1     = fasting,
            value_2     = post_meal,
            unit        = "mg_dL",
            notes       = notes or None,
            source      = "manual"
        )
        db.session.add(m)
        db.session.commit()

        # Auto-alert if very high
        if fasting and fasting >= 200:
            from models import Alert
            alert = Alert(
                user_id    = user.id,
                alert_type = "warning",
                category   = "sugar",
                title      = "⚠️ High Fasting Sugar",
                message    = f"Your fasting sugar of {int(fasting)} mg/dL is significantly elevated. Consult your doctor.",
                trigger_value = fasting
            )
            db.session.add(alert)
            db.session.commit()

        flash("Blood sugar reading saved.", "success")
        return redirect(url_for("tracker.sugar"))

    # ── Latest readings ───────────────────────────────────────
    latest  = get_latest(user.id, "sugar")
    history = get_metric_history(user.id, "sugar", days=30)

    chart_data = [
        {
            "day":      r.recorded_at.strftime("%d %b"),
            "fasting":  r.value_1,
            "postmeal": r.value_2
        }
        for r in history
    ]

    # Status
    latest_status = "No Reading"
    if latest and latest.value_1:
        f = latest.value_1
        if f < 100:       latest_status = "Normal"
        elif f < 126:     latest_status = "Pre-Diabetes"
        else:             latest_status = "Diabetes Range"

    return render_template(
        "tracker/sugar.html",
        latest        = latest,
        latest_status = latest_status,
        chart_data    = chart_data,
        history       = history[-20:][::-1],
        today         = today,
    )


# ============================================================
# DELETE ANY METRIC
# ============================================================

@tracker_bp.route("/delete/<int:metric_id>")
@login_required
def delete_metric(metric_id):
    metric = HealthMetric.query.filter_by(
        id=metric_id, user_id=current_user.id
    ).first_or_404()

    metric_type = metric.metric_type
    db.session.delete(metric)
    db.session.commit()
    flash("Entry deleted.", "info")

    redirect_map = {
        "weight": "tracker.weight",
        "water":  "tracker.water",
        "sugar":  "tracker.sugar",
        "bp":     "bp.tracker",
    }
    return redirect(url_for(redirect_map.get(metric_type, "main.dashboard")))


# ============================================================
# QUICK LOG (AJAX — used from dashboard)
# ============================================================

@tracker_bp.route("/quick-log", methods=["POST"])
@login_required
def quick_log():
    """Quick log any metric via AJAX from the dashboard."""
    metric_type = request.json.get("type")
    value_1     = request.json.get("value_1")
    value_2     = request.json.get("value_2")
    value_3     = request.json.get("value_3")

    allowed = ["weight", "water", "steps", "mood"]
    if metric_type not in allowed:
        return jsonify({"success": False, "error": "Invalid metric type"}), 400

    try:
        m = HealthMetric(
            user_id     = current_user.id,
            metric_type = metric_type,
            value_1     = float(value_1) if value_1 else None,
            value_2     = float(value_2) if value_2 else None,
            value_3     = float(value_3) if value_3 else None,
            source      = "manual"
        )
        db.session.add(m)
        db.session.commit()
        return jsonify({"success": True})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500