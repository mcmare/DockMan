import docker
import asyncio
from docker.errors import DockerException, APIError
from typing import List, Dict, Any
import os
from datetime import datetime
import iso8601
import time
import logging

# Set up logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DockerClient:
    def __init__(self):
        """Initialize Docker client."""
        try:
            if not os.path.exists("/var/run/docker.sock"):
                raise Exception("Docker socket /var/run/docker.sock not found. Is Docker running?")
            if not os.access("/var/run/docker.sock", os.R_OK | os.W_OK):
                raise Exception(
                    "Permission denied for Docker socket. "
                    "Try running with sudo or add user to 'docker' group: sudo usermod -aG docker $USER"
                )
            self.client = docker.from_env()
            self._cache = {
                "containers": {"data": [], "last_update": 0},
                "images": {"data": [], "last_update": 0},
                "volumes": {"data": [], "last_update": 0},
                "networks": {"data": [], "last_update": 0}
            }
            self._container_stats_cache = {}
            self._cache_duration = 5  # Cache data for 5 seconds
            logger.debug("DockerClient initialized successfully")
        except DockerException as e:
            logger.error(f"Failed to connect to Docker: {e}")
            raise Exception(f"Failed to connect to Docker: {e}")

    async def get_containers(self, all: bool = True) -> List[Dict[str, Any]]:
        """Get list of containers with details."""
        current_time = time.time()
        if current_time - self._cache["containers"]["last_update"] < self._cache_duration:
            logger.debug("Returning cached containers")
            return self._cache["containers"]["data"]

        try:
            containers = await asyncio.to_thread(self.client.containers.list, all=all)
            await self._update_stats_cache(containers)
            self._cache["containers"]["data"] = [
                {
                    "id": c.id[:12],
                    "name": c.name,
                    "status": c.status,
                    "image": c.image.tags[0] if c.image.tags else "unknown",
                    "ports": self._format_ports(c.attrs["NetworkSettings"]["Ports"]),
                    "cpu": self._container_stats_cache.get(c.id, {"cpu": 0.0})["cpu"],
                    "memory": self._container_stats_cache.get(c.id, {"memory": 0.0})["memory"],
                    "memory_percent": self._container_stats_cache.get(c.id, {"memory_percent": 0.0})["memory_percent"],
                    "created": self._format_datetime(c.attrs["Created"]),
                    "labels": c.attrs["Config"]["Labels"]
                }
                for c in containers
            ]
            self._cache["containers"]["last_update"] = current_time
            logger.debug(f"Fetched {len(containers)} containers")
            return self._cache["containers"]["data"]
        except APIError as e:
            logger.error(f"Error fetching containers: {e}")
            raise Exception(f"Error fetching containers: {e}")

    async def _update_stats_cache(self, containers: List) -> None:
        """Update cached container statistics."""
        for container in containers:
            try:
                stats = await asyncio.to_thread(container.stats, stream=False)
                cpu_delta = (
                    stats["cpu_stats"]["cpu_usage"]["total_usage"]
                    - stats["precpu_stats"]["cpu_usage"]["total_usage"]
                )
                system_delta = (
                    stats["cpu_stats"]["system_cpu_usage"]
                    - stats["precpu_stats"]["system_cpu_usage"]
                )
                cpu_percent = (cpu_delta / system_delta * 100) if system_delta > 0 else 0.0
                memory_usage = stats["memory_stats"]["usage"] / (1024 * 1024)  # MB
                memory_limit = stats["memory_stats"].get("limit", 1) / (1024 * 1024)
                memory_percent = (memory_usage / memory_limit * 100) if memory_limit > 0 else 0.0
                self._container_stats_cache[container.id] = {
                    "cpu": round(cpu_percent, 2),
                    "memory": round(memory_usage, 2),
                    "memory_percent": round(memory_percent, 2)
                }
            except Exception as e:
                logger.warning(f"Failed to fetch stats for container {container.id}: {e}")
                self._container_stats_cache[container.id] = {
                    "cpu": 0.0,
                    "memory": 0.0,
                    "memory_percent": 0.0
                }

    def _format_datetime(self, datetime_str: str) -> str:
        """Parse ISO 8601 datetime string to readable format."""
        try:
            dt = iso8601.parse_date(datetime_str)
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return "Unknown"

    def _format_ports(self, ports: Dict) -> str:
        """Format container ports into a readable string."""
        if not ports:
            return ""
        result = []
        for private_port, public_ports in ports.items():
            if public_ports:
                for public_port in public_ports:
                    result.append(f"{public_port['HostPort']}:{private_port}")
            else:
                result.append(f"{private_port}")
        return ", ".join(result)

    async def start_container(self, container_id: str) -> None:
        """Start a container by ID."""
        try:
            container = await asyncio.to_thread(self.client.containers.get, container_id)
            await asyncio.to_thread(container.start)
            self._cache["containers"]["last_update"] = 0  # Invalidate cache
            logger.debug(f"Started container {container_id}")
        except APIError as e:
            logger.error(f"Error starting container {container_id}: {e}")
            raise Exception(f"Error starting container {container_id}: {e}")

    async def stop_container(self, container_id: str, timeout: int = 10) -> None:
        """Stop a container by ID."""
        try:
            container = await asyncio.to_thread(self.client.containers.get, container_id)
            await asyncio.to_thread(container.stop, timeout=timeout)
            self._cache["containers"]["last_update"] = 0  # Invalidate cache
            logger.debug(f"Stopped container {container_id}")
        except APIError as e:
            logger.error(f"Error stopping container {container_id}: {e}")
            raise Exception(f"Error stopping container {container_id}: {e}")

    async def restart_container(self, container_id: str, timeout: int = 10) -> None:
        """Restart a container by ID."""
        try:
            container = await asyncio.to_thread(self.client.containers.get, container_id)
            await asyncio.to_thread(container.restart, timeout=timeout)
            self._cache["containers"]["last_update"] = 0  # Invalidate cache
            logger.debug(f"Restarted container {container_id}")
        except APIError as e:
            logger.error(f"Error restarting container {container_id}: {e}")
            raise Exception(f"Error restarting container {container_id}: {e}")

    async def remove_container(self, container_id: str, force: bool = False) -> None:
        """Remove a container by ID."""
        try:
            container = await asyncio.to_thread(self.client.containers.get, container_id)
            await asyncio.to_thread(container.remove, force=force)
            self._cache["containers"]["last_update"] = 0  # Invalidate cache
            logger.debug(f"Removed container {container_id}")
        except APIError as e:
            logger.error(f"Error removing container {container_id}: {e}")
            raise Exception(f"Error removing container {container_id}: {e}")

    async def get_container_logs(self, container_id: str, tail: int = 100) -> str:
        """Get logs for a container."""
        try:
            container = await asyncio.to_thread(self.client.containers.get, container_id)
            logs = await asyncio.to_thread(container.logs, tail=tail)
            return logs.decode("utf-8")
        except APIError as e:
            logger.error(f"Error fetching logs for container {container_id}: {e}")
            raise Exception(f"Error fetching logs for container {container_id}: {e}")

    async def get_images(self) -> List[Dict[str, Any]]:
        """Get list of Docker images."""
        current_time = time.time()
        if current_time - self._cache["images"]["last_update"] < self._cache_duration:
            logger.debug("Returning cached images")
            return self._cache["images"]["data"]

        try:
            images = await asyncio.to_thread(self.client.images.list)
            self._cache["images"]["data"] = [
                {
                    "id": img.id[:12],
                    "tags": img.tags if img.tags else ["<none>"],
                    "size": round(img.attrs["Size"] / (1024 * 1024), 2),  # MB
                    "created": self._format_datetime(img.attrs["Created"])
                }
                for img in images
            ]
            self._cache["images"]["last_update"] = current_time
            logger.debug(f"Fetched {len(images)} images")
            return self._cache["images"]["data"]
        except APIError as e:
            logger.error(f"Error fetching images: {e}")
            raise Exception(f"Error fetching images: {e}")

    async def remove_image(self, image_id: str, force: bool = False) -> None:
        """Remove a Docker image by ID."""
        try:
            await asyncio.to_thread(self.client.images.remove, image_id, force=force)
            self._cache["images"]["last_update"] = 0  # Invalidate cache
            logger.debug(f"Removed image {image_id}")
        except APIError as e:
            logger.error(f"Error removing image {image_id}: {e}")
            raise Exception(f"Error removing image {image_id}: {e}")

    async def get_volumes(self) -> List[Dict[str, Any]]:
        """Get list of Docker volumes."""
        current_time = time.time()
        if current_time - self._cache["volumes"]["last_update"] < self._cache_duration:
            logger.debug("Returning cached volumes")
            return self._cache["volumes"]["data"]

        try:
            volumes = await asyncio.to_thread(self.client.volumes.list)
            self._cache["volumes"]["data"] = [
                {
                    "name": vol.name,
                    "driver": vol.attrs["Driver"],
                    "mountpoint": vol.attrs["Mountpoint"],
                    "created": vol.attrs.get("CreatedAt", "Unknown")
                }
                for vol in volumes
            ]
            self._cache["volumes"]["last_update"] = current_time
            logger.debug(f"Fetched {len(volumes)} volumes")
            return self._cache["volumes"]["data"]
        except APIError as e:
            logger.error(f"Error fetching volumes: {e}")
            raise Exception(f"Error fetching volumes: {e}")

    async def remove_volume(self, volume_name: str) -> None:
        """Remove a Docker volume by name."""
        try:
            volume = await asyncio.to_thread(self.client.volumes.get, volume_name)
            await asyncio.to_thread(volume.remove)
            self._cache["volumes"]["last_update"] = 0  # Invalidate cache
            logger.debug(f"Removed volume {volume_name}")
        except APIError as e:
            logger.error(f"Error removing volume {volume_name}: {e}")
            raise Exception(f"Error removing volume {volume_name}: {e}")

    async def get_networks(self) -> List[Dict[str, Any]]:
        """Get list of Docker networks."""
        current_time = time.time()
        if current_time - self._cache["networks"]["last_update"] < self._cache_duration:
            logger.debug("Returning cached networks")
            return self._cache["networks"]["data"]

        try:
            networks = await asyncio.to_thread(self.client.networks.list)
            self._cache["networks"]["data"] = [
                {
                    "id": net.id[:12],
                    "name": net.name,
                    "driver": net.attrs["Driver"],
                    "created": net.attrs.get("Created", "Unknown")
                }
                for net in networks
            ]
            self._cache["networks"]["last_update"] = current_time
            logger.debug(f"Fetched {len(networks)} networks")
            return self._cache["networks"]["data"]
        except APIError as e:
            logger.error(f"Error fetching networks: {e}")
            raise Exception(f"Error fetching networks: {e}")

    async def remove_network(self, network_id: str) -> None:
        """Remove a Docker network by ID."""
        try:
            network = await asyncio.to_thread(self.client.networks.get, network_id)
            await asyncio.to_thread(network.remove)
            self._cache["networks"]["last_update"] = 0  # Invalidate cache
            logger.debug(f"Removed network {network_id}")
        except APIError as e:
            logger.error(f"Error removing network {network_id}: {e}")
            raise Exception(f"Error removing network {network_id}: {e}")