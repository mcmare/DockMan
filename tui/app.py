import sys
import os
import asyncio
import logging

# Add parent directory to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, DataTable, TabbedContent, TabPane, LoadingIndicator
from textual.reactive import reactive
from core.docker_client import DockerClient

# Set up logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


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
        self.tab_ids = ["containers", "images", "volumes", "networks"]

    async def on_mount(self) -> None:
        """Initialize the app after mounting."""
        logger.debug("Mounting TUI application")
        # Show loading indicator
        self.query_one(TabbedContent).mount(LoadingIndicator())
        try:
            self.docker_client = DockerClient()
            self.notify("Connected to Docker successfully!", severity="information")
            logger.debug("Docker client initialized")
        except Exception as e:
            self.notify(f"Failed to connect to Docker: {e}", severity="error")
            logger.error(f"Failed to connect to Docker: {e}")

        # Initialize tab content
        await self.update_tab_content("containers")
        # Remove loading indicator
        for widget in self.query_one(TabbedContent).query(LoadingIndicator):
            widget.remove()
        self.is_loading = False
        logger.debug("TUI initialization complete")
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
            logger.debug(f"Skipping update for {tab_id} due to loading state")
            return

        if not self.docker_client:
            self.mount_error_table(tab_id, "Failed to connect to Docker")
            logger.error(f"No Docker client for {tab_id}")
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
            logger.error(f"Error updating {tab_id}: {e}")

    async def update_containers_tab(self) -> None:
        """Update the Containers tab."""
        logger.debug("Updating containers tab")
        tab = self.query_one("#containers", TabPane)
        containers = await self.docker_client.get_containers(all=True)
        logger.debug(f"Received {len(containers)} containers: {containers}")

        if not containers:
            self.mount_error_table("containers", "No containers found")
            logger.debug("No containers found")
            return

        if "containers" not in self.tables:
            tab.mount(DataTable())
            self.tables["containers"] = tab.query_one(DataTable)
            self.tables["containers"].add_columns("Name", "Status", "CPU %", "Memory MB", "Ports", "Created")
            logger.debug("Created containers table")

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
        logger.debug("Containers table updated")

    async def update_images_tab(self) -> None:
        """Update the Images tab."""
        logger.debug("Updating images tab")
        tab = self.query_one("#images", TabPane)
        images = await self.docker_client.get_images()

        if not images:
            self.mount_error_table("images", "No images found")
            logger.debug("No images found")
            return

        if "images" not in self.tables:
            tab.mount(DataTable())
            self.tables["images"] = tab.query_one(DataTable)
            self.tables["images"].add_columns("ID", "Tags", "Size MB", "Created")
            logger.debug("Created images table")

        table = self.tables["images"]
        table.clear()
        for img in images:
            table.add_row(
                img["id"],
                ", ".join(img["tags"]),
                str(img["size"]),
                img["created"]
            )
        logger.debug("Images table updated")

    async def update_volumes_tab(self) -> None:
        """Update the Volumes tab."""
        logger.debug("Updating volumes tab")
        tab = self.query_one("#volumes", TabPane)
        volumes = await self.docker_client.get_volumes()

        if not volumes:
            self.mount_error_table("volumes", "No volumes found")
            logger.debug("No volumes found")
            return

        if "volumes" not in self.tables:
            tab.mount(DataTable())
            self.tables["volumes"] = tab.query_one(DataTable)
            self.tables["volumes"].add_columns("Name", "Driver", "Mountpoint", "Created")
            logger.debug("Created volumes table")

        table = self.tables["volumes"]
        table.clear()
        for vol in volumes:
            table.add_row(
                vol["name"],
                vol["driver"],
                vol["mountpoint"],
                vol["created"]
            )
        logger.debug("Volumes table updated")

    async def update_networks_tab(self) -> None:
        """Update the Networks tab."""
        logger.debug("Updating networks tab")
        tab = self.query_one("#networks", TabPane)
        networks = await self.docker_client.get_networks()

        if not networks:
            self.mount_error_table("networks", "No networks found")
            logger.debug("No networks found")
            return

        if "networks" not in self.tables:
            tab.mount(DataTable())
            self.tables["networks"] = tab.query_one(DataTable)
            self.tables["networks"].add_columns("ID", "Name", "Driver", "Created")
            logger.debug("Created networks table")

        table = self.tables["networks"]
        table.clear()
        for net in networks:
            table.add_row(
                net["id"],
                net["name"],
                net["driver"],
                net["created"]
            )
        logger.debug("Networks table updated")

    def mount_error_table(self, tab_id: str, message: str) -> None:
        """Mount a table with an error or no-data message."""
        logger.debug(f"Mounting error table for {tab_id}: {message}")
        tab = self.query_one(f"#{tab_id}", TabPane)
        for widget in tab.query():
            widget.remove()
        tab.mount(DataTable(classes="no-data"))
        table = tab.query_one(DataTable)
        table.add_column("Message")
        table.add_row(message)

    def action_switch_tab(self) -> None:
        """Switch to the next tab."""
        logger.debug("Switching tab")
        tabbed_content = self.query_one(TabbedContent)
        current_tab = tabbed_content.active
        if current_tab:
            current_index = self.tab_ids.index(current_tab)
            next_index = (current_index + 1) % len(self.tab_ids)
            next_tab = self.tab_ids[next_index]
            tabbed_content.active = next_tab
            self.active_tab = next_tab
            logger.debug(f"Switched to tab {next_tab}")
            self.run_worker(self.update_tab_content(next_tab))
        else:
            logger.warning("No active tab found")


if __name__ == "__main__":
    app = DockManApp()
    app.run()