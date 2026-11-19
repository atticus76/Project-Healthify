from unittest.mock import patch

import pytest
import reflex as rx

from backend.nutrition import dish_portions
from healthify.state.auth import AuthState
from healthify.state.nutrition import NutritionState
from healthify.state.reports import ReportsState


def state(cls):
    root = rx.State(_reflex_internal_init=True)
    return root.get_substate(cls.get_full_name().split(".")[1:])


def test_profile_units_and_save():
    auth = state(AuthState)
    auth.username = "alice"
    auth.age, auth.gender, auth.activity_level = "30", "Female", "Active"
    auth.height_input, auth.weight_input = "182.88", "150"
    for unit, expected in [("feet", 6), ("inches", 72), ("meters", 1.8288)]:
        AuthState.set_height_unit.fn(auth, unit)
        assert float(auth.height_input) == pytest.approx(expected)
    AuthState.set_weight_unit.fn(auth, "kg")
    assert float(auth.weight_input) == pytest.approx(68.0388555)
    with patch("healthify.state.auth.profile_controller.save_profile",
               return_value={"calorie_target": 2200, "estimated_daily_calories": 2000,
                             "baseline_weight_lb": 150}) as save,          patch("healthify.state.auth.auth_controller.get_user"),          patch("healthify.state.auth.auth_controller.update_user"):
        AuthState.save_profile.fn(auth)
    assert save.call_args.args[3:5] == pytest.approx((150, 182.88))


def test_usda_portions_and_single_submission():
    rates = dish_portions({"foodNutrients": [{"nutrient": {"id": 1008, "unitName": "kcal"}, "amount": 80}],
                           "foodPortions": [{"amount": 1, "modifier": "cup", "gramWeight": 150}]})
    assert rates == {"g": 0.8, "1 cup (150 g)": 120}
    ui = state(NutritionState)
    ui.username, ui.mode = "alice", "dish"
    ui.results = [{"id": "123", "name": "Example food"}]
    with patch("healthify.state.nutrition.nutrition.food", return_value=rates):
        NutritionState.select_item.fn(ui, "123")
    NutritionState.set_serving.fn(ui, "1 cup (150 g)")
    NutritionState.set_quantity.fn(ui, "1.5")
    with patch("healthify.state.nutrition.calories.add_food") as add:
        NutritionState.add_dish.fn(ui)
        NutritionState.add_dish.fn(ui)
    add.assert_called_once_with("alice", 180)


def test_branded_liquid_label_portion():
    assert dish_portions({"servingSize": 250, "servingSizeUnit": "ml",
                          "labelNutrients": {"calories": {"value": 110}}}) == {
                              "Serving (250 mL)": 110, "mL": 0.44}


def test_print_and_download_regenerate_snapshot():
    ui = state(ReportsState)
    ui.username = "alice"
    stamp = "2026-11-19T13:00:00+00:00"
    report = {"period_start": stamp, "period_end": stamp, "generated_at": stamp,
              "delivery_status": "", "delivery_error": "",
              "content": {"goals": [], "alerts": [], "metrics": {"available": False, "message": ""},
                          "calories": {"target": 2200, "burned": 50, "consumed": 180}}}
    with patch("healthify.state.reports.reports_backend.generate_report", return_value=report) as fresh:
        ReportsState.print_report.fn(ui)
        assert "Consumed: 180 kcal" in ui.report_text
        report["content"]["calories"]["consumed"] = 350
        ReportsState.export_report.fn(ui)
        assert "Consumed: 350 kcal" in ui.report_text
        assert fresh.call_count == 2

def test_suggestion_ranking_respects_budget_and_food_group():
    from backend import nutrition
    cards = [{"slug": str(k), "name": str(k), "calories": k, "rating": {"value": 4},
              "food_groups": ["grains"] if k == 480 else []}
             for k in [100, 300, 400, 450, 480, 490, 500, 510, 520, 530, 540, 800]]
    with patch.object(nutrition, "_get", return_value={"results": cards, "total": len(cards)}):
        results, _ = nutrition.suggested_recipes(700, "grains")
    assert len(results) == 10 and results[0]["id"] == "480"
    assert "800" not in [r["id"] for r in results]


def test_carousel_wrap_and_recommendation_refresh():
    ui = state(NutritionState)
    ui.username = "alice"
    cards = [{"id": str(i), "name": str(i), "image": "", "kcal": "400"} for i in range(10)]
    budget = {"target": 2000, "eaten": 1300, "last_meal": 1}
    with patch("healthify.state.nutrition.calories.daily_budget", return_value=budget),          patch("healthify.state.nutrition.nutrition.suggested_recipes", return_value=(cards, 10)) as lookup:
        ui._update_suggestions()
        NutritionState.move_slide.fn(ui, -1)
        assert ui.slide == 9
        NutritionState.move_slide.fn(ui, 1)
        assert ui.slide == 0
        budget["target"] += 199
        ui._update_suggestions()
        assert lookup.call_count == 1
        budget["target"] += 1
        ui._update_suggestions()
        budget["last_meal"] += 1
        ui._update_suggestions()
        ui._day = "yesterday"
        ui._update_suggestions()
        assert lookup.call_count == 4


def test_recipe_search_pages_keep_images_filters_and_partial_last_batch():
    from backend import nutrition

    catalog = [{"slug": str(i), "name": f"Recipe {i}", "calories": 100 if i % 2 else 250,
                "image_url": f"https://example.org/{i}.jpg"} for i in range(38)]

    def page(url, *, limit, offset, **filters):
        assert filters == {"q": "rice", "max_calories": 300}
        return {"total": len(catalog), "results": catalog[offset:offset + limit]}

    with patch.object(nutrition, "_get", side_effect=page):
        form = {"query": "rice", "min_calories": "200", "max_calories": "300"}
        first, offset = nutrition.recipe_search(form)
        second, offset = nutrition.recipe_search(form, offset)
        last, offset = nutrition.recipe_search(form, offset)
    assert [len(first), len(second), len(last)] == [8, 8, 3]
    assert offset is None
    assert [c["id"] for c in first + second + last] == [str(i) for i in range(0, 38, 2)]
    assert first[0]["image"] == catalog[0]["image_url"]


def test_dish_search_pages_keep_usda_filter_and_stop_at_last_food():
    from backend import nutrition

    def page(url, **params):
        assert url == nutrition.USDA + "/foods/search"
        assert params["query"] == "chicken" and params["dataType"] == "Branded"
        assert params["pageSize"] == 8
        start = (params["pageNumber"] - 1) * 8
        return {"totalHits": 10, "foods": [{"fdcId": i, "description": f"Dish {i}"}
                                            for i in range(start, min(start + 8, 10))]}

    ui = state(NutritionState)
    NutritionState.open_dialog.fn(ui, "dish")
    with patch.object(nutrition, "_get", side_effect=page) as fetch:
        NutritionState.search.fn(ui, {"query": "chicken", "data_type": "Branded"})
        assert len(ui.results) == 8
        generation, offset = ui.search_generation, ui.search_offset
        NutritionState.load_more.fn(ui, generation, offset)
        NutritionState.load_more.fn(ui, generation, offset)
        assert fetch.call_count == 2
    assert [item["id"] for item in ui.results] == list(map(str, range(10)))
    assert ui.search_offset == -1
