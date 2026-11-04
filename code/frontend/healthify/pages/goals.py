import reflex as rx

from ..components import page_header
from ..state.goals import GoalsState
from ..state.auth import AuthState
from ..state.telemetry import TelemetryState


def _goal_row(goal: dict[str, str]) -> rx.Component:
    return rx.table.row(
        rx.table.cell(
            rx.vstack(
                rx.text(goal["label"], weight="bold"),
                rx.text(
                    goal["reminders"],
                    " · Deadline ",
                    goal["deadline"],
                    size="2",
                    color_scheme="gray",
                ),
                align="start",
                spacing="1",
            ),
            style={"width": "24%", "vertical_align": "top"},
        ),
        rx.table.cell(
            rx.text(goal["steps"], " / ", goal["target"], " steps"),
            style={"width": "14%", "vertical_align": "top"},
        ),
        rx.table.cell(
            rx.vstack(
                rx.progress(value=goal["percent"].to(int), max=100, width="150px"),
                rx.text(goal["percent"], "% · ", goal["status"], size="2"),
                align="start",
                spacing="1",
            ),
            style={"width": "20%", "vertical_align": "top"},
        ),
        rx.table.cell(
            rx.hstack(
                rx.input(
                    type="number",
                    min="0",
                    placeholder=                    "Add steps",
                    on_change=GoalsState.set_today_steps_input,
                    width="130px",
                ),
                rx.button("Update", on_click=GoalsState.record_steps(goal["id"]), size="2",
                          disabled=goal["status"] != "In Progress"),
                rx.button("End day", on_click=GoalsState.end_goal(goal["id"]), size="2",
                          variant="outline", disabled=goal["status"] != "In Progress"),
                rx.button("Delete", on_click=GoalsState.delete_goal(goal["id"]), size="2",
                          color_scheme="red", variant="ghost"),
                wrap="wrap",
                spacing="2",
            ),
            style={"width": "42%", "vertical_align": "top"},
        ),
        style={"opacity": rx.cond(goal["status"] == "In Progress", "1", "0.55")},
    )


def _goal_dialog() -> rx.Component:
    return rx.dialog.root(
        rx.dialog.trigger(
            rx.button(
                rx.icon("plus", size=18),
                " Add a goal",
                on_click=GoalsState.open_goal_dialog,
            ),
        ),
        rx.dialog.content(
            rx.dialog.title("Add a goal"),
            rx.dialog.description(
                "Choose a measurable target and decide whether to receive progress reminders."
            ),
            rx.vstack(
                rx.text("Goal type", weight="bold"),
                rx.select.root(
                    rx.select.trigger(width="100%"),
                    rx.select.content(
                        rx.select.item("Step Count", value="daily_steps"),
                    ),
                    value=GoalsState.goal_type,
                    on_change=GoalsState.set_goal_type,
                ),
                rx.text("Target", weight="bold"),
                rx.input(
                    type="number",
                    min="1",
                    max="1000000",
                    value=GoalsState.target_input,
                    on_change=GoalsState.set_target_input,
                    placeholder="e.g. 10000",
                    width="100%",
                ),
                rx.checkbox(
                    "Enable completion reminder (100%)",
                    checked=GoalsState.reminders_enabled,
                    on_change=GoalsState.set_reminders_enabled,
                ),
                rx.text("Milestone reminders", weight="bold"),
                rx.checkbox(
                    "Notify at 25%",
                    checked=GoalsState.reminder_25_enabled,
                    on_change=GoalsState.set_reminder_25_enabled,
                ),
                rx.checkbox(
                    "Notify at 50%",
                    checked=GoalsState.reminder_50_enabled,
                    on_change=GoalsState.set_reminder_50_enabled,
                ),
                rx.checkbox(
                    "Notify at 75%",
                    checked=GoalsState.reminder_75_enabled,
                    on_change=GoalsState.set_reminder_75_enabled,
                ),
                rx.checkbox(
                    "This is a daily goal",
                    checked=GoalsState.is_daily,
                    on_change=GoalsState.set_is_daily,
                ),
                rx.cond(
                    GoalsState.is_daily,
                    rx.text(
                        "Daily goals restart with the same target at the next midnight.",
                        size="2",
                        color_scheme="gray",
                    ),
                    rx.vstack(
                        rx.text("One-time goal deadline", weight="bold"),
                        rx.select.root(
                            rx.select.trigger(width="100%"),
                            rx.select.content(
                                rx.select.item("Choose a deadline", value="deadline"),
                                rx.select.item("Use a duration", value="duration"),
                            ),
                            value=GoalsState.deadline_mode,
                            on_change=GoalsState.set_deadline_mode,
                        ),
                        rx.cond(
                            GoalsState.deadline_mode == "deadline",
                            rx.input(
                                type="datetime-local",
                                value=GoalsState.deadline_input,
                                on_change=GoalsState.set_deadline_input,
                                width="100%",
                            ),
                            rx.hstack(
                                rx.input(
                                    type="number",
                                    min="1",
                                    value=GoalsState.duration_input,
                                    on_change=GoalsState.set_duration_input,
                                    width="100%",
                                ),
                                rx.select.root(
                                    rx.select.trigger(width="140px"),
                                    rx.select.content(
                                        rx.select.item("Hours", value="hours"),
                                        rx.select.item("Days", value="days"),
                                    ),
                                    value=GoalsState.duration_unit,
                                    on_change=GoalsState.set_duration_unit,
                                ),
                                width="100%",
                            ),
                        ),
                        align="stretch",
                        spacing="2",
                    ),
                ),
                rx.cond(
                    GoalsState.goal_error != "",
                    rx.text(GoalsState.goal_error, color_scheme="red", size="2"),
                ),
                rx.hstack(
                    rx.dialog.close(
                        rx.button("Cancel", variant="outline"),
                    ),
                    rx.button("Add goal", on_click=GoalsState.add_goal),
                    justify="end",
                    width="100%",
                ),
                align="stretch",
                spacing="3",
            ),
            max_width="420px",
        ),
        open=GoalsState.goal_dialog_open,
        on_open_change=GoalsState.set_goal_dialog_open,
    )


