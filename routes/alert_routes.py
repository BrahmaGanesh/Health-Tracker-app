# ============================================================
# ADAPTIVE HEALTH MANAGEMENT PLATFORM
# routes/alert_routes.py — Alert Engine & Management
# ============================================================

from flask import Blueprint, render_template, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from datetime import datetime, date, timedelta

# from app import db
from extensions import db
from models import Alert, HealthMetric, NutritionDailyLog

alert_bp = Blueprint("alert", __name__)


# ============================================================
# ALERT LIST PAGE
# ============================================================

@alert_bp.route("/")
@login_required
def index():
    user = current_user

    # All unread
    unread = Alert.query.filter_by(
        user_id=user.id, is_read=False, is_dismissed=False
    ).order_by(Alert.created_at.desc()).all()

    # Recent read (last 30 days)
    read = Alert.query.filter_by(
        user_id=user.id, is_read=True
    ).filter(
        Alert.created_at >= datetime.utcnow() - timedelta(days=30)
    ).order_by(Alert.created_at.desc()).limit(20).all()

    # Auto-generate alerts for this user
    _run_alert_engine(user)

    # Refresh unread
    unread = Alert.query.filter_by(
        user_id=user.id, is_read=False, is_dismissed=False
    ).order_by(Alert.created_at.desc()).all()

    return render_template(
        "alerts/index.html",
        unread  = unread,
        read    = read,
        today   = date.today(),
    )


# ============================================================
# MARK ALERT AS READ
# ============================================================

@alert_bp.route("/read/<int:alert_id>")
@login_required
def mark_read(alert_id):
    alert = Alert.query.filter_by(
        id=alert_id, user_id=current_user.id
    ).first_or_404()
    alert.is_read = True
    db.session.commit()
    return redirect(url_for("alert.index"))


# ============================================================
# MARK ALL READ
# ============================================================

@alert_bp.route("/read-all")
@login_required
def mark_all_read():
    Alert.query.filter_by(
        user_id=current_user.id, is_read=False
    ).update({"is_read": True})
    db.session.commit()
    flash("All alerts marked as read.", "success")
    return redirect(url_for("alert.index"))


# ============================================================
# DISMISS ALERT
# ============================================================

@alert_bp.route("/dismiss/<int:alert_id>")
@login_required
def dismiss(alert_id):
    alert = Alert.query.filter_by(
        id=alert_id, user_id=current_user.id
    ).first_or_404()
    if alert.alert_type != "emergency":
        alert.is_dismissed = True
        alert.is_read      = True
        db.session.commit()
    return redirect(url_for("alert.index"))


# ============================================================
# DISMISS ALL NON-EMERGENCY
# ============================================================

@alert_bp.route("/dismiss-all")
@login_required
def dismiss_all():
    Alert.query.filter_by(
        user_id=current_user.id, is_dismissed=False
    ).filter(
        Alert.alert_type != "emergency"
    ).update({"is_dismissed": True, "is_read": True})
    db.session.commit()
    flash("All alerts dismissed.", "info")
    return redirect(url_for("alert.index"))


# ============================================================
# ALERT COUNT API (AJAX — navbar badge)
# ============================================================

@alert_bp.route("/count")
@login_required
def count():
    n = Alert.query.filter_by(
        user_id=current_user.id, is_read=False, is_dismissed=False
    ).count()
    return jsonify({"count": n})


# ============================================================
# ALERT ENGINE — Core Logic
# ============================================================

