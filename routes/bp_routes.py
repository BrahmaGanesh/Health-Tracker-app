# ============================================================
# ADAPTIVE HEALTH MANAGEMENT PLATFORM
# routes/bp_routes.py — Blood Pressure Tracker
# ============================================================

from flask import (
    Blueprint, render_template, redirect,
    url_for, flash, request, jsonify
)
from flask_login import login_required, current_user
from datetime import datetime, date, timedelta
from sqlalchemy import func

from extensions import db
from models import HealthMetric, Alert

bp_bp = Blueprint("bp", __name__)


# ── BP STATUS HELPER ─────────────────────────────────────────
def get_bp_status(systolic, diastolic):
    s, d = float(systolic or 0), float(diastolic or 0)
    if s < 120 and d < 80:    return "Normal",       "normal"
    elif s < 130 and d < 80:  return "Elevated",     "elevated"
    elif s < 140 or d < 90:   return "High Stage 1", "high"
    elif s < 180 or d < 120:  return "High Stage 2", "high"
    else:                      return "Crisis",       "critical"


def check_and_create_alerts(user_id, systolic, diastolic):
    """Auto-create alert if BP is dangerously high."""
    s, d = float(systolic), float(diastolic)
    if s >= 180 or d >= 120:
        existing = Alert.query.filter_by(
            user_id=user_id,
            alert_type="emergency",
            category="bp",
            is_dismissed=False
        ).first()
        if not existing:
            alert = Alert(
                user_id=user_id,
                alert_type="emergency",
                category="bp",
                title="🚨 BP Crisis Level Detected",
                message=f"Your BP reading of {int(s)}/{int(d)} mmHg is at crisis level (above 180/120). "
                        f"Rest immediately, take your medicine, and see a doctor today.",
                action_text="Go to BP Tracker",
                action_url="/bp",
                trigger_value=s
            )
            db.session.add(alert)
            db.session.commit()
    elif s >= 160 or d >= 100:
        existing = Alert.query.filter_by(
            user_id=user_id,
            alert_type="warning",
            category="bp",
            is_dismissed=False
        ).first()
        if not existing:
            alert = Alert(
                user_id=user_id,
                alert_type="warning",
                category="bp",
                title="⚠️ High BP Detected",
                message=f"Your BP reading of {int(s)}/{int(d)} mmHg is significantly elevated. "
                        f"Review your salt intake, ensure medicine is taken, and track regularly.",
                trigger_value=s
            )
            db.session.add(alert)
            db.session.commit()


# ============================================================
# BP TRACKER — MAIN PAGE
# ============================================================

