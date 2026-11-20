import reflex as rx
from backend.nutrition import USDA_TYPES
from ..state.nutrition import NutritionState as State


def _dish():
    return rx.vstack(
        rx.heading(State.selected, size="4"),
        rx.text("Quantity and portion"),
        rx.hstack(rx.input(type="number", min="0", step="any", value=State.quantity,
                           on_change=State.set_quantity, aria_label="Quantity", width="6em"),
                  rx.select(State.portions, value=State.serving, on_change=State.set_serving,
                            aria_label="Portion unit")),
        rx.cond(State.portion_kcal >= 0, rx.text(State.portion_kcal, " kcal")),
        rx.button("Add to consumed calories", on_click=State.add_dish, disabled=State.portion_kcal < 0),
        align="stretch",
    )


def _recipe():
    return rx.vstack(
        rx.heading(State.selected, size="4"), rx.text(State.servings),
        rx.heading("Ingredients", size="3"), rx.foreach(State.ingredients, lambda item: rx.text(item)),
        rx.heading("Directions", size="3"), rx.text(State.directions, white_space="pre-line"),
        rx.heading("Nutrition per serving", size="3"), rx.foreach(State.nutrients, lambda item: rx.text(item)),
        align="stretch",
    )


GROUPS = ["Any", "fruits", "vegetables", "grains", "protein-foods", "dairy"]


def _search_form(recipes):
    fields = [rx.input(name="query", placeholder="Food or ingredient", required=not recipes,
                       aria_label="Food search", width="100%")]
    if recipes:
        fields.extend([
            rx.input(name="ingredients", placeholder="Ingredients, separated by commas", aria_label="Ingredients"),
            rx.grid(rx.input(name="min_calories", type="number", min="0", placeholder="Min kcal", aria_label="Minimum kcal"),
                    rx.input(name="max_calories", type="number", min="0", placeholder="Max kcal", aria_label="Maximum kcal"),
                    columns="2", gap="2"),
            rx.text("Food group", size="2"),
            rx.select(GROUPS, name="food_group", default_value="Any", aria_label="Food group"),
            rx.input(name="category", placeholder="Category, e.g. Soup", aria_label="Recipe category"),
            rx.input(name="min_rating", type="number", min="0", max="5", step="0.1",
                     placeholder="Minimum rating (0 to 5)", aria_label="Minimum rating"),
        ])
    else:
        fields.extend([
            rx.text("USDA food type", size="2"),
            rx.select(["Any", *USDA_TYPES], name="data_type", default_value="Any",
                      aria_label="USDA food type"),
        ])
    return rx.form(rx.vstack(*fields, rx.button("Search", type="submit", color_scheme="green"),
                             align="stretch"), on_submit=State.search, width="100%")


def food_dialog(recipes=False):
    mode = "recipes" if recipes else "dish"
    label = "Search Recipe" if recipes else "Add Calories by Dish"
    return rx.dialog.root(
        rx.dialog.trigger(rx.button(label, size="2", color_scheme="green", on_click=State.open_dialog(mode))),
        rx.dialog.content(
            rx.dialog.title(label),
            rx.dialog.description("Search MyPlate by dish or ingredient." if recipes else
                                  "Search USDA FoodData Central, then choose your portion."),
            rx.vstack(
                rx.box(_search_form(recipes), display=rx.cond(State.selected == "", "block", "none")),
                rx.cond(State.error != "", rx.text(State.error, color_scheme="red")),
                rx.box(_search_results(mode), display=rx.cond(State.selected == "", "block", "none")),
                rx.cond(State.selected != "",
                        rx.vstack(rx.button("Back to results", variant="ghost", on_click=State.back_to_results),
                                  _recipe() if recipes else _dish(), align="stretch")),
                rx.dialog.close(rx.button("Close", variant="outline", align_self="end")),
                align="stretch", margin_top="1em",
            ),
            max_width="36rem", width="min(36rem, 92vw)", max_height="85vh", overflow_y="auto",
        ),
        open=State.mode == mode, on_open_change=State.close_dialog,
    )


def _recipe_tile(item, carousel=False):
    return rx.button(
        rx.cond(item["image"] != "",
                rx.image(src=item["image"], alt="", position="absolute", inset="0",
                         width="100%", height="100%", object_fit="cover"),
                rx.icon("utensils", size=32, color="white", aria_hidden=True)),
        rx.box(rx.text(item["name"], weight="bold", white_space="normal"),
               *([rx.text(item["kcal"], " kcal per serving", size="1")] if carousel else []),
               position="absolute", bottom="0", left="0", right="0", padding="0.6em",
               background="rgba(0,0,0,0.72)", color="white", text_align="left"),
        on_click=State.show_suggested(item["id"]) if carousel else State.select_item(item["id"]),
        aria_label=item["name"],
        position="relative", flex="0 0 100%", height="100%" if carousel else "auto",
        aspect_ratio="1", width="100%", min_width="0", overflow="hidden", padding="0",
        background_color="#276749",
    )


