from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QStackedWidget,
    QWidget, QLabel, QPushButton, QComboBox, QCheckBox, QSpinBox,
    QFrame, QRadioButton, QButtonGroup, QMessageBox, QScrollArea
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon
import logging
from src.core.settings_manager import SettingsManager
from src.gui.theme import stylesheet, TEXT, TEXT_SECONDARY, BG, BORDER, ACCENT, DANGER

logger = logging.getLogger(__name__)

class SettingsDialog(QDialog):
    def __init__(self, backend, parent=None):
        super().__init__(parent)
        self.backend = backend
        self.settings: SettingsManager = backend.settings
        
        self.setWindowTitle("Settings")
        self.setWindowIcon(QIcon("assets/settings_icon.svg"))
        self.setFixedSize(700, 500)
        self.setStyleSheet(stylesheet())
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint | Qt.WindowCloseButtonHint)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Navigation List
        self.nav_list = QListWidget()
        self.nav_list.setFixedWidth(180)
        self.nav_list.setStyleSheet(f"""
            QListWidget {{
                background: {BG};
                border-right: 1px solid {BORDER};
                border-top: none; border-bottom: none; border-left: none;
                padding: 10px 0;
            }}
            QListWidget::item {{
                padding: 10px 20px;
                color: {TEXT};
            }}
            QListWidget::item:selected {{
                background: rgba(255, 255, 255, 0.05);
                border-left: 3px solid {ACCENT};
                color: {ACCENT};
            }}
            QListWidget::item:hover:!selected {{
                background: rgba(255, 255, 255, 0.02);
            }}
        """)
        
        categories = ["AI & Model", "Voice", "Automation", "Interface", "Diagnostics"]
        self.nav_list.addItems(categories)
        self.nav_list.currentRowChanged.connect(self._change_page)
        
        layout.addWidget(self.nav_list)
        
        # Main Content Area
        content_container = QWidget()
        content_container.setStyleSheet(f"background: {BG};")
        content_layout = QVBoxLayout(content_container)
        content_layout.setContentsMargins(20, 20, 20, 20)
        
        self.stacked_widget = QStackedWidget()
        self.stacked_widget.setStyleSheet("QStackedWidget { background: transparent; }")
        
        self.page_ai = self._create_ai_page()
        self.page_voice = self._create_voice_page()
        self.page_automation = self._create_automation_page()
        self.page_interface = self._create_interface_page()
        self.page_diagnostics = self._create_diagnostics_page()
        
        self.stacked_widget.addWidget(self.page_ai)
        self.stacked_widget.addWidget(self.page_voice)
        self.stacked_widget.addWidget(self.page_automation)
        self.stacked_widget.addWidget(self.page_interface)
        self.stacked_widget.addWidget(self.page_diagnostics)
        
        content_layout.addWidget(self.stacked_widget)
        
        # Bottom Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedSize(100, 32)
        cancel_btn.clicked.connect(self._cancel_and_close)
        
        save_btn = QPushButton("Save Changes")
        save_btn.setFixedSize(120, 32)
        save_btn.clicked.connect(self._save_settings)
        
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(save_btn)
        
        content_layout.addLayout(btn_layout)
        
        layout.addWidget(content_container, 1)
        
        self.nav_list.setCurrentRow(0)
        
    def _create_header(self, title: str, description: str) -> QVBoxLayout:
        layout = QVBoxLayout()
        layout.setSpacing(4)
        lbl_title = QLabel(title)
        lbl_title.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {TEXT};")
        lbl_desc = QLabel(description)
        lbl_desc.setStyleSheet(f"font-size: 13px; color: {TEXT_SECONDARY};")
        layout.addWidget(lbl_title)
        layout.addWidget(lbl_desc)
        layout.addSpacing(16)
        return layout
        
    def _create_ai_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignTop)
        
        layout.addLayout(self._create_header("AI & Model", "Configure the AI provider and model used for intelligence."))
        
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Provider:"))
        self.ai_provider = QComboBox()
        self.ai_provider.addItems(["Ollama"])
        row1.addWidget(self.ai_provider)
        layout.addLayout(row1)
        
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Model:"))
        self.ai_model = QComboBox()
        
        refresh_btn = QPushButton("Refresh Models")
        refresh_btn.clicked.connect(self._refresh_models)
        
        row2.addWidget(self.ai_model, 1)
        row2.addWidget(refresh_btn)
        layout.addLayout(row2)
        
        # Initial populate
        self._refresh_models()
        
        # Set from settings
        saved_model = self.settings.get("ai", "model")
        idx = self.ai_model.findText(saved_model)
        if idx >= 0:
            self.ai_model.setCurrentIndex(idx)
        else:
            self.ai_model.addItem(saved_model)
            self.ai_model.setCurrentText(saved_model)
            
        return page
        
    def _refresh_models(self):
        if hasattr(self.backend.engine.parser, 'client'):
            models = self.backend.engine.parser.client.get_available_models()
            current = self.ai_model.currentText()
            self.ai_model.clear()
            if models:
                self.ai_model.addItems(models)
            else:
                self.ai_model.addItem("gemma3:4b")
                
            idx = self.ai_model.findText(current)
            if idx >= 0:
                self.ai_model.setCurrentIndex(idx)

    def _create_voice_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignTop)
        
        layout.addLayout(self._create_header("Voice & Audio", "Configure microphone and wake word detection."))
        
        self.voice_enabled = QCheckBox("Enable Voice Commands")
        self.voice_enabled.setChecked(self.settings.get("voice", "enabled"))
        layout.addWidget(self.voice_enabled)
        layout.addSpacing(10)
        
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Microphone:"))
        self.voice_mic = QComboBox()
        self.voice_mic.addItem("default")
        
        from src.voice.audio_utils import get_available_microphones
        mics = get_available_microphones()
        for m in mics:
            self.voice_mic.addItem(f"{m['id']}: {m['name']}", userData=m['id'])
            
        saved_mic = self.settings.get("voice", "microphone")
        if saved_mic != "default":
            for i in range(self.voice_mic.count()):
                if self.voice_mic.itemData(i) == saved_mic:
                    self.voice_mic.setCurrentIndex(i)
                    break
                    
        test_btn = QPushButton("Test Mic")
        test_btn.clicked.connect(self._test_microphone)
        
        row1.addWidget(self.voice_mic, 1)
        row1.addWidget(test_btn)
        layout.addLayout(row1)
        
        layout.addSpacing(20)
        
        self.wake_word_enabled = QCheckBox("Enable Wake Word ('Hey Assistant')")
        # Explicitly checking if it's supported. We know it isn't (Vosk missing).
        self.wake_word_enabled.setChecked(False)
        self.wake_word_enabled.setEnabled(False)
        layout.addWidget(self.wake_word_enabled)
        
        lbl_warning = QLabel("Wake word is currently unavailable. Ensure Vosk and the offline model are installed.")
        lbl_warning.setStyleSheet(f"color: {DANGER}; font-size: 11px;")
        layout.addWidget(lbl_warning)
        
        return page

    def _test_microphone(self):
        QMessageBox.information(self, "Mic Test", "Microphone testing will check for input levels.")

    def _create_automation_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignTop)
        
        layout.addLayout(self._create_header("Automation Engine", "Configure how commands are executed and confirmed."))
        
        lbl = QLabel("Execution Mode:")
        layout.addWidget(lbl)
        
        self.exec_mode_group = QButtonGroup(self)
        
        row1 = QHBoxLayout()
        self.mode_auto = QRadioButton("Automatic (Fastest, asks only when needed)")
        self.mode_manual = QRadioButton("Manual (Requires confirmation for EVERY action)")
        
        self.exec_mode_group.addButton(self.mode_auto, 0)
        self.exec_mode_group.addButton(self.mode_manual, 1)
        
        saved_mode = self.settings.get("automation", "execution_mode")
        if saved_mode == "manual":
            self.mode_manual.setChecked(True)
        else:
            self.mode_auto.setChecked(True)
            
        row1.addWidget(self.mode_auto)
        row1.addWidget(self.mode_manual)
        layout.addLayout(row1)
        layout.addSpacing(15)
        
        lbl2 = QLabel("Require Confirmation For:")
        layout.addWidget(lbl2)
        
        self.chk_del = QCheckBox("File and Folder Deletion")
        self.chk_del.setChecked(self.settings.get("automation", "confirm_delete"))
        self.chk_power = QCheckBox("System Shutdown & Restart")
        self.chk_power.setChecked(self.settings.get("automation", "confirm_shutdown_restart"))
        self.chk_bulk = QCheckBox("Bulk File Operations")
        self.chk_bulk.setChecked(self.settings.get("automation", "confirm_bulk_file_operations"))
        
        layout.addWidget(self.chk_del)
        layout.addWidget(self.chk_power)
        layout.addWidget(self.chk_bulk)
        
        layout.addSpacing(15)
        
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Command Timeout (seconds):"))
        self.spin_timeout = QSpinBox()
        self.spin_timeout.setRange(5, 300)
        self.spin_timeout.setValue(self.settings.get("automation", "command_timeout"))
        row2.addWidget(self.spin_timeout)
        row2.addStretch()
        layout.addLayout(row2)
        
        return page

    def _create_interface_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignTop)
        
        layout.addLayout(self._create_header("Interface & Startup", "Configure visual elements and startup behavior."))
        
        self.chk_status = QCheckBox("Show System Status Panel (Right Sidebar)")
        self.chk_status.setChecked(self.settings.get("interface", "show_system_status"))
        
        self.chk_recent = QCheckBox("Show Recent Actions (Right Sidebar)")
        self.chk_recent.setChecked(self.settings.get("interface", "show_recent_actions"))
        
        self.chk_minimized = QCheckBox("Launch minimized on startup")
        self.chk_minimized.setChecked(self.settings.get("interface", "launch_minimized"))
        
        self.chk_windows = QCheckBox("Start with Windows")
        self.chk_windows.setChecked(self.settings.get("interface", "start_with_windows"))
        
        layout.addWidget(self.chk_status)
        layout.addWidget(self.chk_recent)
        layout.addSpacing(10)
        layout.addWidget(self.chk_minimized)
        layout.addWidget(self.chk_windows)
        
        return page

    def _create_diagnostics_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignTop)
        
        layout.addLayout(self._create_header("System Diagnostics", "Live view of internal service health states."))
        
        grid = QVBoxLayout()
        self.diag_labels = {}
        
        fields = ["Ollama Status", "Microphone Status", "Executor Status"]
        for f in fields:
            row = QHBoxLayout()
            row.addWidget(QLabel(f"{f}:"))
            lbl = QLabel("Checking...")
            lbl.setStyleSheet(f"color: {ACCENT}; font-weight: bold;")
            row.addWidget(lbl)
            row.addStretch()
            grid.addLayout(row)
            self.diag_labels[f] = lbl
            
        layout.addLayout(grid)
        
        # Wire live updates
        sm = self.backend.status_monitor
        if sm:
            sm.ollama_status_changed.connect(lambda s, ok: self.diag_labels["Ollama Status"].setText(s))
            sm.microphone_status_changed.connect(lambda s, ok: self.diag_labels["Microphone Status"].setText(s))
            sm.executor_status_changed.connect(lambda s, ok: self.diag_labels["Executor Status"].setText(s))
            sm.force_emit_all()
            
        return page

    def _change_page(self, index: int):
        self.stacked_widget.setCurrentIndex(index)

    def _save_settings(self):
        # AI
        self.settings.update_category("ai", {
            "provider": self.ai_provider.currentText().lower(),
            "model": self.ai_model.currentText()
        })
        
        # Voice
        mic_id = self.voice_mic.currentData()
        if not mic_id:
            mic_id = "default"
            
        self.settings.update_category("voice", {
            "enabled": self.voice_enabled.isChecked(),
            "microphone": mic_id,
            "wake_word_enabled": self.wake_word_enabled.isChecked()
        })
        
        # Automation
        self.settings.update_category("automation", {
            "execution_mode": "manual" if self.mode_manual.isChecked() else "automatic",
            "confirm_delete": self.chk_del.isChecked(),
            "confirm_shutdown_restart": self.chk_power.isChecked(),
            "confirm_bulk_file_operations": self.chk_bulk.isChecked(),
            "command_timeout": self.spin_timeout.value()
        })
        
        # Interface
        old_start_with_windows = self.settings.get("interface", "start_with_windows")
        new_start_with_windows = self.chk_windows.isChecked()
        
        self.settings.update_category("interface", {
            "show_system_status": self.chk_status.isChecked(),
            "show_recent_actions": self.chk_recent.isChecked(),
            "launch_minimized": self.chk_minimized.isChecked(),
            "start_with_windows": new_start_with_windows
        })
        
        if old_start_with_windows != new_start_with_windows:
            from src.utils.startup_manager import ensure_startup_state
            ensure_startup_state(new_start_with_windows)
        
        
        self.accept()

    def _cancel_and_close(self):
        """Discards unsaved changes and closes the dialog."""
        self.reject()

    def closeEvent(self, event):
        """Handle the title bar X close button."""
        self._cancel_and_close()
        event.accept()
