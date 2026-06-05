# ============================================================
# ADAPTIVE HEALTH MANAGEMENT PLATFORM
# models.py — Complete Database Models
# ============================================================

from datetime import datetime, date
from flask_login import UserMixin
# from app import db, bcrypt
from extensions import db, bcrypt
import math


# ============================================================
# SECTION 1 — AUTH & USER
# ============================================================

class User(UserMixin, db.Model):
    """Core user account. Authentication only."""
    __tablename__ = "users"

    id              = db.Column(db.Integer, primary_key=True)
    name            = db.Column(db.String(120), nullable=False)
    email           = db.Column(db.String(180), unique=True, nullable=False, index=True)
    password_hash   = db.Column(db.String(255), nullable=False)
    is_active       = db.Column(db.Boolean, default=True)
    is_verified     = db.Column(db.Boolean, default=False)
    onboarding_done = db.Column(db.Boolean, default=False)
    dark_mode       = db.Column(db.Boolean, default=False)
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)
    last_login      = db.Column(db.DateTime, nullable=True)
    last_updated    = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # ── Relationships ─────────────────────────────────────────
    health_profile  = db.relationship("UserHealthProfile", backref="user", uselist=False, cascade="all, delete-orphan")
    conditions      = db.relationship("UserCondition",     backref="user", cascade="all, delete-orphan")
    goals           = db.relationship("UserGoal",          backref="user", uselist=False, cascade="all, delete-orphan")
    health_metrics  = db.relationship("HealthMetric",      backref="user", cascade="all, delete-orphan", lazy="dynamic")
    meal_plans      = db.relationship("MealPlan",          backref="user", cascade="all, delete-orphan", lazy="dynamic")
    favorites       = db.relationship("Favorite",          backref="user", cascade="all, delete-orphan")
    grocery_items   = db.relationship("GroceryItem",       backref="user", cascade="all, delete-orphan", lazy="dynamic")
    alerts          = db.relationship("Alert",             backref="user", cascade="all, delete-orphan", lazy="dynamic")
    medicines       = db.relationship("Medicine",          backref="user", cascade="all, delete-orphan")
    nutrition_logs  = db.relationship("NutritionDailyLog", backref="user", cascade="all, delete-orphan", lazy="dynamic")
    weekly_insights = db.relationship("WeeklyInsight",     backref="user", cascade="all, delete-orphan", lazy="dynamic")

    # ── Password Methods ──────────────────────────────────────
    def set_password(self, password):
        self.password_hash = bcrypt.generate_password_hash(password).decode("utf-8")

    def check_password(self, password):
        return bcrypt.check_password_hash(self.password_hash, password)

    # ── Computed Properties ───────────────────────────────────
    @property
    def bmi(self):
        """Compute BMI dynamically from profile."""
        if not self.health_profile:
            return None
        h = self.health_profile.height_cm
        w = self.health_profile.current_weight_kg
        if not h or not w:
            return None
        height_m = h / 100
        return round(w / (height_m ** 2), 1)

    @property
    def bmi_status(self):
        bmi = self.bmi
        if bmi is None: return "Unknown"
        if bmi < 18.5:  return "Underweight"
        elif bmi < 25:  return "Normal"
        elif bmi < 30:  return "Overweight"
        elif bmi < 35:  return "Obese I"
        elif bmi < 40:  return "Obese II"
        else:           return "Obese III"

    @property
    def age(self):
        if not self.health_profile or not self.health_profile.date_of_birth:
            return None
        today = date.today()
        dob = self.health_profile.date_of_birth
        return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))

    @property
    def daily_calorie_target(self):
        """Mifflin-St Jeor equation + activity + goal modifier."""
        p = self.health_profile
        if not p:
            return 2000
        w = p.current_weight_kg or 70
        h = p.height_cm or 170
        age = self.age or 30
        gender = p.gender or "female"

        # BMR
        if gender == "male":
            bmr = (10 * w) + (6.25 * h) - (5 * age) + 5
        else:
            bmr = (10 * w) + (6.25 * h) - (5 * age) - 161

        # Activity multiplier
        activity_map = {
            "sedentary": 1.2,
            "light":     1.375,
            "moderate":  1.55,
            "active":    1.725,
            "very_active": 1.9,
        }
        factor = activity_map.get(p.activity_level or "sedentary", 1.2)
        tdee = bmr * factor

        # Goal modifier
        goal = self.goals
        if goal:
            if goal.primary_goal == "weight_loss":
                speed_map = {"slow": 250, "normal": 500, "fast": 750}
                deficit = speed_map.get(goal.goal_speed or "normal", 500)
                return max(1200, int(tdee - deficit))
            elif goal.primary_goal == "weight_gain":
                return int(tdee + 400)

        return int(tdee)

    @property
    def daily_protein_target(self):
        """Protein target based on weight and conditions."""
        if not self.health_profile:
            return 80
        w = self.health_profile.current_weight_kg or 70
        condition_names = [c.condition.name for c in self.conditions]
        if "High Blood Pressure" in condition_names:
            return int(w * 1.0)
        elif any("Weight Loss" in n for n in condition_names):
            return int(w * 1.4)
        return int(w * 1.0)

    @property
    def condition_names(self):
        return [uc.condition.name for uc in self.conditions]

    @property
    def has_bp(self):
        return "High Blood Pressure" in self.condition_names

    @property
    def has_diabetes(self):
        return any("Diabetes" in n for n in self.condition_names)

    @property
    def has_weight_loss(self):
        return any("Weight Loss" in n for n in self.condition_names)

    @property
    def has_sleep_apnea(self):
        return "Sleep Apnea" in self.condition_names

    def __repr__(self):
        return f"<User {self.id}: {self.email}>"


