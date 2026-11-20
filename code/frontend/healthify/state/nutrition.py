import math
import random
import time
from datetime import datetime
from zoneinfo import ZoneInfo
import reflex as rx

from backend import calories, nutrition
from .session import SessionState
from .telemetry import TelemetryState


class NutritionState(SessionState):
    mode: str = ""
    results: list[dict[str, str]] = []
    search_offset: int = -1
    search_generation: int = 0
    _filters: dict = {}
    selected: str = ""
    error: str = ""
    portions: list[str] = []
    _rates: dict[str, float] = {}
    serving: str = ""
    quantity: str = "1"
    ingredients: list[str] = []
    nutrients: list[str] = []
    directions: str = ""
    servings: str = ""

    suggestions: list[dict[str, str]] = []
    slide: int = 0
    suggestion_note: str = ""
    preferred_group: str = "Any"
    _budget_user: str = ""
    _day: str = ""
    _remaining: int = 0
    _last_meal: int = 0
    _candidate_count: int = 0
    _next_check: float = 0
    _next_slide: float = 0

    def _update_suggestions(self, force=False):
        if not self.username:
            return
        if self._budget_user != self.username:
            self.suggestions = []
            self.preferred_group = "Any"
            self._candidate_count = 0
            self._day = ""
            self._budget_user = self.username
        now = datetime.now(ZoneInfo(self.meal_timezone)) if self.meal_timezone else datetime.now().astimezone()
        day = now.date().isoformat()
        budget = calories.daily_budget(self.username, now.replace(hour=0,minute=0,second=0,microsecond=0)) or {}
        target = budget.get("target") or 0
        remaining = target - int(budget.get("eaten") or 0)
        meal = budget.get("last_meal") or 0
        if (not force and day == self._day and meal == self._last_meal
                and abs(remaining - self._remaining) < 200 and (remaining > 0) == (self._remaining > 0)):
            return
        if remaining <= 0 or not target:
            self.suggestions = []
            self.suggestion_note = ("Complete Health Profile for personalized suggestions." if not target
                                    else "Daily target reached. You can still search all recipes.")
        else:
            offset = random.randint(0, max(0, self._candidate_count - 100)) if force else 0
            try:
                self.suggestions, self._candidate_count = nutrition.suggested_recipes(
                    remaining, self.preferred_group, offset)
            except (KeyError, TypeError, ValueError):
                self.suggestion_note = "MyPlate is unavailable. Refresh to try again."
                self._next_check = time.monotonic() + 60
                return
            self.suggestion_note = "" if self.suggestions else "No recipes found in the remaining calorie range."
        self._day, self._remaining, self._last_meal = day, remaining, meal
        self.slide = 0
        self._next_slide = time.monotonic() + 10

    def refresh_suggestions(self):
        self._update_suggestions(force=True)

    def set_preferred_group(self, value: str):
        self.preferred_group = value
        self.refresh_suggestions()

    def cycle_suggestions(self):
        now = time.monotonic()
        if now >= self._next_check or self._budget_user != self.username:
            self._next_check = now + 15
            self._update_suggestions()
        if self.suggestions and now >= self._next_slide and not self.mode:
            self.move_slide(1)

    def move_slide(self, delta: int):
        if self.suggestions:
            self.slide = (self.slide + delta) % len(self.suggestions)
            self._next_slide = time.monotonic() + 10

    def show_suggested(self, key: str):
        self.open_dialog("detail")
        self.results = [item for item in self.suggestions if item["id"] == key]
        self.select_item(key)

    def open_dialog(self, mode: str):
        self.search_offset = -1
        self.mode = mode
        self.results = []
        self.selected = self.error = ""
        self._rates = {}

    def close_dialog(self, opened: bool):
        if not opened:
            self.mode = ""

    def search(self, form: dict):
        self.selected = self.error = ""
        self.results = []
        self._rates = {}
        self.search_offset = -1
        self.search_generation += 1
        query = str(form.get("query", "")).strip()
        if not query and self.mode != "recipes":
            self.error = "Enter a food or dish name."
            return
        try:
            self._filters = dict(form)
            self.results, offset = self._search_page(0)
            self.search_offset = -1 if offset is None else offset
            if not self.results:
                self.error = "No matches. Try another food or ingredient."
        except (ValueError, KeyError, TypeError) as exc:
            self.error = str(exc) if isinstance(exc, ValueError) else "Search results unavailable."

    def _search_page(self, offset):
        search = nutrition.recipe_search if self.mode == "recipes" else nutrition.dish_search
        return search(self._filters, offset)

    def load_more(self, generation: int, offset: int):
        if (self.mode not in ("dish", "recipes") or generation != self.search_generation
                or offset != self.search_offset or offset < 0):
            return
        try:
            cards, next_offset = self._search_page(offset)
        except (ValueError, KeyError, TypeError):
            self.error = "Could not load more results. Try again."
            return
        self.error = ""
        self.results.extend(cards)
        self.search_offset = -1 if next_offset is None else next_offset

    def back_to_results(self):
        self.selected = ""

    def select_item(self, key: str):
        item = next((r for r in self.results if r["id"] == key), None)
        if not item:
            return
        self.selected = self.error = ""
        self._rates = {}
        try:
            if self.mode in ("detail", "recipes"):
                data = nutrition.recipe(key)
                self.ingredients = [i["text"] + (f" ({i['note']})" if i.get("note") else "")
                                    for i in data["ingredients"]]
                self.directions = data.get("directions") or ""
                self.servings = " · ".join(filter(None, [data.get("yield"), data.get("serving_size")]))
                self.nutrients = [f"{n['name']}: {n['amount']:g} {n.get('unit') or ('kcal' if n['key']=='total_calories' else '')}".strip()
                                  for n in data["nutrition"] if isinstance(n.get("amount"), (float,int))]
            else:
                self._rates = nutrition.food(key)
                self.portions = list(self._rates)
                if not self.portions:
                    self.error = "USDA has no calorie amount for this food. Choose another result."
                    return
                self.serving = self.portions[0]
                self.quantity = "100" if self.serving in ("g", "mL") else "1"
            self.selected = item["name"]
        except (ValueError, KeyError, TypeError) as exc:
            self.error = str(exc) if isinstance(exc, ValueError) else "Food details unavailable."

    def set_quantity(self, value: str):
        self.quantity = value

    def set_serving(self, value: str):
        if value in self._rates:
            self.serving = value
            self.quantity = "100" if value in ("g", "mL") else "1"

    @rx.var
    def portion_kcal(self) -> int:
        try:
            quantity = float(self.quantity)
            total = quantity * self._rates[self.serving]
            if quantity > 0 and math.isfinite(total) and total <= 10000:
                return round(total)
        except (ValueError, KeyError):
            pass
        return -1

    def add_dish(self):
        if self.mode != "dish" or not self.selected or not self.username:
            return
        amount = self.portion_kcal
        if amount < 0:
            self.error = "Enter a positive quantity up to 10,000 kcal."
            return
        calories.add_food(self.username, amount)
        self.mode = self.selected = ""
        return [TelemetryState.load_calories, NutritionState.refresh_suggestions, rx.toast(f"Added {amount} kcal.")]
