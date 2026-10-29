"""
Configuration File Watcher
Monitors domain pack files for changes and triggers hot-reload.
"""

import logging
import time
from pathlib import Path
from typing import Callable, Optional

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

logger = logging.getLogger(__name__)


class ConfigFileEventHandler(FileSystemEventHandler):
    """Handles file system events for config file changes."""

    def __init__(self, config_path: Path, on_change_callback: Callable[[], None]):
        self.config_path = config_path
        self.on_change_callback = on_change_callback
        self.last_modified = time.time()
        self.debounce_seconds = 1.0  # Debounce rapid file changes

    def on_modified(self, event: FileSystemEvent) -> None:
        """Called when a file is modified."""
        if event.is_directory:
            return

        # Check if the modified file is our config file
        modified_path = Path(event.src_path).resolve()
        if modified_path == self.config_path.resolve():
            # Debounce: ignore if modified too recently
            current_time = time.time()
            if current_time - self.last_modified < self.debounce_seconds:
                logger.debug(f"Debouncing config change: {modified_path}")
                return

            self.last_modified = current_time
            logger.info(f"Config file changed: {modified_path}")
            self.on_change_callback()


class ConfigWatcher:
    """
    Watches a domain pack configuration file for changes.
    Triggers reload callback when file is modified.
    """

    def __init__(self, config_path: Path, on_change_callback: Callable[[], None]):
        """
        Initialize config watcher.

        Args:
            config_path: Path to config file to watch
            on_change_callback: Function to call when config changes
        """
        self.config_path = config_path
        self.on_change_callback = on_change_callback
        self.observer: Optional[Observer] = None
        self.is_watching = False

    def start(self) -> None:
        """Start watching the config file."""
        if self.is_watching:
            logger.warning("Watcher already started")
            return

        if not self.config_path.exists():
            raise FileNotFoundError(f"Config file not found: {self.config_path}")

        # Watch the directory containing the config file
        watch_dir = self.config_path.parent

        event_handler = ConfigFileEventHandler(self.config_path, self.on_change_callback)
        self.observer = Observer()
        self.observer.schedule(event_handler, str(watch_dir), recursive=False)
        self.observer.start()
        self.is_watching = True

        logger.info(f"Started watching config file: {self.config_path}")

    def stop(self) -> None:
        """Stop watching the config file."""
        if not self.is_watching or not self.observer:
            logger.warning("Watcher not started")
            return

        self.observer.stop()
        self.observer.join()
        self.is_watching = False
        logger.info(f"Stopped watching config file: {self.config_path}")

    def __enter__(self):
        """Context manager entry."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop()