# ============================================================
# SECTION 2 — HEALTH PROFILE
# ============================================================

class UserHealthProfile(db.Model):
    """Extended health information linked to user."""
    __tablename__ = "user_health_profiles"

    id                  = db.Column(db.Integer, primary_key=True)
    user_id             = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True, nullable=False)

    # Physical
    gender              = db.Column(db.String(20), nullable=True)   # male / female / other
    date_of_birth       = db.Column(db.Date, nullable=True)
    height_cm           = db.Column(db.Float, nullable=True)
    current_weight_kg   = db.Column(db.Float, nullable=True)

    # Lifestyle
    activity_level      = db.Column(db.String(30), default="sedentary")
    # sedentary / light / moderate / active / very_active

    diet_preference     = db.Column(db.String(30), default="vegetarian")
    # vegetarian / non_vegetarian / vegan / eggetarian

    # Onboarding state
    onboarding_step     = db.Column(db.Integer, default=1)

    # Meta
    created_at          = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at          = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<HealthProfile user_id={self.user_id}>"


# ============================================================
# SECTION 3 — HEALTH CONDITIONS
# ============================================================

class HealthCondition(db.Model):
    """Master list of all health conditions."""
    __tablename__ = "health_conditions"

    id          = db.Column(db.Integer, primary_key=True)
    name        = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)
    icon        = db.Column(db.String(10), default="🏥")
    category    = db.Column(db.String(50), nullable=True)
    # cardiovascular / metabolic / hormonal / lifestyle

    users       = db.relationship("UserCondition", backref="condition", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Condition {self.name}>"


class UserCondition(db.Model):
    """Many-to-many: user ↔ health conditions."""
    __tablename__ = "user_conditions"

    id              = db.Column(db.Integer, primary_key=True)
    user_id         = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    condition_id    = db.Column(db.Integer, db.ForeignKey("health_conditions.id"), nullable=False)
    severity        = db.Column(db.String(20), default="moderate")   # mild / moderate / severe
    diagnosed_at    = db.Column(db.Date, nullable=True)
    notes           = db.Column(db.Text, nullable=True)
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint("user_id", "condition_id"),)

    def __repr__(self):
        return f"<UserCondition user={self.user_id} condition={self.condition_id}>"


