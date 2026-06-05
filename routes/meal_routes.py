# ============================================================
# ADAPTIVE HEALTH MANAGEMENT PLATFORM
# routes/meal_routes.py — Meal Planner, Recipes, Grocery
# ============================================================

from flask import (
    Blueprint, render_template, redirect,
    url_for, flash, request, jsonify
)
from flask_login import login_required, current_user
from datetime import date, timedelta
from sqlalchemy import or_
import random

# from app import db
from extensions import db
from models import (
    Recipe, MealPlan, MealItem, Favorite,
    GroceryItem, NutritionDailyLog
)

meal_bp = Blueprint("meal", __name__)

# ── Meal slot order & timing ──────────────────────────────────
MEAL_SLOTS = [
    ("Morning Drink", 1, 100),
    ("Breakfast",     2, 320),
    ("Lunch",         3, 500),
    ("Snacks",        4, 180),
    ("Dinner",        5, 400),
]

DAYS_OF_WEEK = [
    "Monday", "Tuesday", "Wednesday",
    "Thursday", "Friday", "Saturday", "Sunday"
]

SLOT_CATEGORY_MAP = {
    "Morning Drink": ["Morning", "BP Special"],
    "Breakfast":     ["Breakfast"],
    "Lunch":         ["Lunch"],
    "Snacks":        ["Snack"],
    "Dinner":        ["Dinner", "Soup"],
}


# ============================================================
# HELPERS
# ============================================================

def get_condition_filters(user):
    """Return SQLAlchemy filter conditions based on user's health conditions."""
    filters = []
    if user.has_bp:
        filters.append(Recipe.bp_friendly == True)
    if user.has_diabetes:
        filters.append(Recipe.diabetes_friendly == True)
    if user.has_weight_loss:
        filters.append(Recipe.weight_loss_friendly == True)
    return filters


def get_diet_filter(user):
    """Return diet type filter."""
    pref = user.health_profile.diet_preference if user.health_profile else "vegetarian"
    if pref in ("vegetarian", "vegan"):
        return Recipe.is_veg == True
    return None  # non-veg and eggetarian allow all


def pick_recipe_for_slot(user, slot_name, cal_budget, exclude_ids=None):
    """
    Pick the best recipe for a meal slot given user conditions.
    Returns a Recipe or None.
    """
    exclude_ids = exclude_ids or []
    categories  = SLOT_CATEGORY_MAP.get(slot_name, ["General"])

    query = Recipe.query.filter(
        Recipe.category.in_(categories)
    )

    # Diet filter
    diet_filter = get_diet_filter(user)
    if diet_filter is not None:
        query = query.filter(diet_filter)

    # Condition-specific preference (not hard exclude)
    if user.has_bp:
        query = query.filter(Recipe.bp_friendly == True)
    elif user.has_diabetes:
        query = query.filter(Recipe.diabetes_friendly == True)
    elif user.has_weight_loss:
        query = query.filter(Recipe.weight_loss_friendly == True)

    # Calorie budget (within 50% over is okay)
    query = query.filter(Recipe.calories <= cal_budget * 1.5)

    # Exclude recently used
    if exclude_ids:
        query = query.filter(~Recipe.id.in_(exclude_ids))

    recipes = query.all()

    if not recipes:
        # Fallback: remove condition filter but keep category
        recipes = Recipe.query.filter(
            Recipe.category.in_(categories),
            ~Recipe.id.in_(exclude_ids)
        ).all()

    if not recipes:
        return None

    # Score and pick best
    conditions = user.condition_names
    scored = sorted(
        recipes,
        key=lambda r: r.composite_score(conditions),
        reverse=True
    )

    # Pick from top 5 randomly to add variety
    top = scored[:5]
    return random.choice(top) if top else None


def compute_daily_nutrition(plan_id, day_name):
    """Sum up nutrition for all meals in a day."""
    items = MealItem.query.filter_by(plan_id=plan_id, day=day_name).all()
    totals = {
        "calories": 0, "protein": 0, "carbs": 0,
        "fats": 0, "fiber": 0, "sodium": 0
    }
    for item in items:
        r = item.recipe
        totals["calories"] += r.calories or 0
        totals["protein"]  += r.protein  or 0
        totals["carbs"]    += r.carbs    or 0
        totals["fats"]     += r.fats     or 0
        totals["fiber"]    += r.fiber    or 0
        totals["sodium"]   += r.sodium   or 0
    return totals


