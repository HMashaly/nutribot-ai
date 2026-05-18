"""
tools/nutrition_tools.py — NutriBot calculation & lookup tools.

All tools are pure Python / LangChain — no Streamlit imports here.
The remember_fact tool queues facts for HITL confirmation; the caller
(main.py) extracts pending_memories from the agent's intermediate steps
and returns them to the frontend for user confirmation.
"""

import os
from typing import ClassVar

import requests
from langchain.tools import tool


@tool
def calculate_bmi(weight_kg: float, height_cm: float) -> str:
    """
    Calculate Body Mass Index (BMI) given weight in kilograms and height in centimetres.
    Returns BMI value and WHO category with health notes.
    Example: calculate_bmi(70, 175)
    """
    if weight_kg <= 0 or height_cm <= 0:
        return "Error: weight and height must be positive numbers."

    height_m = height_cm / 100
    bmi = round(weight_kg / (height_m ** 2), 1)

    if bmi < 18.5:
        category = "Underweight"
        note = "Consider increasing caloric intake with nutrient-dense foods. Consult a doctor if significantly underweight."
    elif bmi < 25.0:
        category = "Normal weight"
        note = "Healthy range. Focus on maintaining a balanced diet and regular physical activity."
    elif bmi < 30.0:
        category = "Overweight"
        note = "A moderate caloric deficit (300–500 kcal/day) combined with exercise can help move to the healthy range."
    elif bmi < 35.0:
        category = "Obese (Class I)"
        note = "Consider consulting a dietitian and doctor. Gradual lifestyle changes are more sustainable than crash diets."
    else:
        category = "Obese (Class II/III)"
        note = "Medical supervision recommended. Focus on gradual, sustainable changes with professional support."

    return (
        f"📊 BMI Result:\n"
        f"  • BMI: {bmi}\n"
        f"  • Category: {category} (WHO classification)\n"
        f"  • Note: {note}\n\n"
        f"  ⚠️ BMI is a screening tool, not a diagnostic — it does not account for muscle mass, bone density, or fat distribution."
    )


@tool
def calculate_daily_calories(
    weight_kg: float,
    height_cm: float,
    age: int,
    gender: str,
    activity_level: str,
    goal: str = "maintenance",
) -> str:
    """
    Calculate Total Daily Energy Expenditure (TDEE) using the Mifflin-St Jeor formula.
    Parameters:
      - weight_kg: body weight in kilograms
      - height_cm: height in centimetres
      - age: age in years
      - gender: 'male' or 'female'
      - activity_level: one of 'sedentary', 'light', 'moderate', 'active', 'very_active'
      - goal: one of 'weight_loss', 'maintenance', 'muscle_gain' (default: maintenance)
    Returns TDEE and adjusted target calories for the specified goal.
    """
    if weight_kg <= 0 or height_cm <= 0 or age <= 0:
        return "Error: weight, height, and age must be positive numbers."

    gender = gender.lower().strip()
    activity_level = activity_level.lower().strip()
    goal = goal.lower().strip()

    if gender in ("male", "man", "m"):
        bmr = (10 * weight_kg) + (6.25 * height_cm) - (5 * age) + 5
    elif gender in ("female", "woman", "f"):
        bmr = (10 * weight_kg) + (6.25 * height_cm) - (5 * age) - 161
    else:
        return "Error: gender must be 'male' or 'female'."

    activity_multipliers = {
        "sedentary":   1.2,
        "light":       1.375,
        "moderate":    1.55,
        "active":      1.725,
        "very_active": 1.9,
    }
    multiplier = activity_multipliers.get(activity_level)
    if not multiplier:
        return f"Error: activity_level must be one of: {', '.join(activity_multipliers.keys())}"

    tdee = round(bmr * multiplier)

    goal_adjustments = {
        "weight_loss":  -400,
        "maintenance":   0,
        "muscle_gain":  +250,
    }
    adjustment = goal_adjustments.get(goal, 0)
    target = tdee + adjustment

    goal_labels = {
        "weight_loss": "Weight Loss (−400 kcal deficit)",
        "maintenance": "Maintenance",
        "muscle_gain": "Muscle Gain (+250 kcal surplus)",
    }

    return (
        f"🔥 Calorie Calculation:\n"
        f"  • BMR (at rest): {round(bmr)} kcal/day\n"
        f"  • TDEE (maintenance): {tdee} kcal/day\n"
        f"  • Goal: {goal_labels.get(goal, goal)}\n"
        f"  • 🎯 Target Calories: {target} kcal/day\n\n"
        f"  Activity level used: {activity_level} (×{multiplier})"
    )


@tool
def calculate_macros(daily_calories: float, goal: str) -> str:
    """
    Calculate recommended daily macronutrient targets (protein, carbs, fat) in grams.
    Parameters:
      - daily_calories: total daily calorie target (e.g. 1800)
      - goal: one of 'weight_loss', 'maintenance', 'muscle_gain'
    Returns grams of protein, carbohydrates, and fat per day.
    """
    if daily_calories <= 0:
        return "Error: daily_calories must be a positive number."

    goal = goal.lower().strip()

    splits = {
        "weight_loss":  (0.33, 0.32, 0.35),
        "maintenance":  (0.25, 0.50, 0.25),
        "muscle_gain":  (0.30, 0.45, 0.25),
    }

    if goal not in splits:
        return f"Error: goal must be one of: {', '.join(splits.keys())}"

    p_pct, c_pct, f_pct = splits[goal]
    protein_g = round((daily_calories * p_pct) / 4)
    carbs_g   = round((daily_calories * c_pct) / 4)
    fat_g     = round((daily_calories * f_pct) / 9)

    return (
        f"🥗 Daily Macro Targets for {goal.replace('_', ' ').title()}:\n"
        f"  • 🥩 Protein:       {protein_g}g  ({round(p_pct*100)}% of calories)\n"
        f"  • 🍚 Carbohydrates: {carbs_g}g  ({round(c_pct*100)}% of calories)\n"
        f"  • 🥑 Fat:           {fat_g}g   ({round(f_pct*100)}% of calories)\n\n"
        f"  Based on: {round(daily_calories)} kcal/day\n"
        f"  Calories per gram — Protein: 4 kcal | Carbs: 4 kcal | Fat: 9 kcal"
    )