# ============================================================
# SECTION 4 — USER GOALS
# ============================================================

class UserGoal(db.Model):
    """User health and fitness goals."""
    __tablename__ = "user_goals"

    id                  = db.Column(db.Integer, primary_key=True)
    user_id             = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True, nullable=False)

    # Weight goals
    target_weight_kg    = db.Column(db.Float, nullable=True)
    start_weight_kg     = db.Column(db.Float, nullable=True)
    goal_speed          = db.Column(db.String(20), default="normal")    # slow / normal / fast

    # Nutrition targets (overrides computed defaults)
    target_calories     = db.Column(db.Integer, nullable=True)
    target_protein_g    = db.Column(db.Integer, nullable=True)
    target_water_litres = db.Column(db.Float, default=2.5)
    target_steps        = db.Column(db.Integer, default=8000)

    # BP goals
    target_bp_systolic  = db.Column(db.Integer, default=130)
    target_bp_diastolic = db.Column(db.Integer, default=80)

    # Sugar goals
    target_fasting_sugar = db.Column(db.Float, nullable=True)

    # Primary goal
    primary_goal        = db.Column(db.String(50), default="healthy_lifestyle")
    # weight_loss / weight_gain / control_bp / control_sugar / healthy_lifestyle

    # Dates
    goal_start_date     = db.Column(db.Date, default=date.today)
    goal_review_date    = db.Column(db.Date, nullable=True)
    created_at          = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at          = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<UserGoal user={self.user_id} goal={self.primary_goal}>"


# ============================================================
# SECTION 5 — RECIPE SYSTEM
# ============================================================

