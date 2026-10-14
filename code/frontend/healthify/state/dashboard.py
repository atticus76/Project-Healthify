class DashboardState(rx.State):
    sort_a_to_z: bool = False

    def toggle_sort(self):
        self.sort_a_to_z = not self.sort_a_to_z