def _run_alert_engine(user):
    """
    Rule-based alert engine.
    Checks current health data and creates alerts if thresholds are crossed.
    Avoids duplicate alerts by checking existing active ones.
    """
    today = date.today()

    # ── BP Alerts ─────────────────────────────────────────────
    if user.has_bp:
        latest_bp = HealthMetric.query.filter_by(
            user_id=user.id, metric_type="bp"
        ).order_by(HealthMetric.recorded_at.desc()).first()

        if latest_bp:
            s, d = latest_bp.value_1 or 0, latest_bp.value_2 or 0

            # Crisis
            if s >= 180 or d >= 120:
                _create_alert_if_new(user.id, "emergency", "bp",
                    "🚨 BP Crisis Level Detected",
                    f"Your BP reading of {int(s)}/{int(d)} mmHg is at crisis level (above 180/120). "
                    f"Rest immediately, take your medicine, and see a doctor today.",
                    trigger_value=s)

            # High Stage 2
            elif s >= 160 or d >= 100:
                _create_alert_if_new(user.id, "warning", "bp",
                    "⚠️ High BP Detected",
                    f"Your latest BP of {int(s)}/{int(d)} mmHg is significantly elevated. "
                    f"Review your salt intake and medicine consistency.",
                    trigger_value=s)

        # BP not tracked today
        from sqlalchemy import func
        tracked_today = HealthMetric.query.filter(
            HealthMetric.user_id    == user.id,
            HealthMetric.metric_type == "bp",
            func.date(HealthMetric.recorded_at) == today
        ).first()

        if not tracked_today:
            _create_alert_if_new(user.id, "reminder", "bp",
                "📋 BP Not Logged Today",
                "You haven't logged your BP today. Track morning and evening for best insights.",
                expire_hours=24)

    # ── Medicine Alerts ───────────────────────────────────────
    if user.medicines:
        for med in user.medicines:
            if not med.active:
                continue
            from models import MedicineLog
            taken_today = MedicineLog.query.filter_by(
                medicine_id=med.id, log_date=today, taken=True
            ).first()
            if not taken_today:
                _create_alert_if_new(user.id, "reminder", "medicine",
                    f"💊 Medicine Reminder — {med.name}",
                    f"Your {med.name} ({med.dosage or 'dose'}) has not been logged as taken today.",
                    expire_hours=12)

    # ── Hydration Alert ───────────────────────────────────────
    from sqlalchemy import func as sqlfunc
    today_water = HealthMetric.query.filter(
        HealthMetric.user_id    == user.id,
        HealthMetric.metric_type == "water",
        sqlfunc.date(HealthMetric.recorded_at) == today
    ).with_entities(sqlfunc.sum(HealthMetric.value_1)).scalar() or 0

    target_water = user.goals.target_water_litres if user.goals else 2.5
    import time
    hour_now = datetime.now().hour

    if hour_now >= 17 and today_water < target_water * 0.5:
        _create_alert_if_new(user.id, "recommendation", "hydration",
            "💧 Low Hydration Today",
            f"You've consumed only {round(today_water,1)}L of your {target_water}L target. "
            f"Drink at least {round(target_water - today_water, 1)}L more today.",
            expire_hours=12)

    # ── Nutrition Alert ───────────────────────────────────────
    today_nutrition = NutritionDailyLog.query.filter_by(
        user_id=user.id, log_date=today
    ).first()

    if today_nutrition:
        if today_nutrition.total_sodium > 2500:
            _create_alert_if_new(user.id, "recommendation", "nutrition",
                "🧂 High Sodium Intake Today",
                f"Your sodium intake today is {int(today_nutrition.total_sodium)}mg, "
                f"above the 2000mg safe limit. Avoid added salt and packaged food tomorrow.",
                expire_hours=24)

        if today_nutrition.total_protein < user.daily_protein_target * 0.4:
            _create_alert_if_new(user.id, "recommendation", "nutrition",
                "💪 Low Protein Today",
                f"Protein intake is only {int(today_nutrition.total_protein)}g so far "
                f"(target: {user.daily_protein_target}g). Add dal, eggs, fish, or paneer.",
                expire_hours=12)

    # ── Weight Stagnation Alert ───────────────────────────────
    if user.has_weight_loss and user.goals and user.goals.target_weight_kg:
        wt_last_14 = HealthMetric.query.filter(
            HealthMetric.user_id    == user.id,
            HealthMetric.metric_type == "weight",
            HealthMetric.recorded_at >= datetime.utcnow() - timedelta(days=14)
        ).all()

        if len(wt_last_14) >= 2:
            first_w = wt_last_14[0].value_1
            last_w  = wt_last_14[-1].value_1
            if abs(first_w - last_w) < 0.3:
                _create_alert_if_new(user.id, "recommendation", "weight",
                    "⚖️ Weight Plateau Detected",
                    "Your weight has not changed significantly in 14 days. "
                    "Try increasing walking, reducing refined carbs, and eating more fiber.",
                    expire_hours=72)


def _create_alert_if_new(user_id, alert_type, category, title, message,
                          trigger_value=None, expire_hours=None):
    """
    Create alert only if no active alert of same type+category exists.
    Prevents duplicate alerts.
    """
    existing = Alert.query.filter_by(
        user_id=user_id,
        alert_type=alert_type,
        category=category,
        is_dismissed=False
    ).filter(
        Alert.created_at >= datetime.utcnow() - timedelta(hours=expire_hours or 24)
    ).first()

    if existing:
        return  # Already exists, skip

    from datetime import timedelta as td
    expires = datetime.utcnow() + td(hours=expire_hours) if expire_hours else None

    alert = Alert(
        user_id       = user_id,
        alert_type    = alert_type,
        category      = category,
        title         = title,
        message       = message,
        trigger_value = trigger_value,
        expires_at    = expires
    )
    db.session.add(alert)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()