class Recipe(db.Model):
    """Complete recipe with nutrition and health tags."""
    __tablename__ = "recipes"

    id              = db.Column(db.Integer, primary_key=True)

    # Basic info
    name            = db.Column(db.String(200), nullable=False, index=True)
    description     = db.Column(db.Text, nullable=True)
    image           = db.Column(db.String(500), nullable=True)
    category        = db.Column(db.String(50), nullable=True)
    meal_type       = db.Column(db.String(50), nullable=True)
    cooking_time    = db.Column(db.String(30), default="20 mins")
    servings        = db.Column(db.Integer, default=1)
    difficulty      = db.Column(db.String(20), default="easy")
    cuisine_type    = db.Column(db.String(50), default="Indian")
    is_veg          = db.Column(db.Boolean, default=True)
    ingredients     = db.Column(db.Text, nullable=True)
    steps           = db.Column(db.Text, nullable=True)
    tags            = db.Column(db.Text, nullable=True)
    health_benefits = db.Column(db.Text, nullable=True)

    # ── Nutrition fields ──────────────────────────────────────
    calories        = db.Column(db.Integer, default=0)
    protein         = db.Column(db.Float, default=0)
    carbs           = db.Column(db.Float, default=0)
    fats            = db.Column(db.Float, default=0)
    fiber           = db.Column(db.Float, default=0)
    sugar           = db.Column(db.Float, default=0)
    sodium          = db.Column(db.Float, default=0)        # mg — KEY for BP
    potassium       = db.Column(db.Float, default=0)        # mg — KEY for BP
    cholesterol     = db.Column(db.Float, default=0)        # mg
    iron            = db.Column(db.Float, default=0)        # mg
    calcium         = db.Column(db.Float, default=0)        # mg
    vitamin_c       = db.Column(db.Float, default=0)        # mg
    glycemic_index  = db.Column(db.Integer, nullable=True)  # KEY for diabetes

    # ── Health flags ──────────────────────────────────────────
    bp_friendly             = db.Column(db.Boolean, default=True)
    diabetes_friendly       = db.Column(db.Boolean, default=True)
    weight_loss_friendly    = db.Column(db.Boolean, default=True)
    heart_friendly          = db.Column(db.Boolean, default=True)
    kidney_friendly         = db.Column(db.Boolean, default=True)
    high_protein            = db.Column(db.Boolean, default=False)
    high_fiber              = db.Column(db.Boolean, default=False)
    low_sodium              = db.Column(db.Boolean, default=True)
    low_sugar               = db.Column(db.Boolean, default=True)
    anti_inflammatory       = db.Column(db.Boolean, default=False)
    omega3_rich             = db.Column(db.Boolean, default=False)

    # ── Scores (computed) ─────────────────────────────────────
    bp_score                = db.Column(db.Float, default=0.0)
    diabetes_score          = db.Column(db.Float, default=0.0)
    weight_loss_score       = db.Column(db.Float, default=0.0)
    nutrition_score         = db.Column(db.Float, default=0.0)

    created_at              = db.Column(db.DateTime, default=datetime.utcnow)

    # ── Relationships ─────────────────────────────────────────
    favorites   = db.relationship("Favorite",  backref="recipe", cascade="all, delete-orphan")
    meal_items  = db.relationship("MealItem",  backref="recipe")

    # ── Computed Score Methods ────────────────────────────────
    def compute_scores(self):
        """Compute and store all health scores for this recipe."""
        self.bp_score           = self._compute_bp_score()
        self.diabetes_score     = self._compute_diabetes_score()
        self.weight_loss_score  = self._compute_weight_loss_score()
        self.nutrition_score    = self._compute_nutrition_score()

    def _compute_bp_score(self):
        score = 0
        if (self.sodium or 0) < 400:    score += 40
        elif (self.sodium or 0) < 600:  score += 20
        if (self.potassium or 0) > 400: score += 30
        if self.omega3_rich:            score += 15
        if self.anti_inflammatory:      score += 10
        if self.bp_friendly:            score += 5
        return min(100, score)

    def _compute_diabetes_score(self):
        score = 0
        gi = self.glycemic_index or 70
        if gi < 55:      score += 40
        elif gi < 70:    score += 20
        if (self.sugar or 0) < 5:    score += 30
        elif (self.sugar or 0) < 10: score += 15
        if (self.fiber or 0) >= 7:   score += 20
        elif (self.fiber or 0) >= 4: score += 10
        if self.diabetes_friendly:   score += 10
        return min(100, score)

    def _compute_weight_loss_score(self):
        score = 0
        if (self.calories or 0) < 300:  score += 40
        elif (self.calories or 0) < 450: score += 20
        if (self.protein or 0) >= 20:   score += 30
        elif (self.protein or 0) >= 12: score += 15
        if (self.fiber or 0) >= 7:      score += 20
        elif (self.fiber or 0) >= 4:    score += 10
        if self.weight_loss_friendly:   score += 10
        return min(100, score)

    def _compute_nutrition_score(self):
        score = 0
        if (self.protein or 0) >= 15:  score += 25
        if (self.fiber or 0) >= 5:     score += 25
        if (self.sodium or 0) < 600:   score += 25
        if (self.fats or 0) < 20:      score += 15
        if (self.sugar or 0) < 8:      score += 10
        return min(100, score)

    def composite_score(self, conditions):
        """
        Compute weighted score for a user with given conditions.
        conditions: list of condition name strings
        """
        weights = {}
        if "High Blood Pressure" in conditions:
            weights["bp"] = 0.40
        if any("Diabetes" in c for c in conditions):
            weights["diabetes"] = 0.35
        if any("Weight Loss" in c for c in conditions):
            weights["weight_loss"] = 0.25

        if not weights:
            return self.nutrition_score or 50

        total_weight = sum(weights.values())
        score = 0
        if "bp" in weights:
            score += (self.bp_score or 0) * (weights["bp"] / total_weight)
        if "diabetes" in weights:
            score += (self.diabetes_score or 0) * (weights["diabetes"] / total_weight)
        if "weight_loss" in weights:
            score += (self.weight_loss_score or 0) * (weights["weight_loss"] / total_weight)

        return round(score, 1)

    def __repr__(self):
        return f"<Recipe {self.id}: {self.name}>"