@bp_bp.route("/")
@login_required
def tracker():
    today = date.today()
    user  = current_user

    # ── Latest reading ────────────────────────────────────────
    latest = HealthMetric.query.filter_by(
        user_id=user.id, metric_type="bp"
    ).order_by(HealthMetric.recorded_at.desc()).first()

    latest_status = "No Reading"
    if latest:
        latest_status, _ = get_bp_status(latest.value_1, latest.value_2)

    # ── Morning BP (first reading today) ─────────────────────
    morning_bp = HealthMetric.query.filter(
        HealthMetric.user_id == user.id,
        HealthMetric.metric_type == "bp",
        func.date(HealthMetric.recorded_at) == today
    ).order_by(HealthMetric.recorded_at.asc()).first()

    morning_bp_str = (
        f"{int(morning_bp.value_1)}/{int(morning_bp.value_2)}"
        if morning_bp else "—"
    )

    # ── Evening BP (last reading today after 3pm) ─────────────
    evening_bp = HealthMetric.query.filter(
        HealthMetric.user_id == user.id,
        HealthMetric.metric_type == "bp",
        func.date(HealthMetric.recorded_at) == today,
        func.strftime('%H', HealthMetric.recorded_at) >= '15'
    ).order_by(HealthMetric.recorded_at.desc()).first()

    evening_bp_str = (
        f"{int(evening_bp.value_1)}/{int(evening_bp.value_2)}"
        if evening_bp else "—"
    )

    # ── Weekly chart data ─────────────────────────────────────
    seven_days = []
    for i in range(6, -1, -1):
        day_d    = today - timedelta(days=i)
        day_rdgs = HealthMetric.query.filter(
            HealthMetric.user_id == user.id,
            HealthMetric.metric_type == "bp",
            func.date(HealthMetric.recorded_at) == day_d
        ).all()

        if day_rdgs:
            avg_sys   = round(sum(r.value_1 for r in day_rdgs if r.value_1) / len(day_rdgs), 0)
            avg_dia   = round(sum(r.value_2 for r in day_rdgs if r.value_2) / len(day_rdgs), 0)
            avg_pulse = round(sum(r.value_3 for r in day_rdgs if r.value_3) / len(day_rdgs), 0) if any(r.value_3 for r in day_rdgs) else None
        else:
            avg_sys = avg_dia = avg_pulse = None

        seven_days.append({
            "day":   day_d.strftime("%a"),
            "sys":   avg_sys,
            "dia":   avg_dia,
            "pulse": avg_pulse
        })

    # ── All readings (history) ────────────────────────────────
    readings = HealthMetric.query.filter_by(
        user_id=user.id, metric_type="bp"
    ).order_by(HealthMetric.recorded_at.desc()).limit(50).all()

    # ── Streak ────────────────────────────────────────────────
    streak = 0
    check  = today
    for _ in range(365):
        exists = HealthMetric.query.filter(
            HealthMetric.user_id == user.id,
            HealthMetric.metric_type == "bp",
            func.date(HealthMetric.recorded_at) == check
        ).first()
        if exists:
            streak += 1
            check  -= timedelta(days=1)
        else:
            break

    # ── 30-day stats ──────────────────────────────────────────
    thirty_ago = datetime.utcnow() - timedelta(days=30)
    recent_30  = HealthMetric.query.filter(
        HealthMetric.user_id == user.id,
        HealthMetric.metric_type == "bp",
        HealthMetric.recorded_at >= thirty_ago
    ).all()

    avg_sys_30 = avg_dia_30 = None
    days_normal = days_high = 0

    if recent_30:
        avg_sys_30 = round(sum(r.value_1 for r in recent_30 if r.value_1) / len(recent_30), 0)
        avg_dia_30 = round(sum(r.value_2 for r in recent_30 if r.value_2) / len(recent_30), 0)
        for r in recent_30:
            _, cat = get_bp_status(r.value_1, r.value_2)
            if cat == "normal":   days_normal += 1
            elif cat in ("high", "critical"): days_high += 1

    # ── Goals ─────────────────────────────────────────────────
    goals = user.goals

    return render_template(
        "bp/tracker.html",
        latest=latest,
        latest_status=latest_status,
        morning_bp=morning_bp_str,
        evening_bp=evening_bp_str,
        weekly_bp=seven_days,
        readings=readings,
        streak=streak,
        avg_sys_30=avg_sys_30,
        avg_dia_30=avg_dia_30,
        days_normal=days_normal,
        days_high=days_high,
        goals=goals,
        today=today,
    )


# ============================================================
# ADD BP READING
# ============================================================

