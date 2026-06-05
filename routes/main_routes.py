# ============================================================
# ADAPTIVE HEALTH MANAGEMENT PLATFORM
# routes/main_routes.py — Main Dashboard & Home
# ============================================================

from flask import Blueprint, render_template, redirect, url_for
from flask_login import login_required, current_user
from datetime import datetime, date, timedelta
from sqlalchemy import func

# from app import db
from extensions import db
from models import (
    HealthMetric, MealPlan, MealItem, Recipe,
    NutritionDailyLog, Alert, WeeklyInsight,
    Medicine, MedicineLog
)

main_bp = Blueprint("main", __name__)


# ============================================================
# HOME — redirect based on auth state
# ============================================================

@main_bp.route("/")
def home():
    if current_user.is_authenticated:
        if not current_user.onboarding_done:
            step = current_user.health_profile.onboarding_step if current_user.health_profile else 1
            return redirect(url_for(f"profile.onboarding_step{step}"))
        return redirect(url_for("main.dashboard"))
    return redirect(url_for("auth.login"))


# ============================================================
# MAIN DASHBOARD
# ============================================================

@main_bp.route("/dashboard")
@login_required
def dashboard():
    """
    Condition-specific dashboard.
    Collects all widgets needed based on user's health conditions.
    """
    today     = date.today()
    user      = current_user
    conditions = user.condition_names

    # ── Latest BP reading ─────────────────────────────────────
    latest_bp = HealthMetric.query.filter_by(
        user_id=user.id, metric_type="bp"
    ).order_by(HealthMetric.recorded_at.desc()).first()

    # ── BP trend (last 7 days) ────────────────────────────────
    bp_7day = HealthMetric.query.filter(
        HealthMetric.user_id == user.id,
        HealthMetric.metric_type == "bp",
        HealthMetric.recorded_at >= datetime.utcnow() - timedelta(days=7)
    ).order_by(HealthMetric.recorded_at.asc()).all()

    bp_chart_data = [
        {
            "day":   m.recorded_at.strftime("%a"),
            "sys":   m.value_1,
            "dia":   m.value_2,
            "pulse": m.value_3
        }
        for m in bp_7day
    ] if bp_7day else []

    # ── BP status text ────────────────────────────────────────
    latest_bp_status = "No Reading"
    if latest_bp:
        s, d = latest_bp.value_1 or 0, latest_bp.value_2 or 0
        if s < 120 and d < 80:    latest_bp_status = "Normal"
        elif s < 130 and d < 80:  latest_bp_status = "Elevated"
        elif s < 140 or d < 90:   latest_bp_status = "High Stage 1"
        elif s < 180 or d < 120:  latest_bp_status = "High Stage 2"
        else:                     latest_bp_status = "Crisis"

    # ── BP tracking streak ────────────────────────────────────
    bp_streak = _compute_streak(user.id, "bp")

    # ── Latest weight ─────────────────────────────────────────
    latest_weight = HealthMetric.query.filter_by(
        user_id=user.id, metric_type="weight"
    ).order_by(HealthMetric.recorded_at.desc()).first()

    # Weight trend (last 30 days)
    weight_30day = HealthMetric.query.filter(
        HealthMetric.user_id == user.id,
        HealthMetric.metric_type == "weight",
        HealthMetric.recorded_at >= datetime.utcnow() - timedelta(days=30)
    ).order_by(HealthMetric.recorded_at.asc()).all()

    weight_chart = [
        {"day": m.recorded_at.strftime("%d %b"), "weight": m.value_1}
        for m in weight_30day
    ]

    # ── Today's water intake ──────────────────────────────────
    today_water = HealthMetric.query.filter(
        HealthMetric.user_id == user.id,
        HealthMetric.metric_type == "water",
        func.date(HealthMetric.recorded_at) == today
    ).with_entities(func.sum(HealthMetric.value_1)).scalar() or 0

    water_target = user.goals.target_water_litres if user.goals else 2.5
    water_pct    = min(100, int((today_water / water_target) * 100)) if water_target else 0

    # ── Today's nutrition log ─────────────────────────────────
    today_nutrition = NutritionDailyLog.query.filter_by(
        user_id=user.id, log_date=today
    ).first()

    # ── Today's meal plan ─────────────────────────────────────
    active_plan = MealPlan.query.filter_by(
        user_id=user.id, is_active=True
    ).order_by(MealPlan.generated_at.desc()).first()

    today_meals = []
    day_name    = today.strftime("%A")

    if active_plan:
        today_meals = MealItem.query.filter_by(
            plan_id=active_plan.id, day=day_name
        ).order_by(MealItem.slot_order.asc()).all()

    meals_done    = sum(1 for m in today_meals if m.completed)
    meals_total   = len(today_meals)
    meals_pct     = int((meals_done / meals_total) * 100) if meals_total else 0

    # ── Unread alerts ─────────────────────────────────────────
    active_alerts = Alert.query.filter_by(
        user_id=user.id, is_read=False, is_dismissed=False
    ).order_by(Alert.created_at.desc()).limit(3).all()

    # ── Weekly insights ───────────────────────────────────────
    week_start = today - timedelta(days=today.weekday())
    insights   = WeeklyInsight.query.filter_by(
        user_id=user.id, week_start=week_start
    ).order_by(WeeklyInsight.priority.asc()).limit(3).all()

    # If no pre-generated insights, generate them live
    if not insights:
        insights = _generate_live_insights(user, latest_bp, today_nutrition)

    # ── Medicine compliance today ─────────────────────────────
    medicines_today = []
    if user.medicines:
        for med in user.medicines:
            if not med.active:
                continue
            log = MedicineLog.query.filter_by(
                medicine_id=med.id, log_date=today
            ).first()
            medicines_today.append({
                "medicine": med,
                "taken":    log.taken if log else False,
                "log_id":   log.id if log else None
            })

    meds_taken = sum(1 for m in medicines_today if m["taken"])
    meds_total = len(medicines_today)

    # ── Sugar reading (diabetes users) ───────────────────────
    latest_sugar = None
    if user.has_diabetes:
        latest_sugar = HealthMetric.query.filter_by(
            user_id=user.id, metric_type="sugar"
        ).order_by(HealthMetric.recorded_at.desc()).first()

    # ── 7-day avg BP ─────────────────────────────────────────
    avg_sys_7 = avg_dia_7 = None
    if bp_7day:
        avg_sys_7 = round(sum(m.value_1 for m in bp_7day if m.value_1) / len(bp_7day), 0)
        avg_dia_7 = round(sum(m.value_2 for m in bp_7day if m.value_2) / len(bp_7day), 0)

    # ── Goals progress ────────────────────────────────────────
    goals = user.goals
    weight_to_go   = None
    weight_progress = 0
    if goals and goals.target_weight_kg and latest_weight:
        start_w = goals.start_weight_kg or (latest_weight.value_1 + 5)
        curr_w  = latest_weight.value_1
        target_w = goals.target_weight_kg
        if start_w != target_w:
            weight_progress = max(0, min(100, int(
                (start_w - curr_w) / (start_w - target_w) * 100
            )))
        weight_to_go = round(curr_w - target_w, 1) if curr_w > target_w else 0

    return render_template(
        "dashboard/index.html",

        # User
        user           = user,
        conditions     = conditions,

        # BP
        latest_bp          = latest_bp,
        latest_bp_status   = latest_bp_status,
        bp_chart_data      = bp_chart_data,
        bp_streak          = bp_streak,
        avg_sys_7          = avg_sys_7,
        avg_dia_7          = avg_dia_7,

        # Weight
        latest_weight      = latest_weight,
        weight_chart       = weight_chart,
        weight_to_go       = weight_to_go,
        weight_progress    = weight_progress,

        # Water
        today_water        = round(today_water, 1),
        water_target       = water_target,
        water_pct          = water_pct,

        # Nutrition
        today_nutrition    = today_nutrition,
        calorie_target     = user.daily_calorie_target,
        protein_target     = user.daily_protein_target,

        # Meals
        today_meals        = today_meals,
        meals_done         = meals_done,
        meals_total        = meals_total,
        meals_pct          = meals_pct,
        day_name           = day_name,

        # Alerts & insights
        active_alerts      = active_alerts,
        insights           = insights,

        # Medicines
        medicines_today    = medicines_today,
        meds_taken         = meds_taken,
        meds_total         = meds_total,

        # Sugar
        latest_sugar       = latest_sugar,

        # Goals
        goals              = goals,

        # Date
        today              = today,
    )