class Favorite(db.Model):
    """User saved/favorited recipes."""
    __tablename__ = "favorites"

    id          = db.Column(db.Integer, primary_key=True)
    user_id     = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    recipe_id   = db.Column(db.Integer, db.ForeignKey("recipes.id"), nullable=False)
    saved_at    = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint("user_id", "recipe_id"),)


# ============================================================
# SECTION 6 — MEAL PLANNER
# ============================================================

class MealPlan(db.Model):
    """Weekly meal plan for a user."""
    __tablename__ = "meal_plans"

    id              = db.Column(db.Integer, primary_key=True)
    user_id         = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    week_start_date = db.Column(db.Date, nullable=False)
    generated_at    = db.Column(db.DateTime, default=datetime.utcnow)
    is_active       = db.Column(db.Boolean, default=True)
    notes           = db.Column(db.Text, nullable=True)

    items           = db.relationship("MealItem", backref="meal_plan", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<MealPlan {self.id} week={self.week_start_date}>"


class MealItem(db.Model):
    """Individual meal slot within a meal plan."""
    __tablename__ = "meal_items"

    id              = db.Column(db.Integer, primary_key=True)
    plan_id         = db.Column(db.Integer, db.ForeignKey("meal_plans.id"), nullable=False)
    recipe_id       = db.Column(db.Integer, db.ForeignKey("recipes.id"), nullable=False)

    day             = db.Column(db.String(20), nullable=False)
    # Monday / Tuesday / ... / Sunday

    meal_slot       = db.Column(db.String(30), nullable=False)
    # Morning Drink / Breakfast / Lunch / Snacks / Dinner

    slot_order      = db.Column(db.Integer, default=0)
    # 1=Morning, 2=Breakfast, 3=Lunch, 4=Snacks, 5=Dinner

    completed       = db.Column(db.Boolean, default=False)
    completed_at    = db.Column(db.DateTime, nullable=True)
    locked          = db.Column(db.Boolean, default=False)
    note            = db.Column(db.Text, nullable=True)

    created_at      = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<MealItem {self.day} {self.meal_slot} recipe={self.recipe_id}>"


# ============================================================
# SECTION 7 — GROCERY SYSTEM
# ============================================================

class GroceryItem(db.Model):
    """Auto-generated grocery list from meal plan."""
    __tablename__ = "grocery_items"

    id              = db.Column(db.Integer, primary_key=True)
    user_id         = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    week_start      = db.Column(db.Date, nullable=False)
    ingredient_name = db.Column(db.String(200), nullable=False)
    category        = db.Column(db.String(50), default="Other")
    # Vegetables / Fruits / Lentils / Grains / Dairy / Protein / Nuts / Spices / Other

    quantity        = db.Column(db.String(50), nullable=True)
    unit            = db.Column(db.String(30), nullable=True)
    purchased       = db.Column(db.Boolean, default=False)
    purchased_at    = db.Column(db.DateTime, nullable=True)
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<GroceryItem {self.ingredient_name}>"


# ============================================================
# SECTION 8 — UNIFIED TRACKER SYSTEM
# ============================================================

class HealthMetric(db.Model):
    """
    Unified tracker table for ALL health metrics.
    One table — scalable, flexible, easy analytics.
    """
    __tablename__ = "health_metrics"

    id          = db.Column(db.Integer, primary_key=True)
    user_id     = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)

    metric_type = db.Column(db.String(30), nullable=False, index=True)
    # bp / weight / sugar / water / steps / sleep / exercise / mood / calories / medicine

    value_1     = db.Column(db.Float, nullable=True)
    # bp → systolic | weight → kg | sugar → fasting | water → litres | steps → count

    value_2     = db.Column(db.Float, nullable=True)
    # bp → diastolic | sleep → quality | sugar → post_meal

    value_3     = db.Column(db.Float, nullable=True)
    # bp → pulse | exercise → type_code

    unit        = db.Column(db.String(20), nullable=True)
    # mmHg / kg / mg_dL / litres / steps / hours

    source      = db.Column(db.String(20), default="manual")
    # manual / auto

    notes       = db.Column(db.Text, nullable=True)
    recorded_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    def __repr__(self):
        return f"<HealthMetric {self.metric_type} user={self.user_id} val={self.value_1}>"

    @property
    def bp_status(self):
        """Only relevant for bp metrics."""
        if self.metric_type != "bp":
            return None
        s = self.value_1 or 0
        d = self.value_2 or 0
        if s < 120 and d < 80:   return "Normal"
        elif s < 130 and d < 80: return "Elevated"
        elif s < 140 or d < 90:  return "High Stage 1"
        elif s < 180 or d < 120: return "High Stage 2"
        else:                     return "Crisis"


