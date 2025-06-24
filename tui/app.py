import sys
import os
import asyncio

# Add parent directory to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, DataTable, TabbedContent, TabPane, LoadingIndicator
from textual.reactive import reactive
from core.docker_client import DockerClient


class DockManApp(App):
    """Textual-based TUI for managing Docker containers."""

    CSS = """
    DataTable {
        height: 100%;
        width: 100%;
    }
    TabPane {
        padding: 1;
    }
    .no-data {
        content-align: center middle;
        color: white;
    }
    LoadingIndicator {
        content-align: center middle;
        height: 100%;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("t", "switch_tab", "Switch Tab"),
    ]

    active_tab = reactive("containers")

    def __init__(self):
        super().__init__()
        self.docker_client = None
        self.tables = {}  # Cache tables for each tab
        self.is_loading = True

    async def on_mount(self) -> None:
        """Initialize the app after mounting."""
        # Show loading indicator
        self.query_one(TabbedContent).mount(LoadingIndicator())
        try:
            self.docker_client = DockerClient()
            self.notify("Connected to Docker successfully!", severity="information")
        except Exception as e:
            self.notify(f"Failed to connect to Docker: {e}", severity="error")

        # Initialize tab content
        await self.update_tab_content("containers")
        # Remove loading indicator
        for widget in self.query_one(TabbedContent).query(LoadingIndicator):
            widget.remove()
        self.is_loading = False
        # Start periodic update
        self.set_interval(5.0, self.update_active_tab)

    def compose(self) -> ComposeResult:
        """Create the UI layout."""
        yield Header(show_clock=True)
        with TabbedContent():
            yield TabPane("Containers", id="containers")
            yield TabPane("Images", id="images")
            yield TabPane("Volumes", id="volumes")
            yield TabPane("Networks", id="networks")
        yield Footer()

    async def update_active_tab(self) -> None:
        """Update content for the active tab."""
        await self.update_tab_content(self.active_tab)

    async def update_tab_content(self, tab_id: str) -> None:
        """Update content for a specific tab."""
        if self.is_loading:
            return

        if not self.docker_client:
            self.mount_error_table(tab_id, "Failed to connect to Docker")
            return

        try:
            if tab_id == "containers":
                await self.update_containers_tab()
            elif tab_id == "images":
                await self.update_images_tab()
            elif tab_id == "volumes":
                await self.update_volumes_tab()
            elif tab_id == "networks":
                await self.update_networks_tab()
        except Exception as e:
            self.mount_error_table(tab_id, f"Error: {e}")
            self.notify(f"Error updating {tab_id}: {e}", severity="error")

    async def update_containers_tab(self) -> None:
        """Update the Containers tab."""
        tab = self.query_one("#containers", TabPane)
        containers = self.docker_client.get_containers(all=True)

        if not containers:
            self.mount_error_table("containers", "No containers found")
            return

        if "containers" not in self.tables:
            tab.mount(DataTable())
            self.tables["containers"] = tab.query_one(DataTable)
            self.tables["containers"].add_columns("Name", "Status", "CPU %", "Memory MB", "Ports", "Created")

        table = self.tables["containers"]
        table.clear()
        for c in containers:
            table.add_row(
                c["name"],
                c["status"],
                str(c["cpu"]),
                str(c["memory"]),
                c["ports"],
                c["created"]
            )

    async def update_images_tab(self) -> None:
        """Update the Images tab."""
        tab = self.query_one("#images", TabPane)
        images = self.docker_client.get_images()

        if not images:
            self.mount_error_table("images", "No images found")
            return

        if "images" not in self.tables:
            tab.mount(DataTable())
            self.tables["images"] = tab.query_one(DataTable)
            self.tables["images"].add_columns("ID", "Tags", "Size MB", "Created")

        table = self.tables["images"]
        table.clear()
        for img in images:
            table.add_row(
                img["id"],
                ", ".join(img["tags"]),
                str(img["size"]),
                img["created"]
            )

    async def update_volumes_tab(self) -> None:
        """Update the Volumes tab."""
        tab = self.query_one("#volumes", TabPane)
        volumes = self.docker_client.get_volumes()

        if not volumes:
            self.mount_error_table("volumes", "No volumes found")
            return

        if "volumes" not in self.tables:
            tab.mount(DataTable())
            self.tables["volumes"] = tab.query_one(DataTable)
            self.tables["volumes"].add_columns("Name", "Driver", "Mountpoint", "Created")

        table = self.tables["volumes"]
        table.clear()
        for vol in volumes:
            table.add_row(
                vol["name"],
                vol["driver"],
                vol["mountpoint"],
                vol["created"]
            )

    async def update_networks_tab(self) -> None:
        """Update the Networks tab."""
        tab = self.query_one("#networks", TabPane)
        networks = self.docker_client.get_networks()

        if not networks:
            self.mount_error_table("networks", "No networks found")
            return

        if "networks" not in self.tables:
            tab.mount(DataTable())
            self.tables["networks"] = tab.query_one(DataTable)
            self.tables["networks"].add_columns("ID", "Name", "Driver", "Created")

        table = self.tables["networks"]
        table.clear()
        for net in networks:
            table.add_row(
                net["id"],
                net["name"],
                net["driver"],
                net["created"]
            )

    def mount_error_table(self, tab_id: str, message: str) -> None:
        """Mount a table with an error or no-data message."""
        tab = self.query_one(f"#{tab_id}", TabPane)
        for widget in tab.query():
            widget.remove()
        tab.mount(DataTable(classes="no-data"))
        table = tab.query_one(DataTable)
        table.add_column("Message")
        table.add_row(message)

    def action_switch_tab(self) -> None:
        """Switch to the next tab."""
        tabbed_content = self.query_one(TabbedContent)
        tabbed_content.active = tabbed_content.next_tab
        self.active_tab = tabbed_content.active
        self.run_worker(self.update_tab_content(self.active_tab))


if __name__ == "__main__":
    app = DockManApp()
    app.run()