def _dish_tile(item):
    return rx.button(
        item["name"], on_click=State.select_item(item["id"]),
        width="100%", height="auto", min_width="0", aspect_ratio="1",
        padding="0.75em", white_space="normal", text_align="center",
        overflow_wrap="anywhere", align_items="center", justify_content="center",
        background_color=rx.color_mode_cond("#2f855a", "#276749"), color="white",
        _hover={"background_color": rx.color_mode_cond("#276749", "#22543d")},
    )


def _search_results(mode):
    # Keep scroll detection in the browser. Send a single event when a page ends.
    register_scroll = """
        const grid = document.getElementById('SEARCH_GRID');
        if (grid) grid.onscroll = () => {
            const more = grid.querySelector('[data-next-page]');
            if (more && !more.dataset.requested &&
                grid.scrollTop + grid.clientHeight >= grid.scrollHeight - 32) {
                more.dataset.requested = 'yes';
                more.click();
            }
        };
    """
    grid_id = f"{mode}-results"
    return rx.box(
        rx.grid(rx.foreach(State.results, _dish_tile if mode == "dish" else lambda item: _recipe_tile(item)),
                columns="2", gap="2", width="100%"),
        rx.cond(State.search_offset >= 0,
                rx.button("Load more recipes" if mode == "recipes" else "Load more dishes", variant="ghost", width="100%",
                          custom_attrs={"data-next-page": "true"}, key=State.search_offset.to_string(),
                          on_click=State.load_more(State.search_generation, State.search_offset))),
        id=grid_id, key=State.search_generation.to_string(),
        on_mount=rx.call_script(register_scroll.replace("SEARCH_GRID", grid_id)), max_height="52vh", overflow_y="auto",
    )


def _suggestion_info():
    cloud_id = "suggested-recipes-info"
    return rx.box(
        rx.icon_button(
            rx.icon("info", size=15), id="suggested-recipes-info-button",
            aria_label="How suggested recipes are selected", aria_describedby=cloud_id,
            size="1", variant="ghost", color_scheme="green",
            on_click=rx.call_script("document.getElementById('suggested-recipes-info-button')?.focus()"),
        ),
        rx.box(
            "Personalized Suggested Recipes are selected based on your daily calorie target minus "
            "the calories you logged today. Each serving fits within what remains. For example, with "
            "700 kcal left, recipes from 300 to 700 kcal come first. Within each range, we favor your "
            "preferred food group, then servings closest to the midpoint of the preferred range. "
            "Higher ratings break ties. Up to 10 recipes are shown.",
            id=cloud_id, role="tooltip", position="absolute", bottom="100%", right="-2rem",
            width="min(17rem, 80vw)", padding="0.75em", border_radius="8px", z_index="5",
            font_size="0.8rem", line_height="1.4", background_color=rx.color("gray", 12),
            color=rx.color("gray", 1), box_shadow="0 3px 12px #0003",
        ),
        position="relative",
        style={f"& > #{cloud_id}": {"visibility": "hidden"},
               f"&:hover > #{cloud_id}, &:focus-within > #{cloud_id}": {"visibility": "visible"}},
    )


def suggested_meals():
    return rx.vstack(
        rx.hstack(rx.heading("Suggested Recipes", size="3"),
                  _suggestion_info(),
                  rx.icon_button(rx.icon("refresh-cw", size=14), size="1", variant="ghost",
                                 color_scheme="green", aria_label="Refresh suggested recipes",
                                 on_click=State.refresh_suggestions), align="center"),
        rx.text("Preferred food group", size="1"),
        rx.select(GROUPS, value=State.preferred_group, on_change=State.set_preferred_group,
                  aria_label="Preferred food group", size="1"),
        rx.cond(State.suggestion_note != "", rx.text(State.suggestion_note, size="2")),
        rx.cond(State.suggestions.length() > 0,
                rx.vstack(
                    rx.box(rx.flex(rx.foreach(State.suggestions, lambda item: _recipe_tile(item, carousel=True)),
                                   transform="translateX(-" + (State.slide * 100).to_string() + "%)",
                                   transition="transform 350ms ease", width="100%", height="100%"),
                           width="100%", aspect_ratio="1", border_radius="8px", overflow="hidden"),
                    rx.hstack(rx.icon_button(rx.icon("chevron-left"), on_click=State.move_slide(-1),
                                             size="1", color_scheme="green", aria_label="Previous recipe"),
                              rx.text(State.slide + 1, " / ", State.suggestions.length(), size="1"),
                              rx.icon_button(rx.icon("chevron-right"), on_click=State.move_slide(1),
                                             size="1", color_scheme="green", aria_label="Next recipe"),
                              justify="between", align="center"), align="stretch")),
        rx.dialog.root(rx.dialog.content(rx.dialog.title("Recipe details"),
                                         rx.cond(State.error != "", rx.text(State.error), _recipe()),
                                         rx.dialog.close(rx.button("Close", variant="outline")),
                                         max_width="36rem", max_height="85vh", overflow_y="auto"),
                       open=State.mode == "detail", on_open_change=State.close_dialog),
        align="stretch", width="100%",
    )