# ============================================================
# SECTION 9 — DAILY NUTRITION LOG
# ============================================================

class NutritionDailyLog(db.Model):
    """
    Daily aggregated nutrition summary.
    Pre-computed to avoid live recalculation on every page load.
    """
    __tablename__ = "nutrition_daily_logs"

    id              = db.Column(db.Integer, primary_key=True)
    user_id         = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    log_date        = db.Column(db.Date, nullable=False, index=True)

    total_calories  = db.Column(db.Integer, default=0)
    total_protein   = db.Column(db.Float, default=0)
    total_carbs     = db.Column(db.Float, default=0)
    total_fats      = db.Column(db.Float, default=0)
    total_fiber     = db.Column(db.Float, default=0)
    total_sodium    = db.Column(db.Float, default=0)
    total_potassium = db.Column(db.Float, default=0)
    total_sugar     = db.Column(db.Float, default=0)
    total_water     = db.Column(db.Float, default=0)

    meals_completed = db.Column(db.Integer, default=0)
    meals_planned   = db.Column(db.Integer, default=5)
    health_score    = db.Column(db.Float, default=0)

    created_at      = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at      = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint("user_id", "log_date"),)

    def __repr__(self):
        return f"<NutritionLog {self.log_date} user={self.user_id}>"


# ============================================================
# SECTION 10 — ALERT SYSTEM
# ============================================================

class Alert(db.Model):
    """Health alerts generated by the alert engine."""
    __tablename__ = "alerts"

    id              = db.Column(db.Integer, primary_key=True)
    user_id         = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)

    alert_type      = db.Column(db.String(20), nullable=False)
    # emergency / warning / recommendation / reminder

    category        = db.Column(db.String(30), nullable=True)
    # bp / sugar / weight / nutrition / medicine / hydration

    title           = db.Column(db.String(200), nullable=False)
    message         = db.Column(db.Text, nullable=False)
    action_text     = db.Column(db.String(100), nullable=True)
    action_url      = db.Column(db.String(200), nullable=True)

    trigger_value   = db.Column(db.Float, nullable=True)
    is_read         = db.Column(db.Boolean, default=False)
    is_dismissed    = db.Column(db.Boolean, default=False)

    created_at      = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    expires_at      = db.Column(db.DateTime, nullable=True)

    def __repr__(self):
        return f"<Alert {self.alert_type}: {self.title[:30]}>"


# ============================================================
# SECTION 11 — MEDICINE SYSTEM
# ============================================================