@bp_bp.route("/add", methods=["POST"])
@login_required
def add_bp():
    systolic  = request.form.get("systolic", "")
    diastolic = request.form.get("diastolic", "")
    pulse     = request.form.get("pulse", "")
    notes     = request.form.get("notes", "")

    # Validate
    errors = []
    sys_val = dia_val = pulse_val = None

    try:
        sys_val = float(systolic)
        if not (60 <= sys_val <= 250):
            errors.append("Systolic must be between 60 and 250.")
    except (ValueError, TypeError):
        errors.append("Please enter a valid systolic value.")

    try:
        dia_val = float(diastolic)
        if not (40 <= dia_val <= 150):
            errors.append("Diastolic must be between 40 and 150.")
    except (ValueError, TypeError):
        errors.append("Please enter a valid diastolic value.")

    if pulse:
        try:
            pulse_val = float(pulse)
            if not (30 <= pulse_val <= 220):
                errors.append("Pulse must be between 30 and 220.")
        except (ValueError, TypeError):
            errors.append("Please enter a valid pulse value.")

    if errors:
        for e in errors:
            flash(e, "danger")
        return redirect(url_for("bp.tracker"))

    # Save
    metric = HealthMetric(
        user_id     = current_user.id,
        metric_type = "bp",
        value_1     = sys_val,
        value_2     = dia_val,
        value_3     = pulse_val,
        unit        = "mmHg",
        notes       = notes or None,
        source      = "manual"
    )
    db.session.add(metric)
    db.session.commit()

    # Check for alerts
    check_and_create_alerts(current_user.id, sys_val, dia_val)

    status, _ = get_bp_status(sys_val, dia_val)
    flash(f"BP reading {int(sys_val)}/{int(dia_val)} saved. Status: {status}.", "success")
    return redirect(url_for("bp.tracker"))


# ============================================================
# DELETE BP READING
# ============================================================

@bp_bp.route("/delete/<int:bp_id>")
@login_required
def delete_bp(bp_id):
    metric = HealthMetric.query.filter_by(
        id=bp_id,
        user_id=current_user.id,
        metric_type="bp"
    ).first_or_404()

    db.session.delete(metric)
    db.session.commit()
    flash("BP reading deleted.", "info")
    return redirect(url_for("bp.tracker"))


# ============================================================
# BP CHART DATA (AJAX — for dynamic date range)
# ============================================================

@bp_bp.route("/chart-data")
@login_required
def chart_data():
    """Return BP chart data as JSON for a given number of days."""
    days  = min(int(request.args.get("days", 7)), 90)
    today = date.today()
    data  = []

    for i in range(days - 1, -1, -1):
        d      = today - timedelta(days=i)
        rdgs   = HealthMetric.query.filter(
            HealthMetric.user_id == current_user.id,
            HealthMetric.metric_type == "bp",
            func.date(HealthMetric.recorded_at) == d
        ).all()

        if rdgs:
            data.append({
                "day":   d.strftime("%d %b"),
                "sys":   round(sum(r.value_1 for r in rdgs if r.value_1) / len(rdgs), 0),
                "dia":   round(sum(r.value_2 for r in rdgs if r.value_2) / len(rdgs), 0),
                "pulse": round(sum(r.value_3 for r in rdgs if r.value_3) / max(1, sum(1 for r in rdgs if r.value_3)), 0) if any(r.value_3 for r in rdgs) else None,
            })
        else:
            data.append({"day": d.strftime("%d %b"), "sys": None, "dia": None, "pulse": None})

    return jsonify(data)


# ============================================================
# EXPORT BP HISTORY (CSV)
# ============================================================

@bp_bp.route("/export")
@login_required
def export_bp():
    """Export BP history as CSV."""
    import csv
    import io
    from flask import make_response

    readings = HealthMetric.query.filter_by(
        user_id=current_user.id, metric_type="bp"
    ).order_by(HealthMetric.recorded_at.desc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Date", "Time", "Systolic", "Diastolic", "Pulse", "Status", "Notes"])

    for r in readings:
        status, _ = get_bp_status(r.value_1, r.value_2)
        writer.writerow([
            r.recorded_at.strftime("%d %b %Y"),
            r.recorded_at.strftime("%I:%M %p"),
            int(r.value_1) if r.value_1 else "",
            int(r.value_2) if r.value_2 else "",
            int(r.value_3) if r.value_3 else "",
            status,
            r.notes or ""
        ])

    response = make_response(output.getvalue())
    response.headers["Content-Disposition"] = "attachment; filename=bp_history.csv"
    response.headers["Content-type"]        = "text/csv"
    return response