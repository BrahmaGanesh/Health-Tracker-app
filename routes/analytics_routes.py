# ============================================================
# ADAPTIVE HEALTH MANAGEMENT PLATFORM
# routes/analytics_routes.py — Analytics & Insights Engine
# ============================================================

from flask import Blueprint, render_template, jsonify, request
from flask_login import login_required, current_user
from datetime import date, timedelta, datetime
from sqlalchemy import func

# from app import db
from extensions import db
from models import HealthMetric, NutritionDailyLog, WeeklyInsight, MealItem, MealPlan

analytics_bp = Blueprint("analytics", __name__)


@analytics_bp.route("/")
@login_required
def index():
    user  = current_user
    today = date.today()

    # ── BP Analytics (30 days) ────────────────────────────────
    bp_30 = HealthMetric.query.filter(
        HealthMetric.user_id    == user.id,
        HealthMetric.metric_type == "bp",
        HealthMetric.recorded_at >= datetime.utcnow() - timedelta(days=30)
    ).order_by(HealthMetric.recorded_at.asc()).all()

    bp_chart = [
        {
            "day":   r.recorded_at.strftime("%d %b"),
            "sys":   r.value_1,
            "dia":   r.value_2,
            "pulse": r.value_3
        }
        for r in bp_30
    ]

    avg_sys = avg_dia = None
    days_normal = days_high = 0
    if bp_30:
        avg_sys = round(sum(r.value_1 for r in bp_30 if r.value_1) / len(bp_30), 0)
        avg_dia = round(sum(r.value_2 for r in bp_30 if r.value_2) / len(bp_30), 0)
        for r in bp_30:
            s = r.value_1 or 0
            d = r.value_2 or 0
            if s < 130 and d < 80: days_normal += 1
            elif s >= 140 or d >= 90: days_high += 1

    # ── BP streak ─────────────────────────────────────────────
    bp_streak = _compute_streak(user.id, "bp")

    # ── Weight trend (60 days) ────────────────────────────────
    wt_60 = HealthMetric.query.filter(
        HealthMetric.user_id    == user.id,
        HealthMetric.metric_type == "weight",
        HealthMetric.recorded_at >= datetime.utcnow() - timedelta(days=60)
    ).order_by(HealthMetric.recorded_at.asc()).all()

    weight_chart = [
        {"day": r.recorded_at.strftime("%d %b"), "weight": r.value_1}
        for r in wt_60
    ]

    latest_weight = wt_60[-1].value_1 if wt_60 else None
    start_weight  = wt_60[0].value_1  if wt_60 else None
    wt_change_60  = round(latest_weight - start_weight, 1) if (latest_weight and start_weight) else None

    # ── Nutrition 14-day ──────────────────────────────────────
    nutri_14 = NutritionDailyLog.query.filter(
        NutritionDailyLog.user_id  == user.id,
        NutritionDailyLog.log_date >= today - timedelta(days=13)
    ).order_by(NutritionDailyLog.log_date.asc()).all()

    nutrition_chart = [
        {
            "day":      l.log_date.strftime("%d %b"),
            "calories": int(l.total_calories),
            "protein":  round(l.total_protein,  0),
            "fiber":    round(l.total_fiber,    0),
        }
        for l in nutri_14
    ]

    avg_cal_14 = round(sum(l.total_calories for l in nutri_14) / max(1, len(nutri_14))) if nutri_14 else 0
    avg_pro_14 = round(sum(l.total_protein  for l in nutri_14) / max(1, len(nutri_14)), 1) if nutri_14 else 0

    # ── Water 7-day ───────────────────────────────────────────
    water_7 = []
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        total = HealthMetric.query.filter(
            HealthMetric.user_id     == user.id,
            HealthMetric.metric_type == "water",
            func.date(HealthMetric.recorded_at) == d
        ).with_entities(func.sum(HealthMetric.value_1)).scalar() or 0
        water_7.append({"day": d.strftime("%a"), "litres": round(total, 2)})

    # ── Meal adherence (last 7 days) ──────────────────────────
    active_plan = MealPlan.query.filter_by(
        user_id=user.id, is_active=True
    ).first()

    meal_adherence = 0
    if active_plan:
        total_items    = MealItem.query.filter_by(plan_id=active_plan.id).count()
        completed_items= MealItem.query.filter_by(plan_id=active_plan.id, completed=True).count()
        if total_items:
            meal_adherence = int(completed_items / total_items * 100)

    # ── Weekly insights ───────────────────────────────────────
    week_start = today - timedelta(days=today.weekday())
    insights   = WeeklyInsight.query.filter_by(
        user_id=user.id, week_start=week_start
    ).order_by(WeeklyInsight.priority.asc()).all()

    if not insights:
        insights = _generate_insights(user, bp_30, wt_60, nutri_14)

    # ── Health score trend ────────────────────────────────────
    score_trend = [
        {
            "day":   l.log_date.strftime("%d %b"),
            "score": int(l.health_score)
        }
        for l in nutri_14 if l.health_score
    ]

    return render_template(
        "analytics/index.html",
        # BP
        bp_chart       = bp_chart,
        avg_sys        = avg_sys,
        avg_dia        = avg_dia,
        days_normal    = days_normal,
        days_high      = days_high,
        bp_streak      = bp_streak,
        # Weight
        weight_chart   = weight_chart,
        latest_weight  = latest_weight,
        wt_change_60   = wt_change_60,
        # Nutrition
        nutrition_chart= nutrition_chart,
        avg_cal_14     = avg_cal_14,
        avg_pro_14     = avg_pro_14,
        # Water
        water_7        = water_7,
        # Meals
        meal_adherence = meal_adherence,
        # Insights
        insights       = insights,
        # Score
        score_trend    = score_trend,
        # Targets
        calorie_target = user.daily_calorie_target,
        protein_target = user.daily_protein_target,
        water_target   = user.goals.target_water_litres if user.goals else 2.5,
        today          = today,
    )