def _email_settings() -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.heading("Shared email notifications", size="5"),
            rx.text(
                "The same address receives health alerts and goal milestone emails. "
                "You can change it here or on the Alerts page.",
                size="2",
                color_scheme="gray",
            ),
            rx.cond(
                ~GoalsState.email_configured,
                rx.callout(
                    "Email sending requires SMTP_USERNAME and SMTP_PASSWORD in .env. "
                    "Restart the app after changing .env.",
                    icon="triangle_alert",
                    color_scheme="orange",
                    size="1",
                ),
            ),
            rx.hstack(
                rx.input(
                    placeholder="you@example.com",
                    type="email",
                    value=GoalsState.email_input,
                    on_change=GoalsState.set_email_input,
                    flex="1",
                    min_width="220px",
                ),
                rx.button("Save address", on_click=GoalsState.save_email),
                rx.button(
                    "Send test email",
                    on_click=GoalsState.send_test_email,
                    loading=GoalsState.sending_test_email,
                    disabled=(GoalsState.alert_email == "") | ~GoalsState.email_configured,
                    variant="outline",
                ),
                rx.cond(
                    GoalsState.alert_email != "",
                    rx.button(
                        "Turn off",
                        on_click=GoalsState.turn_off_email,
                        variant="ghost",
                        color_scheme="gray",
                    ),
                ),
                wrap="wrap",
                spacing="2",
                width="100%",
            ),
            rx.cond(
                GoalsState.email_error != "",
                rx.text(GoalsState.email_error, color_scheme="red", size="2"),
            ),
            rx.cond(
                GoalsState.email_message != "",
                rx.text(GoalsState.email_message, color_scheme="green", size="2"),
            ),
            align="stretch",
            spacing="3",
        ),
        width="100%",
        padding="1em",
        border_radius="10px",
        border=rx.color_mode_cond("1px solid #e2e8f0", "1px solid #4a5568"),
    )


@rx.page(route="/goals", title="Goals | Healthify", on_load=[AuthState.require_login, GoalsState.load_page])
def goals_page() -> rx.Component:
    return rx.vstack(
        page_header(),
        rx.vstack(
            rx.heading("Goal Management", size="8"),
            rx.text("Track measurable improvements with goals and reminders."),
            rx.button(
                "Automatic refresh",
                id="goals-auto-refresh",
                on_click=[TelemetryState.auto_refresh, GoalsState.refresh_goals],
                opacity="0",
                position="absolute",
                width="1px",
                height="1px",
                pointer_events="none",
            ),
            rx.hstack(
                rx.heading("Your goals", size="5"),
                rx.spacer(),
                _goal_dialog(),
                width="100%",
                align="center",
            ),
            rx.cond(
                GoalsState.goals.length() > 0,
                rx.box(
                    rx.table.root(
                        rx.table.header(
                            rx.table.row(
                                rx.table.column_header_cell("Goal"),
                                rx.table.column_header_cell("Steps"),
                                rx.table.column_header_cell("Progress"),
                                rx.table.column_header_cell("Update"),
                            ),
                        ),
                        rx.table.body(
                            rx.foreach(GoalsState.goals, _goal_row),
                        ),
                        style={
                            "width": "100%",
                            "table_layout": "fixed",
                            "overflow_wrap": "anywhere",
                        },
                    ),
                    width="100%",
                    max_height="390px",
                    overflow_y="auto",
                    padding_right="0.35em",
                    border=rx.color_mode_cond("1px solid #e2e8f0", "1px solid #4a5568"),
                    border_radius="10px",
                ),
                rx.box(
                    rx.vstack(
                        rx.icon("target", size=32, color_scheme="gray"),
                        rx.text("No goals yet."),
                        rx.text(
                            "Use the plus button to add your first goal and reminder.",
                            size="2",
                            color_scheme="gray",
                        ),
                        align="center",
                        spacing="2",
                    ),
                    width="100%",
                    padding="2em",
                    border_radius="10px",
                    border="1px dashed #a0aec0",
                ),
            ),
            rx.cond(
                GoalsState.progress_error != "",
                rx.text(GoalsState.progress_error, color_scheme="red", size="2"),
            ),
            rx.cond(
                GoalsState.progress_message != "",
                rx.text(GoalsState.progress_message, color_scheme="green", size="2"),
            ),
            rx.cond(
                GoalsState.motivational_prompt != "",
                rx.callout(
                    GoalsState.motivational_prompt,
                    icon="heart",
                    color_scheme="blue",
                ),
            ),
            _email_settings(),
            rx.button("Back to Dashboard", on_click=rx.redirect("/"), variant="outline"),
            width="100%",
            max_width="960px",
            padding="2em",
            align="stretch",
            spacing="4",
        ),
        width="100%",
        min_height="100vh",
        align="center",
        background_color=rx.color_mode_cond("white", "#1a202c"),
        color=rx.color_mode_cond("#1a202c", "white"),
    )