# ============================================================
# MEALS DASHBOARD
# ============================================================

@meal_bp.route("/")
@login_required
def meals():
    today      = date.today()
    user       = current_user
    week_start = today - timedelta(days=today.weekday())

    # Get active plan
    active_plan = MealPlan.query.filter_by(
        user_id=user.id, is_active=True
    ).order_by(MealPlan.generated_at.desc()).first()

    weekly_data   = {}
    avg_daily_cal = avg_daily_pro = avg_daily_carb = avg_daily_fat = 0
    nutrition_score = 0

    if active_plan:
        for day in DAYS_OF_WEEK:
            items = MealItem.query.filter_by(
                plan_id=active_plan.id, day=day
            ).order_by(MealItem.slot_order).all()

            if items:
                weekly_data[day] = {
                    item.meal_slot: {
                        "recipe":  item.recipe,
                        "item_id": item.id,
                        "completed": item.completed,
                        "note":    item.note,
                    }
                    for item in items
                }

        # Compute weekly averages
        if weekly_data:
            all_cals = all_prot = all_carb = all_fat = count = 0
            for day, slots in weekly_data.items():
                for slot, data in slots.items():
                    r = data["recipe"]
                    all_cals += r.calories or 0
                    all_prot += r.protein  or 0
                    all_carb += r.carbs    or 0
                    all_fat  += r.fats     or 0
                    count    += 1

            if count:
                meals_per_day    = 5
                days_count       = max(1, count // meals_per_day)
                avg_daily_cal    = round(all_cals / days_count)
                avg_daily_pro    = round(all_prot / days_count)
                avg_daily_carb   = round(all_carb / days_count)
                avg_daily_fat    = round(all_fat  / days_count)

            # Nutrition score: how well does avg match targets?
            cal_score   = min(100, int(avg_daily_cal / max(1, user.daily_calorie_target) * 100))
            pro_score   = min(100, int(avg_daily_pro / max(1, user.daily_protein_target) * 100))
            nutrition_score = round((cal_score + pro_score) / 2)

    return render_template(
        "meals/dashboard.html",
        weekly_data       = weekly_data,
        active_plan       = active_plan,
        avg_daily_calories= avg_daily_cal,
        avg_daily_protein = avg_daily_pro,
        avg_daily_carbs   = avg_daily_carb,
        avg_daily_fats    = avg_daily_fat,
        nutrition_score   = nutrition_score,
        calorie_target    = user.daily_calorie_target,
        protein_target    = user.daily_protein_target,
        today             = today,
        week_start        = week_start,
    )


# ============================================================
# GENERATE WEEKLY MEAL PLAN
# ============================================================

@meal_bp.route("/generate")
@login_required
def generate_weekly_meals():
    user       = current_user
    today      = date.today()
    week_start = today - timedelta(days=today.weekday())

    # Deactivate previous plans
    MealPlan.query.filter_by(user_id=user.id, is_active=True).update({"is_active": False})

    # Create new plan
    plan = MealPlan(
        user_id         = user.id,
        week_start_date = week_start,
        is_active       = True
    )
    db.session.add(plan)
    db.session.flush()

    used_ids_day = []  # track per-day to avoid same recipe twice in a day

    for day in DAYS_OF_WEEK:
        used_today = []
        for slot_name, slot_order, cal_budget in MEAL_SLOTS:
            recipe = pick_recipe_for_slot(
                user, slot_name, cal_budget,
                exclude_ids=used_today + used_ids_day[-10:]  # avoid recent repeats
            )
            if recipe:
                item = MealItem(
                    plan_id    = plan.id,
                    recipe_id  = recipe.id,
                    day        = day,
                    meal_slot  = slot_name,
                    slot_order = slot_order
                )
                db.session.add(item)
                used_today.append(recipe.id)
                used_ids_day.append(recipe.id)

    db.session.commit()

    # Auto-generate grocery list
    _generate_grocery_list(user.id, plan.id, week_start)

    flash("✅ Your personalised weekly meal plan has been generated!", "success")
    return redirect(url_for("meal.meals"))


def _generate_grocery_list(user_id, plan_id, week_start):
    """Auto-generate grocery list from meal plan ingredients."""
    # Clear existing grocery list for this week
    GroceryItem.query.filter_by(
        user_id=user_id, week_start=week_start
    ).delete()

    # Gather all ingredients
    items = MealItem.query.filter_by(plan_id=plan_id).all()
    seen  = set()

    for item in items:
        r = item.recipe
        if not r.ingredients:
            continue
        for ing in r.ingredients.split(","):
            ing_clean = ing.strip()
            if not ing_clean or ing_clean.lower() in seen:
                continue
            seen.add(ing_clean.lower())

            # Categorize
            category = _categorize_ingredient(ing_clean)

            grocery = GroceryItem(
                user_id         = user_id,
                week_start      = week_start,
                ingredient_name = ing_clean,
                category        = category
            )
            db.session.add(grocery)

    db.session.commit()


def _categorize_ingredient(name):
    """Auto-categorize ingredient by name."""
    n = name.lower()
    if any(x in n for x in ["spinach","palak","methi","bathua","amaranth","moringa","drumstick leaf"]):
        return "Leafy Greens"
    elif any(x in n for x in ["banana","apple","orange","pomegranate","guava","papaya","amla","mango","kiwi","watermelon","jamun","dates","anjeer","fig","avocado"]):
        return "Fruits"
    elif any(x in n for x in ["tomato","onion","carrot","cucumber","capsicum","cabbage","broccoli","cauliflower","peas","beans","lauki","turai","karela","gourd","yam","potato","beetroot","mushroom","corn","radish","celery"]):
        return "Vegetables"
    elif any(x in n for x in ["moong","masoor","toor","chana","rajma","lobia","urad","dal","lentil","chickpea","sprout","soya"]):
        return "Lentils & Legumes"
    elif any(x in n for x in ["rice","wheat","atta","oats","ragi","bajra","jowar","quinoa","millet","barley","rava","poha","bread"]):
        return "Grains & Cereals"
    elif any(x in n for x in ["milk","curd","yogurt","buttermilk","paneer","ghee","butter","dairy"]):
        return "Dairy"
    elif any(x in n for x in ["egg","eggs"]):
        return "Eggs"
    elif any(x in n for x in ["chicken","fish","salmon","sardine","mackerel","tuna","prawn","turkey","rohu","katla","mutton"]):
        return "Protein / Non-Veg"
    elif any(x in n for x in ["almond","walnut","cashew","peanut","pumpkin seed","sunflower","flaxseed","chia","sesame","til","makhana","nut","seed"]):
        return "Nuts & Seeds"
    elif any(x in n for x in ["garlic","ginger","turmeric","cumin","jeera","coriander","pepper","cardamom","cinnamon","mustard","fenugreek","ajwain","tulsi","mint","lemon","lime","chilli","spice","masala","herb"]):
        return "Herbs & Spices"
    elif any(x in n for x in ["oil","olive","mustard oil"]):
        return "Oils"
    elif any(x in n for x in ["coconut water","green tea","hibiscus","water","juice","tea","milk"]):
        return "Beverages"
    else:
        return "Other"


# ============================================================
# MARK MEAL DONE
# ============================================================

@meal_bp.route("/done/<int:item_id>")
@login_required
def meal_done(item_id):
    from datetime import datetime
    item = MealItem.query.filter_by(id=item_id).first_or_404()

    # Ensure the meal plan belongs to current user
    if item.meal_plan.user_id != current_user.id:
        flash("Unauthorised.", "danger")
        return redirect(url_for("meal.meals"))

    item.completed    = not item.completed
    item.completed_at = datetime.utcnow() if item.completed else None
    db.session.commit()

    # Update nutrition log
    _update_nutrition_log(current_user.id, item.meal_plan.id, item.day)

    return redirect(url_for("meal.meals"))


def _update_nutrition_log(user_id, plan_id, day_name):
    """Recompute and save daily nutrition log from completed meals."""
    today   = date.today()
    totals  = {"calories":0,"protein":0,"carbs":0,"fats":0,"fiber":0,"sodium":0}
    items   = MealItem.query.filter_by(plan_id=plan_id, day=day_name).all()
    done    = completed = 0

    for item in items:
        done += 1
        if item.completed:
            completed += 1
            r = item.recipe
            totals["calories"] += r.calories or 0
            totals["protein"]  += r.protein  or 0
            totals["carbs"]    += r.carbs    or 0
            totals["fats"]     += r.fats     or 0
            totals["fiber"]    += r.fiber    or 0
            totals["sodium"]   += r.sodium   or 0

    from models import NutritionDailyLog
    log = NutritionDailyLog.query.filter_by(user_id=user_id, log_date=today).first()
    if not log:
        log = NutritionDailyLog(user_id=user_id, log_date=today)
        db.session.add(log)

    log.total_calories  = totals["calories"]
    log.total_protein   = totals["protein"]
    log.total_carbs     = totals["carbs"]
    log.total_fats      = totals["fats"]
    log.total_fiber     = totals["fiber"]
    log.total_sodium    = totals["sodium"]
    log.meals_completed = completed
    log.meals_planned   = done

    # Health score
    from flask_login import current_user
    try:
        user        = current_user._get_current_object()
        cal_score   = min(100, int(totals["calories"] / max(1, user.daily_calorie_target) * 100))
        pro_score   = min(100, int(totals["protein"]  / max(1, user.daily_protein_target) * 100))
        log.health_score = round((cal_score + pro_score) / 2)
    except Exception:
        log.health_score = 0

    db.session.commit()


# ============================================================
# REGENERATE SINGLE MEAL
# ============================================================

@meal_bp.route("/regenerate/<int:item_id>")
@login_required
def regenerate_meal(item_id):
    item = MealItem.query.filter_by(id=item_id).first_or_404()

    if item.meal_plan.user_id != current_user.id:
        flash("Unauthorised.", "danger")
        return redirect(url_for("meal.meals"))

    if item.locked:
        flash("This meal is locked. Unlock it first.", "warning")
        return redirect(url_for("meal.meals"))

    # Get exclusions: other meals in same plan to avoid repeats
    used = [mi.recipe_id for mi in MealItem.query.filter_by(plan_id=item.plan_id).all() if mi.id != item.id]

    # Find slot budget
    cal_budget = dict((s[0], s[2]) for s in MEAL_SLOTS).get(item.meal_slot, 400)

    new_recipe = pick_recipe_for_slot(
        current_user, item.meal_slot, cal_budget, exclude_ids=used
    )

    if new_recipe:
        item.recipe_id  = new_recipe.id
        item.completed  = False
        item.completed_at = None
        db.session.commit()
        flash(f"Meal replaced with {new_recipe.name}.", "success")
    else:
        flash("No alternative recipe found for this slot.", "warning")

    return redirect(url_for("meal.meals"))


# ============================================================
# SAVE MEAL NOTE
# ============================================================

@meal_bp.route("/note/<int:item_id>", methods=["POST"])
@login_required
def meal_note(item_id):
    item = MealItem.query.filter_by(id=item_id).first_or_404()

    if item.meal_plan.user_id != current_user.id:
        return jsonify({"success": False}), 403

    item.note = request.form.get("note", "").strip() or None
    db.session.commit()
    flash("Note saved.", "success")
    return redirect(url_for("meal.meals"))


# ============================================================
# LOCK / UNLOCK MEAL
# ============================================================

@meal_bp.route("/lock/<int:item_id>")
@login_required
def lock_meal(item_id):
    item = MealItem.query.filter_by(id=item_id).first_or_404()
    if item.meal_plan.user_id != current_user.id:
        return jsonify({"success": False}), 403
    item.locked = not item.locked
    db.session.commit()
    return jsonify({"success": True, "locked": item.locked})


# ============================================================
# RECIPES — LIST
# ============================================================

@meal_bp.route("/recipes")
@login_required
def recipes():
    search          = request.args.get("search", "").strip()
    selected_cat    = request.args.get("category", "all")
    selected_goal   = request.args.get("goal", "all")
    selected_diet   = request.args.get("diet", "all")

    query = Recipe.query

    if search:
        query = query.filter(
            or_(
                Recipe.name.ilike(f"%{search}%"),
                Recipe.ingredients.ilike(f"%{search}%"),
                Recipe.health_benefits.ilike(f"%{search}%")
            )
        )

    if selected_cat and selected_cat != "all":
        query = query.filter(Recipe.category == selected_cat)

    if selected_goal == "bp":
        query = query.filter(Recipe.bp_friendly == True)
    elif selected_goal == "weight":
        query = query.filter(Recipe.weight_loss_friendly == True)

    if selected_diet == "veg":
        query = query.filter(Recipe.is_veg == True)
    elif selected_diet == "nonveg":
        query = query.filter(Recipe.is_veg == False)

    all_recipes = query.order_by(Recipe.name).all()

    # All categories for filter dropdown
    categories = sorted(set(
        r.category for r in Recipe.query.with_entities(Recipe.category).distinct().all()
        if r.category
    ))

    # Get user's favorite IDs
    fav_ids = {f.recipe_id for f in Favorite.query.filter_by(user_id=current_user.id).all()}

    return render_template(
        "meals/recipes.html",
        recipes          = all_recipes,
        categories       = categories,
        search           = search,
        selected_category= selected_cat,
        selected_goal    = selected_goal,
        selected_diet    = selected_diet,
        fav_ids          = fav_ids,
    )


# ============================================================
# RECIPE DETAIL
# ============================================================

@meal_bp.route("/recipes/<int:recipe_id>")
@login_required
def recipe_detail(recipe_id):
    recipe  = Recipe.query.get_or_404(recipe_id)
    is_fav  = Favorite.query.filter_by(
        user_id=current_user.id, recipe_id=recipe_id
    ).first() is not None

    # Related recipes: same category, different id
    related = Recipe.query.filter(
        Recipe.category == recipe.category,
        Recipe.id != recipe_id
    ).limit(4).all()

    return render_template(
        "meals/recipe_detail.html",
        recipe  = recipe,
        related = related,
        is_fav  = is_fav,
    )


# ============================================================
# FAVOURITE RECIPE
# ============================================================

@meal_bp.route("/recipes/<int:recipe_id>/favorite")
@login_required
def favorite_recipe(recipe_id):
    Recipe.query.get_or_404(recipe_id)

    existing = Favorite.query.filter_by(
        user_id=current_user.id, recipe_id=recipe_id
    ).first()

    if existing:
        db.session.delete(existing)
        db.session.commit()
        flash("Removed from favourites.", "info")
    else:
        fav = Favorite(user_id=current_user.id, recipe_id=recipe_id)
        db.session.add(fav)
        db.session.commit()
        flash("Added to favourites! ❤️", "success")

    return redirect(url_for("meal.recipe_detail", recipe_id=recipe_id))


# ============================================================
# GROCERY LIST
# ============================================================

@meal_bp.route("/grocery")
@login_required
def grocery_list():
    today      = date.today()
    week_start = today - timedelta(days=today.weekday())

    grocery_items = GroceryItem.query.filter_by(
        user_id    = current_user.id,
        week_start = week_start
    ).order_by(GroceryItem.category, GroceryItem.ingredient_name).all()

    # If no items, try to generate from active plan
    if not grocery_items:
        active_plan = MealPlan.query.filter_by(
            user_id=current_user.id, is_active=True
        ).first()
        if active_plan:
            _generate_grocery_list(current_user.id, active_plan.id, week_start)
            grocery_items = GroceryItem.query.filter_by(
                user_id=current_user.id, week_start=week_start
            ).order_by(GroceryItem.category, GroceryItem.ingredient_name).all()

    # Group by category
    from collections import defaultdict
    grouped = defaultdict(list)
    for item in grocery_items:
        grouped[item.category].append(item)

    return render_template(
        "meals/grocery_list.html",
        grocery_items  = [g.ingredient_name for g in grocery_items],
        grouped        = dict(grouped),
        week_start     = week_start,
        today          = today,
    )


# ============================================================
# MARK GROCERY ITEM PURCHASED (AJAX)
# ============================================================

@meal_bp.route("/grocery/toggle/<int:item_id>", methods=["POST"])
@login_required
def toggle_grocery(item_id):
    from datetime import datetime
    item = GroceryItem.query.filter_by(
        id=item_id, user_id=current_user.id
    ).first_or_404()

    item.purchased    = not item.purchased
    item.purchased_at = datetime.utcnow() if item.purchased else None
    db.session.commit()

    return jsonify({"success": True, "purchased": item.purchased})


# ============================================================
# FAVOURITES LIST
# ============================================================

@meal_bp.route("/favourites")
@login_required
def favourites():
    favs = Favorite.query.filter_by(user_id=current_user.id)\
                         .order_by(Favorite.saved_at.desc()).all()
    recipes = [f.recipe for f in favs]
    return render_template("meals/favourites.html", recipes=recipes)