# ============================================================
# CHART DATA API — for dynamic range loading
# ============================================================

@analytics_bp.route("/bp-data")
@login_required
def bp_data():
    days = min(int(request.args.get("days", 30)), 90)
    since = datetime.utcnow() - timedelta(days=days)
    records = HealthMetric.query.filter(
        HealthMetric.user_id    == current_user.id,
        HealthMetric.metric_type == "bp",
        HealthMetric.recorded_at >= since
    ).order_by(HealthMetric.recorded_at.asc()).all()

    return jsonify([
        {"day": r.recorded_at.strftime("%d %b"), "sys": r.value_1, "dia": r.value_2, "pulse": r.value_3}
        for r in records
    ])


@analytics_bp.route("/weight-data")
@login_required
def weight_data():
    days  = min(int(request.args.get("days", 30)), 180)
    since = datetime.utcnow() - timedelta(days=days)
    records = HealthMetric.query.filter(
        HealthMetric.user_id    == current_user.id,
        HealthMetric.metric_type == "weight",
        HealthMetric.recorded_at >= since
    ).order_by(HealthMetric.recorded_at.asc()).all()
    return jsonify([{"day": r.recorded_at.strftime("%d %b"), "weight": r.value_1} for r in records])


# ============================================================
# HELPERS
# ============================================================

def _compute_streak(user_id, metric_type):
    streak   = 0
    check_dt = date.today()
    for _ in range(365):
        exists = HealthMetric.query.filter(
            HealthMetric.user_id    == user_id,
            HealthMetric.metric_type == metric_type,
            func.date(HealthMetric.recorded_at) == check_dt
        ).first()
        if exists:
            streak  += 1
            check_dt -= timedelta(days=1)
        else:
            break
    return streak


def _generate_insights(user, bp_records, weight_records, nutrition_logs):
    """Generate rule-based intelligence insights."""
    insights = []

    # ── BP insight ────────────────────────────────────────────
    if bp_records and user.has_bp:
        recent  = bp_records[-3:] if len(bp_records) >= 3 else bp_records
        earlier = bp_records[:3]  if len(bp_records) >= 6 else []

        avg_recent  = sum(r.value_1 for r in recent)  / len(recent)
        avg_earlier = sum(r.value_1 for r in earlier) / len(earlier) if earlier else avg_recent

        change = round(avg_earlier - avg_recent, 0)

        if change >= 5:
            text = f"Your average BP dropped {int(change)} mmHg over the tracking period. The lifestyle changes are showing results."
            icon = "📉"; direction = "improving"
        elif change <= -5:
            text = f"Your BP trend has increased {int(abs(change))} mmHg. Review salt intake, medicine adherence, and stress levels."
            icon = "📈"; direction = "worsening"
        else:
            avg_s = round(avg_recent, 0)
            avg_d = round(sum(r.value_2 for r in recent) / len(recent), 0)
            text = f"BP is stable at around {int(avg_s)}/{int(avg_d)} mmHg. Continue current routine."
            icon = "📊"; direction = "stable"

        insights.append(_make_insight(text, icon, direction, 1, "bp"))

    # ── Weight insight ────────────────────────────────────────
    if weight_records and len(weight_records) >= 2:
        start  = weight_records[0].value_1
        latest = weight_records[-1].value_1
        change = round(start - latest, 1)

        if change > 0:
            text = f"You have lost {change}kg over the tracked period. At 0.5kg/week pace, keep going consistently."
            icon = "⚖️"; direction = "improving"
        elif change < -0.5:
            text = f"Weight increased {abs(change)}kg. Review calorie intake and increase activity level."
            icon = "⚠️"; direction = "worsening"
        else:
            text = f"Weight is holding steady at {latest}kg. Consistent effort is needed for further progress."
            icon = "⚖️"; direction = "stable"

        insights.append(_make_insight(text, icon, direction, 2, "weight"))

    # ── Nutrition insight ─────────────────────────────────────
    if nutrition_logs:
        avg_cal = sum(l.total_calories for l in nutrition_logs) / len(nutrition_logs)
        avg_pro = sum(l.total_protein  for l in nutrition_logs) / len(nutrition_logs)
        target  = user.daily_calorie_target

        if avg_cal < target * 0.6:
            text = f"Average daily calories ({int(avg_cal)} kcal) are below target. Ensure balanced meals to support recovery."
            icon = "🍽️"; direction = "worsening"
        elif avg_pro < user.daily_protein_target * 0.6:
            text = f"Protein intake averaging {round(avg_pro,0)}g/day is low. Add more dal, eggs, fish, or low-fat paneer."
            icon = "💪"; direction = "worsening"
        else:
            text = f"Good nutrition consistency — averaging {int(avg_cal)} kcal and {round(avg_pro,0)}g protein daily."
            icon = "🥗"; direction = "stable"

        insights.append(_make_insight(text, icon, direction, 3, "nutrition"))

    return insights[:3]


def _make_insight(text, icon, direction, priority, metric_type):
    return type("Insight", (), {
        "insight_text": text,
        "icon":         icon,
        "direction":    direction,
        "priority":     priority,
        "metric_type":  metric_type
    })()