@tool
def check_dietary_compatibility(food_item: str, dietary_restrictions: str) -> str:
    """
    Check if a food item is compatible with given dietary restrictions.
    Parameters:
      - food_item: the food or ingredient to check (e.g. 'gelatin', 'parmesan cheese', 'soy sauce')
      - dietary_restrictions: comma-separated list such as 'vegan, gluten-free, halal'
    Returns compatibility analysis with explanations.
    """
    food = food_item.lower().strip()
    restrictions = [r.strip().lower() for r in dietary_restrictions.split(",")]

    rules = {
        "vegan": {
            "avoid": [
                "meat", "beef", "chicken", "pork", "fish", "salmon", "tuna", "shrimp",
                "dairy", "milk", "cheese", "butter", "cream", "whey", "casein",
                "egg", "honey", "gelatin", "lard", "anchovy", "worcestershire",
                "rennet", "isinglass", "carmine", "shellac",
            ],
            "label": "Vegan",
        },
        "vegetarian": {
            "avoid": [
                "meat", "beef", "chicken", "pork", "fish", "salmon", "tuna",
                "shrimp", "anchovy", "gelatin", "lard", "rennet", "isinglass",
            ],
            "label": "Vegetarian",
        },
        "halal": {
            "avoid": [
                "pork", "pig", "ham", "bacon", "lard", "gelatin",
                "alcohol", "wine", "beer", "rum", "whisky",
                "blood", "black pudding",
            ],
            "label": "Halal",
        },
        "gluten-free": {
            "avoid": [
                "wheat", "flour", "bread", "pasta", "barley", "rye", "spelt",
                "semolina", "couscous", "seitan", "soy sauce", "malt", "beer",
            ],
            "label": "Gluten-Free",
        },
        "nut-free": {
            "avoid": [
                "peanut", "almond", "cashew", "walnut", "pistachio", "pecan",
                "hazelnut", "macadamia", "pine nut", "nut butter", "marzipan",
            ],
            "label": "Nut-Free",
        },
        "dairy-free": {
            "avoid": [
                "milk", "cheese", "butter", "cream", "yogurt", "whey",
                "casein", "lactose", "ghee", "kefir",
            ],
            "label": "Dairy-Free",
        },
    }

    results = []
    for restriction in restrictions:
        if restriction not in rules:
            results.append(f"⚠️  '{restriction}' — not a recognised restriction in my database.")
            continue

        rule = rules[restriction]
        flagged = [kw for kw in rule["avoid"] if kw in food]

        if flagged:
            results.append(
                f"❌ {rule['label']}: '{food_item}' may NOT be compatible "
                f"(contains/related to: {', '.join(flagged)})"
            )
        else:
            results.append(
                f"✅ {rule['label']}: '{food_item}' appears compatible "
                f"(no known {restriction} conflicts detected)"
            )

    note = (
        "\n\n⚠️ This is a basic keyword check. Always verify labels, ask manufacturers "
        "about cross-contamination, and consult a professional for strict medical requirements."
    )
    return "\n".join(results) + note


@tool
def remember_fact(fact: str) -> str:
    """
    Queue an important user fact to save for future sessions.
    Use when the user shares a durable preference, allergy, goal, or personal detail
    worth remembering (e.g. "I am lactose intolerant", "My goal is to run a marathon").
    The user must confirm in the UI before this is persisted to the database.
    Parameters:
      - fact: a concise statement of the fact to remember (max 200 chars)
    """
    if not fact.strip():
        return "No fact provided."
    return f"📝 Queued for confirmation: '{fact.strip()}'"


@tool
def search_usda_food(food_name: str) -> str:
    """
    Look up USDA FoodData Central nutrition values for a food item.
    Returns calories, protein, carbs, and fat per 100g when available.
    Use this for specific food nutritional data lookups.
    Parameters:
      - food_name: name of the food to search (e.g. 'avocado', 'chicken breast', 'oats')
    """
    if not food_name.strip():
        return "Please provide a food name."

    api_key = os.getenv("USDA_API_KEY", "DEMO_KEY")
    url = "https://api.nal.usda.gov/fdc/v1/foods/search"
    params = {"query": food_name, "api_key": api_key, "pageSize": 1}
    try:
        resp = requests.get(url, params=params, timeout=8)
        resp.raise_for_status()
    except requests.RequestException as exc:
        return f"USDA lookup failed: {exc}"

    foods = resp.json().get("foods", [])
    if not foods:
        return f"No USDA data found for '{food_name}'."

    food = foods[0]
    name = food.get("description", food_name)
    nutrients = {
        n.get("nutrientName"): n.get("value")
        for n in food.get("foodNutrients", [])
        if n.get("nutrientName")
    }
    return (
        f"USDA data for {name} (per 100g):\n"
        f"Calories: {nutrients.get('Energy', 'N/A')} kcal\n"
        f"Protein:  {nutrients.get('Protein', 'N/A')} g\n"
        f"Carbs:    {nutrients.get('Carbohydrate, by difference', 'N/A')} g\n"
        f"Fat:      {nutrients.get('Total lipid (fat)', 'N/A')} g"
    )