class Medicine(db.Model):
    """User medicines with reminders."""
    __tablename__ = "medicines"

    id          = db.Column(db.Integer, primary_key=True)
    user_id     = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    name        = db.Column(db.String(200), nullable=False)
    dosage      = db.Column(db.String(100), nullable=True)
    timing      = db.Column(db.String(20), nullable=True)   # "08:00"
    frequency   = db.Column(db.String(30), default="daily")
    # daily / twice_daily / weekly / as_needed

    with_food   = db.Column(db.String(20), default="doesn't_matter")
    # yes / no / doesn't_matter

    condition   = db.Column(db.String(100), nullable=True)
    # Which condition this medicine is for

    active      = db.Column(db.Boolean, default=True)
    start_date  = db.Column(db.Date, default=date.today)
    notes       = db.Column(db.Text, nullable=True)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)

    logs        = db.relationship("MedicineLog", backref="medicine", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Medicine {self.name}>"


class MedicineLog(db.Model):
    """Daily log of whether medicine was taken."""
    __tablename__ = "medicine_logs"

    id          = db.Column(db.Integer, primary_key=True)
    medicine_id = db.Column(db.Integer, db.ForeignKey("medicines.id"), nullable=False)
    user_id     = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    taken       = db.Column(db.Boolean, default=False)
    log_date    = db.Column(db.Date, default=date.today, index=True)
    logged_at   = db.Column(db.DateTime, default=datetime.utcnow)
    notes       = db.Column(db.Text, nullable=True)

    __table_args__ = (db.UniqueConstraint("medicine_id", "log_date"),)


# ============================================================
# SECTION 12 — WEEKLY INSIGHTS
# ============================================================

class WeeklyInsight(db.Model):
    """Pre-generated weekly intelligence insights."""
    __tablename__ = "weekly_insights"

    id              = db.Column(db.Integer, primary_key=True)
    user_id         = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    week_start      = db.Column(db.Date, nullable=False, index=True)

    insight_text    = db.Column(db.Text, nullable=False)
    metric_type     = db.Column(db.String(30), nullable=True)
    change_value    = db.Column(db.Float, nullable=True)
    direction       = db.Column(db.String(20), nullable=True)
    # improving / worsening / stable

    priority        = db.Column(db.Integer, default=3)
    # 1=critical, 2=important, 3=informational

    icon            = db.Column(db.String(10), default="📊")
    generated_at    = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<WeeklyInsight user={self.user_id} week={self.week_start}>"


# ============================================================
# SECTION 13 — SEED HELPER
# ============================================================

def seed_health_conditions():
    """
    Seed the HealthCondition table with all supported conditions.
    Call once after db.create_all().
    """
    conditions = [
        {"name": "High Blood Pressure",   "icon": "❤️",  "category": "cardiovascular"},
        {"name": "Type 2 Diabetes",        "icon": "🩺",  "category": "metabolic"},
        {"name": "Pre-Diabetes",           "icon": "⚠️",  "category": "metabolic"},
        {"name": "High Cholesterol",       "icon": "🫀",  "category": "cardiovascular"},
        {"name": "Weight Loss Goal",       "icon": "⚖️",  "category": "lifestyle"},
        {"name": "Weight Gain Goal",       "icon": "💪",  "category": "lifestyle"},
        {"name": "PCOS / PCOD",            "icon": "🌸",  "category": "hormonal"},
        {"name": "Thyroid (Hypothyroid)",  "icon": "🦋",  "category": "hormonal"},
        {"name": "Heart Disease",          "icon": "💗",  "category": "cardiovascular"},
        {"name": "Kidney Disease (CKD)",   "icon": "🫘",  "category": "metabolic"},
        {"name": "Sleep Apnea",            "icon": "😴",  "category": "lifestyle"},
        {"name": "Fatty Liver",            "icon": "🫁",  "category": "metabolic"},
        {"name": "Acid Reflux / IBS",      "icon": "🔥",  "category": "digestive"},
        {"name": "Healthy Lifestyle",      "icon": "🌿",  "category": "lifestyle"},
        {"name": "Post-Pregnancy",         "icon": "👶",  "category": "hormonal"},
        {"name": "Menopause",              "icon": "🌺",  "category": "hormonal"},
    ]
    for c in conditions:
        existing = HealthCondition.query.filter_by(name=c["name"]).first()
        if not existing:
            db.session.add(HealthCondition(**c))
    db.session.commit()