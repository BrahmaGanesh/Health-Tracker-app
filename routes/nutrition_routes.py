# ============================================================
# ADAPTIVE HEALTH MANAGEMENT PLATFORM
# routes/nutrition_routes.py — Nutrition Dashboard
# ============================================================

from flask import Blueprint, render_template
from flask_login import login_required, current_user
from datetime import date, timedelta, datetime
from sqlalchemy import func

# from app import db
from extensions import db
from models import NutritionDailyLog, HealthMetric, MealItem, MealPlan

nutrition_bp = Blueprint("nutrition", __name__)


@nutrition_bp.route("/")
@login_required
def dashboard():
    user  = current_user
    today = date.today()

    # ── Today's log ───────────────────────────────────────────
    today_log = NutritionDailyLog.query.filter_by(
        user_id=user.id, log_date=today
    ).first()

    # If no log today, compute from completed meals
    if not today_log:
        today_log = _compute_today_log(user, today)

    total_calories = int(today_log.total_calories) if today_log else 0
    total_protein  = round(today_log.total_protein,  1) if today_log else 0
    total_carbs    = round(today_log.total_carbs,    1) if today_log else 0
    total_fats     = round(today_log.total_fats,     1) if today_log else 0
    total_fiber    = round(today_log.total_fiber,    1) if today_log else 0
    total_sodium   = round(today_log.total_sodium,   0) if today_log else 0
    avg_score      = round(today_log.health_score,   0) if today_log else 0

    # ── 7-day trend ───────────────────────────────────────────
    week_logs = NutritionDailyLog.query.filter(
        NutritionDailyLog.user_id  == user.id,
        NutritionDailyLog.log_date >= today - timedelta(days=6)
    ).order_by(NutritionDailyLog.log_date.asc()).all()

    week_chart = [
        {
            "day":      log.log_date.strftime("%a"),
            "calories": int(log.total_calories),
            "protein":  round(log.total_protein, 0),
            "carbs":    round(log.total_carbs,   0),
            "fiber":    round(log.total_fiber,   0),
        }
        for log in week_logs
    ]

    # ── 7-day averages ────────────────────────────────────────
    avg_7_cal = avg_7_pro = avg_7_fiber = 0
    if week_logs:
        avg_7_cal   = round(sum(l.total_calories for l in week_logs) / len(week_logs))
        avg_7_pro   = round(sum(l.total_protein  for l in week_logs) / len(week_logs), 1)
        avg_7_fiber = round(sum(l.total_fiber    for l in week_logs) / len(week_logs), 1)

    # ── Sodium trend (last 7 days) ────────────────────────────
    sodium_data = [
        {
            "day":    log.log_date.strftime("%a"),
            "sodium": round(log.total_sodium, 0)
        }
        for log in week_logs
    ]

    # ── 30-day adherence ─────────────────────────────────────
    thirty_logs = NutritionDailyLog.query.filter(
        NutritionDailyLog.user_id  == user.id,
        NutritionDailyLog.log_date >= today - timedelta(days=29)
    ).all()

    days_on_track = sum(
        1 for l in thirty_logs
        if l.total_calories >= user.daily_calorie_target * 0.7
    )
    adherence_pct = int(days_on_track / 30 * 100)

    # ── Goals ─────────────────────────────────────────────────
    goals          = user.goals
    calorie_target = user.daily_calorie_target
    protein_target = user.daily_protein_target

    # ── Progress percentages ──────────────────────────────────
    cal_pct   = min(100, int(total_calories / max(1, calorie_target) * 100))
    pro_pct   = min(100, int(total_protein  / max(1, protein_target) * 100))
    carb_pct  = min(100, int(total_carbs    / 300                    * 100))
    fat_pct   = min(100, int(total_fats     / 70                     * 100))
    fiber_pct = min(100, int(total_fiber    / 35                     * 100))

    # ── Sodium status ─────────────────────────────────────────
    sodium_pct    = min(100, int(total_sodium / 2000 * 100))
    sodium_status = (
        "Low ✅"       if total_sodium < 1500 else
        "Moderate ⚠️" if total_sodium < 2000 else
        "High 🔴"
    )

    return render_template(
        "nutrition/dashboard.html",
        total_calories = total_calories,
        total_protein  = total_protein,
        total_carbs    = total_carbs,
        total_fats     = total_fats,
        total_fiber    = total_fiber,
        total_sodium   = int(total_sodium),
        avg_score      = int(avg_score),
        calorie_target = calorie_target,
        protein_target = protein_target,
        cal_pct        = cal_pct,
        pro_pct        = pro_pct,
        carb_pct       = carb_pct,
        fat_pct        = fat_pct,
        fiber_pct      = fiber_pct,
        sodium_pct     = sodium_pct,
        sodium_status  = sodium_status,
        week_chart     = week_chart,
        sodium_data    = sodium_data,
        avg_7_cal      = avg_7_cal,
        avg_7_pro      = avg_7_pro,
        avg_7_fiber    = avg_7_fiber,
        adherence_pct  = adherence_pct,
        days_on_track  = days_on_track,
        today          = today,
    )


def _compute_today_log(user, today):
    """
    Compute today's nutrition from completed meal items.
    Creates and saves NutritionDailyLog if data exists.
    """
    day_name    = today.strftime("%A")
    active_plan = MealPlan.query.filter_by(
        user_id=user.id, is_active=True
    ).order_by(MealPlan.generated_at.desc()).first()

    if not active_plan:
        return None

    items = MealItem.query.filter_by(
        plan_id=active_plan.id,
        day=day_name
    ).all()

    totals = {
        "calories":0,"protein":0,"carbs":0,
        "fats":0,"fiber":0,"sodium":0
    }
    completed = planned = 0

    for item in items:
        planned += 1
        if item.completed:
            completed += 1
            r = item.recipe
            totals["calories"] += r.calories or 0
            totals["protein"]  += r.protein  or 0
            totals["carbs"]    += r.carbs    or 0
            totals["fats"]     += r.fats     or 0
            totals["fiber"]    += r.fiber    or 0
            totals["sodium"]   += r.sodium   or 0

    if completed == 0 and planned == 0:
        return None

    # Health score
    cal_score   = min(100, int(totals["calories"] / max(1, user.daily_calorie_target) * 100))
    pro_score   = min(100, int(totals["protein"]  / max(1, user.daily_protein_target) * 100))
    health_score = round((cal_score + pro_score) / 2)

    log = NutritionDailyLog(
        user_id         = user.id,
        log_date        = today,
        total_calories  = totals["calories"],
        total_protein   = totals["protein"],
        total_carbs     = totals["carbs"],
        total_fats      = totals["fats"],
        total_fiber     = totals["fiber"],
        total_sodium    = totals["sodium"],
        meals_completed = completed,
        meals_planned   = planned,
        health_score    = health_score
    )

    try:
        db.session.merge(log)
        db.session.commit()
    except Exception:
        db.session.rollback()

    return log