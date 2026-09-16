import os
import json
import tempfile
from unittest import TestCase
from PySide6.QtCore import QCoreApplication

# Ensure QCoreApplication is available for signals
if not QCoreApplication.instance():
    app = QCoreApplication([])

from src.core.settings_manager import SettingsManager

class TestSettingsManager(TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.settings = SettingsManager(config_dir=self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_default_creation(self):
        self.assertTrue(os.path.exists(self.settings.get_config_path()))
        self.assertEqual(self.settings.get("ai", "provider"), "ollama")
        self.assertTrue(self.settings.get("voice", "enabled"))

    def test_save_and_load(self):
        self.settings.set("ai", "model", "test-model")
        self.settings.save()

        # Create a new instance pointing to the same dir
        new_settings = SettingsManager(config_dir=self.temp_dir.name)
        self.assertEqual(new_settings.get("ai", "model"), "test-model")

    def test_update_category_emits_signal(self):
        signal_emitted = False
        def on_changed(cat, vals):
            nonlocal signal_emitted
            signal_emitted = True
            
        self.settings.settings_changed.connect(on_changed)
        self.settings.update_category("automation", {"command_timeout": 60})
        
        self.assertTrue(signal_emitted)
        self.assertEqual(self.settings.get("automation", "command_timeout"), 60)

    def test_corrupted_file_falls_back_to_defaults(self):
        # Corrupt the file
        with open(self.settings.get_config_path(), "w") as f:
            f.write("{ invalid json")

        new_settings = SettingsManager(config_dir=self.temp_dir.name)
        self.assertEqual(new_settings.get("ai", "provider"), "ollama")
        
    def test_missing_keys_filled_with_defaults(self):
        partial = {"version": 1, "ai": {"model": "custom"}}
        with open(self.settings.get_config_path(), "w") as f:
            json.dump(partial, f)
            
        new_settings = SettingsManager(config_dir=self.temp_dir.name)
        self.assertEqual(new_settings.get("ai", "model"), "custom")
        self.assertEqual(new_settings.get("voice", "enabled"), True) # Filled from default
