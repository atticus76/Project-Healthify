import reflex as rx

from ..state.auth import AuthState, HEIGHT_UNITS, WEIGHT_UNITS


def measurement_fields():
    def field(label, value, setter, units, unit, change):
        return rx.vstack(
            rx.text(label, weight="bold"),
            rx.hstack(rx.input(type="number", step="any", min="0", value=value, on_change=setter,
                               aria_label=label, width="100%"),
                      rx.select(list(units), value=unit, on_change=change,
                                aria_label=f"{label} unit"), width="100%"),
            width="100%",
        )
    return rx.vstack(
        field("Height", AuthState.height_input, AuthState.set_height_input, HEIGHT_UNITS,
              AuthState.height_unit, AuthState.set_height_unit),
        field("Weight", AuthState.weight_input, AuthState.set_weight_input, WEIGHT_UNITS,
              AuthState.weight_unit, AuthState.set_weight_unit),
        width="100%",
    )
