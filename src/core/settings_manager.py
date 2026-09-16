import json
import os
import logging
from typing import Dict, Any, Optional

from PySide6.QtCore import QObject, Signal

logger = logging.getLogger(__name__)

class SettingsManager(QObject):
    # Signals for live updates
    settings_changed = Signal(str, dict) # category, new_settings
    model_changed = Signal(str) # new model name
    voice_enabled_changed = Signal(bool)
    interface_visibility_changed = Signal()
    
    DEFAULT_SETTINGS = {
        "version": 1,
        "ai": {
            "provider": "ollama",
            "model": "gemma3:4b"
        },
        "voice": {
            "enabled": True,
            "microphone": "default",
            "speech_recognition": "faster_whisper",
            "language": "en",
            "wake_word_enabled": False,
            "wake_word": "Hey Assistant"
        },
        "automation": {
            "confirm_delete": True,
            "confirm_shutdown_restart": True,
            "confirm_bulk_file_operations": True,
            "execution_mode": "automatic",
            "command_timeout": 30
        },
        "interface": {
            "show_system_status": True,
            "show_recent_actions": True,
            "launch_minimized": False,
            "start_with_windows": False
        }
    }

    def __init__(self, config_dir: str = "config"):
        super().__init__()
        # Centralized path for future AppData packaging
        self.config_dir = os.path.abspath(config_dir)
        self.config_path = os.path.join(self.config_dir, "settings.json")
        self.settings: Dict[str, Any] = {}
        self.load()

    def get_config_path(self) -> str:
        return self.config_path

    def load(self) -> None:
        """Loads settings from disk, applying defaults for missing keys."""
        if not os.path.exists(self.config_path):
            logger.info("Settings file not found. Creating with defaults.")
            self.settings = self._deep_copy(self.DEFAULT_SETTINGS)
            self.save()
            return

        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                loaded_settings = json.load(f)
                
            # Handle versioning/migrations here in the future
            if loaded_settings.get("version", 0) < self.DEFAULT_SETTINGS["version"]:
                logger.info("Outdated settings version detected. Migrating...")
                # Simple migration: just merge with defaults
                pass
                
            self.settings = self._merge_with_defaults(loaded_settings, self.DEFAULT_SETTINGS)
            # Ensure we don't accidentally overwrite the version string back to old
            self.settings["version"] = self.DEFAULT_SETTINGS["version"]
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Failed to load settings (corrupt or unreadable). Using defaults. Error: {e}")
            self.settings = self._deep_copy(self.DEFAULT_SETTINGS)
            # We don't save immediately here to avoid overwriting a manually broken file unless the user explicitly saves later

    def save(self) -> bool:
        """Saves current settings to disk."""
        try:
            os.makedirs(self.config_dir, exist_ok=True)
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.settings, f, indent=4)
            return True
        except IOError as e:
            logger.error(f"Failed to save settings to {self.config_path}. Error: {e}")
            return False

    def get(self, category: str, key: str = None) -> Any:
        """Gets a full category or a specific key within a category."""
        if category not in self.settings:
            return None
        if key is None:
            return self.settings[category]
        return self.settings[category].get(key)

    def set(self, category: str, key: str, value: Any) -> None:
        """Sets a specific key in a category without saving."""
        if category not in self.settings:
            self.settings[category] = {}
        self.settings[category][key] = value

    def update_category(self, category: str, new_values: Dict[str, Any]) -> None:
        """Updates multiple keys in a category, saves, and emits a signal."""
        if category not in self.settings:
            self.settings[category] = {}
            
        changed = False
        for k, v in new_values.items():
            if self.settings[category].get(k) != v:
                self.settings[category][k] = v
                changed = True
                
        if changed:
            self.save()
            self.settings_changed.emit(category, self.settings[category])
            
            # Emit specific lifecycle signals
            if category == "ai" and "model" in new_values:
                self.model_changed.emit(new_values["model"])
            elif category == "voice" and "enabled" in new_values:
                self.voice_enabled_changed.emit(new_values["enabled"])
            elif category == "interface":
                self.interface_visibility_changed.emit()

    def reset_to_defaults(self) -> None:
        """Resets all settings to defaults and saves."""
        self.settings = self._deep_copy(self.DEFAULT_SETTINGS)
        self.save()

    def _deep_copy(self, d: Dict[str, Any]) -> Dict[str, Any]:
        return json.loads(json.dumps(d))

    def _merge_with_defaults(self, loaded: Dict[str, Any], defaults: Dict[str, Any]) -> Dict[str, Any]:
        """Deep merge dictionaries, preserving loaded values but filling missing keys from defaults."""
        result = self._deep_copy(defaults)
        for k, v in loaded.items():
            if k in result and isinstance(result[k], dict) and isinstance(v, dict):
                result[k] = self._merge_with_defaults(v, result[k])
            else:
                result[k] = v
        return result
