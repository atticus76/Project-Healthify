"""On-demand nutrition searches. API credentials stay on the server."""
import math
import os
from urllib.parse import quote

import requests

USDA = "https://api.nal.usda.gov/fdc/v1"
RECIPES = "https://myplate.food/api/v1/recipes"


def _get(url, **params):
    if url.startswith(USDA):
        params["api_key"] = os.getenv("USDA_API_KEY") or "DEMO_KEY"
    try:
        response = requests.get(url, params=params, timeout=8)
        if response.status_code == 429:
            raise ValueError("Search limit reached. Try again later.")
        response.raise_for_status()
        return response.json()
    except requests.RequestException:
        raise ValueError("The food service is unavailable. Try again shortly.") from None


SEARCH_PAGE_SIZE = 8
USDA_TYPES = ["Foundation", "Survey (FNDDS)", "SR Legacy", "Branded"]


def dish_search(form, offset=0):
    params = {"query": form["query"].strip(), "pageSize": SEARCH_PAGE_SIZE,
              "pageNumber": offset // SEARCH_PAGE_SIZE + 1}
    if form.get("data_type") in USDA_TYPES:
        params["dataType"] = form["data_type"]
    page = _get(f"{USDA}/foods/search", **params)
    cards = []
    for item in page["foods"]:
        brand = item.get("brandOwner") or item.get("brandName")
        name = " - ".join(filter(None, [item["description"], brand]))
        cards.append({"id": str(item["fdcId"]), "name": name, "image": item.get("imageUrl") or ""})
    more = params["pageNumber"] * SEARCH_PAGE_SIZE < page["totalHits"]
    return cards, offset + SEARCH_PAGE_SIZE if cards and more else None


def recipe(slug):
    return _get(f"{RECIPES}/{quote(slug, safe='')}")


def dish_portions(food):
    """Return selectable portion labels and kcal per unit from the USDA detail record."""
    energy = {entry["nutrient"]["id"]: entry["amount"] for entry in food.get("foodNutrients", [])
              if entry.get("nutrient", {}).get("unitName", "").lower() == "kcal"
              and entry.get("amount") is not None}
    kcal = next((energy[key] for key in (1008, 2048, 2047) if key in energy), None)
    liquid = str(food.get("servingSizeUnit", "")).lower() == "ml"
    unit = "mL" if liquid else "g"
    portions = {}
    size = food.get("servingSize") or 0
    label_kcal = food.get("labelNutrients", {}).get("calories", {}).get("value")
    if size > 0 and (label_kcal is not None or kcal is not None):
        portions[f"Serving ({size:g} {unit})"] = label_kcal if label_kcal is not None else size*kcal/100
    if kcal is None and label_kcal is not None and size > 0:
        kcal = 100 * label_kcal / size
    if kcal is not None:
        portions[unit] = kcal / 100
        for item in food.get("foodPortions", []):
            grams = item.get("gramWeight") or 0
            if grams <= 0 or liquid:
                continue
            name = (item.get("portionDescription") or item.get("modifier")
                    or item.get("measureUnit", {}).get("name") or "portion")
            portions[f"{item.get('amount') or 1:g} {name} ({grams:g} g)"] = grams*kcal/100
    return {label: value for label, value in portions.items() if math.isfinite(value) and value >= 0}


def food(fdc_id):
    return dish_portions(_get(f"{USDA}/food/{int(fdc_id)}"))


def recipe_search(form, offset=0):
    params = {k: str(form[k]).strip() for k in ("ingredients", "category", "food_group", "min_rating")
              if form.get(k) and form[k] != "Any"}
    if form.get("query"):
        params["q"] = str(form["query"]).strip()
    low = float(form.get("min_calories") or 0)
    high = float(form.get("max_calories") or math.inf)
    if not 0 <= low <= high:
        raise ValueError("Enter a calorie range with the minimum at or below the maximum.")
    if high != math.inf:
        params["max_calories"] = high
    matches = []
    while len(matches) < SEARCH_PAGE_SIZE:
        page = _get(RECIPES, **params, limit=100 if low else SEARCH_PAGE_SIZE, offset=offset)
        cards = page["results"]
        for row in cards:
            offset += 1
            if (row.get("calories") or 0) >= low:
                matches.append({"id": row["slug"], "name": row["name"],
                                "image": row.get("image_url") or ""})
            if len(matches) == SEARCH_PAGE_SIZE:
                break
        if not cards or offset >= page["total"]:
            return matches, None
    return matches, offset


def suggested_recipes(remaining, preferred_group, offset=0):
    page = _get(RECIPES, max_calories=remaining, limit=100, offset=offset)
    if offset and len(page["results"]) < min(10, page["total"]):
        page = _get(RECIPES, max_calories=remaining, limit=100)
    lower = min(300, remaining * 0.45)
    ideal = (lower + remaining) / 2
    cards = [r for r in page["results"] if isinstance(r.get("calories"), (float, int))
             and 0 < r["calories"] <= remaining]

    def rank(r):
        return (r["calories"] < lower, preferred_group not in (r.get("food_groups") or []),
                abs(r["calories"] - ideal), -((r.get("rating") or {}).get("value") or 0))

    return [{"id": r["slug"], "name": r["name"], "image": r.get("image_url") or "",
             "kcal": str(r["calories"])} for r in sorted(cards, key=rank)[:10]], page["total"]