# ============================================================
# HELPERS
# ============================================================

def _compute_streak(user_id, metric_type):
    """
    Count consecutive days a metric was tracked ending today.
    Returns integer streak count.
    """
    streak   = 0
    check_dt = date.today()

    for _ in range(365):
        exists = HealthMetric.query.filter(
            HealthMetric.user_id == user_id,
            HealthMetric.metric_type == metric_type,
            func.date(HealthMetric.recorded_at) == check_dt
        ).first()

        if exists:
            streak   += 1
            check_dt -= timedelta(days=1)
        else:
            break

    return streak


def _generate_live_insights(user, latest_bp, today_nutrition):
    """
    Generate up to 3 dynamic text insights without pre-computation.
    Rule-based intelligence — no AI API needed.
    """
    insights = []

    # ── BP insight ────────────────────────────────────────────
    if latest_bp and user.has_bp:
        s = latest_bp.value_1 or 0
        prev_bp = HealthMetric.query.filter(
            HealthMetric.user_id == user.id,
            HealthMetric.metric_type == "bp",
            HealthMetric.recorded_at < latest_bp.recorded_at
        ).order_by(HealthMetric.recorded_at.desc()).first()

        if prev_bp and prev_bp.value_1:
            change = round(prev_bp.value_1 - s, 0)
            if change >= 5:
                text = f"Your systolic BP dropped {int(change)} mmHg since last reading. The plan is working. Keep it up."
                icon = "📉"
                direction = "improving"
            elif change <= -5:
                text = f"Your systolic BP increased {int(abs(change))} mmHg since last reading. Review your salt intake and medicine consistency."
                icon = "📈"
                direction = "worsening"
            else:
                text = f"Your BP is holding steady around {int(s)}/{int(latest_bp.value_2 or 0)} mmHg. Consistency is the key to recovery."
                icon = "📊"
                direction = "stable"
        else:
            text = f"Latest BP reading: {int(s)}/{int(latest_bp.value_2 or 0)} mmHg. Keep tracking twice daily for best insights."
            icon = "❤️"
            direction = "stable"

        insights.append(type("Insight", (), {
            "insight_text": text,
            "icon":         icon,
            "direction":    direction,
            "priority":     1,
            "metric_type":  "bp"
        })())

    # ── Nutrition insight ─────────────────────────────────────
    if today_nutrition:
        cal    = today_nutrition.total_calories or 0
        target = user.daily_calorie_target
        pct    = int(cal / target * 100) if target else 0

        if pct > 95:
            text = f"You've reached {cal} kcal today — near your {target} kcal target. Keep dinner light tonight."
            icon = "🔥"
        elif pct < 50:
            text = f"Only {cal} kcal consumed so far. Make sure to eat balanced meals to support your recovery."
            icon = "🍽️"
        else:
            text = f"Good nutrition progress today — {cal} of {target} kcal. Protein: {int(today_nutrition.total_protein or 0)}g."
            icon = "🥗"

        insights.append(type("Insight", (), {
            "insight_text": text,
            "icon":         icon,
            "direction":    "stable",
            "priority":     2,
            "metric_type":  "nutrition"
        })())

    # ── Weight insight ────────────────────────────────────────
    if user.goals and user.goals.target_weight_kg:
        latest_w = HealthMetric.query.filter_by(
            user_id=user.id, metric_type="weight"
        ).order_by(HealthMetric.recorded_at.desc()).first()

        if latest_w:
            remaining = round(latest_w.value_1 - user.goals.target_weight_kg, 1)
            if remaining > 0:
                weeks = int(remaining / 0.5)
                text  = f"You are {remaining}kg from your target weight of {user.goals.target_weight_kg}kg. At 0.5kg/week — approximately {weeks} weeks to go."
                icon  = "⚖️"
            else:
                text = f"You've reached or passed your target weight of {user.goals.target_weight_kg}kg. Excellent progress!"
                icon = "🏆"

            insights.append(type("Insight", (), {
                "insight_text": text,
                "icon":         icon,
                "direction":    "improving" if remaining <= 0 else "stable",
                "priority":     3,
                "metric_type":  "weight"
            })())

    return insights[:3]