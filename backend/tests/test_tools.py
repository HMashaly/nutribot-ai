"""
tests/test_tools.py — Unit tests for NutriBot calculation tools.

Run with:
    pytest tests/ -v
"""

import pytest


class TestCalculateBMI:
    def test_normal_bmi(self):
        from tools.nutrition_tools import calculate_bmi
        result = calculate_bmi.invoke({"weight_kg": 70, "height_cm": 175})
        assert "BMI" in result
        assert "Normal weight" in result

    def test_underweight(self):
        from tools.nutrition_tools import calculate_bmi
        result = calculate_bmi.invoke({"weight_kg": 45, "height_cm": 175})
        assert "Underweight" in result

    def test_obese(self):
        from tools.nutrition_tools import calculate_bmi
        result = calculate_bmi.invoke({"weight_kg": 120, "height_cm": 170})
        assert "Obese" in result

    def test_invalid_height_returns_error(self):
        from tools.nutrition_tools import calculate_bmi
        result = calculate_bmi.invoke({"weight_kg": 70, "height_cm": 0})
        assert "Error" in result


class TestCalculateDailyCalories:
    def test_sedentary_male(self):
        from tools.nutrition_tools import calculate_daily_calories
        result = calculate_daily_calories.invoke({
            "weight_kg": 80, "height_cm": 180, "age": 30,
            "gender": "male", "activity_level": "sedentary",
        })
        assert "Target Calories" in result

    def test_active_female(self):
        from tools.nutrition_tools import calculate_daily_calories
        result = calculate_daily_calories.invoke({
            "weight_kg": 60, "height_cm": 165, "age": 25,
            "gender": "female", "activity_level": "active",
        })
        assert "TDEE" in result

    def test_invalid_gender(self):
        from tools.nutrition_tools import calculate_daily_calories
        result = calculate_daily_calories.invoke({
            "weight_kg": 70, "height_cm": 170, "age": 30,
            "gender": "robot", "activity_level": "sedentary",
        })
        assert "Error" in result


class TestCalculateMacros:
    def test_weight_loss_macros(self):
        from tools.nutrition_tools import calculate_macros
        result = calculate_macros.invoke({"daily_calories": 1500, "goal": "weight_loss"})
        assert "Protein" in result
        assert "Carbohydrates" in result
        assert "Fat" in result

    def test_invalid_goal(self):
        from tools.nutrition_tools import calculate_macros
        result = calculate_macros.invoke({"daily_calories": 2000, "goal": "fly_to_moon"})
        assert "Error" in result


class TestDietaryCompatibility:
    def test_vegan_gelatin_incompatible(self):
        from tools.nutrition_tools import check_dietary_compatibility
        result = check_dietary_compatibility.invoke({
            "food_item": "gelatin", "dietary_restrictions": "vegan"
        })
        assert "❌" in result

    def test_halal_pork_incompatible(self):
        from tools.nutrition_tools import check_dietary_compatibility
        result = check_dietary_compatibility.invoke({
            "food_item": "pork ribs", "dietary_restrictions": "halal"
        })
        assert "❌" in result

    def test_vegan_apple_compatible(self):
        from tools.nutrition_tools import check_dietary_compatibility
        result = check_dietary_compatibility.invoke({
            "food_item": "apple", "dietary_restrictions": "vegan"
        })
        assert "✅" in result


class TestAuthHelpers:
    def test_normalize_email(self):
        from auth import normalize_email
        assert normalize_email("  User@Example.COM  ") == "user@example.com"

    def test_password_strength_too_short(self):
        from auth import validate_password_strength
        with pytest.raises(ValueError):
            validate_password_strength("short")

    def test_password_strength_no_digit(self):
        from auth import validate_password_strength
        with pytest.raises(ValueError):
            validate_password_strength("onlyletters")

    def test_password_strength_valid(self):
        from auth import validate_password_strength
        validate_password_strength("Valid1password")  # should not raise
