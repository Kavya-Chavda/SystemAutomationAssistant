from PySide6.QtWidgets import QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QMessageBox

from .theme import stylesheet, SUCCESS, DANGER, WARNING
from .top_bar import TopBar
from .chat_widget import ChatWidget
from .command_input import CommandInput
from .sidebar import Sidebar
from .status_bar import BottomStatusBar


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("System Automation Assistant")
        self.resize(1180, 760)
        self.setStyleSheet(stylesheet())

        self.backend = None  # Will be set by gui_main.py

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.top_bar = TopBar()
        root.addWidget(self.top_bar)

        body = QWidget()
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(16, 16, 16, 0)
        body_layout.setSpacing(16)

        center = QWidget()
        center_layout = QVBoxLayout(center)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(0)

        self.chat = ChatWidget()
        self.command_input = CommandInput()
        center_layout.addWidget(self.chat, 1)
        center_layout.addWidget(self.command_input)

        self.sidebar = Sidebar()

        body_layout.addWidget(center, 1)
        body_layout.addWidget(self.sidebar)
        root.addWidget(body, 1)

        self.status_bar = BottomStatusBar()
        root.addWidget(self.status_bar)

        self.command_input.execute_requested.connect(self.handle_command)
        self.command_input.clear_requested.connect(self.chat_clear)
        self.command_input.voice_toggled.connect(self._handle_voice_toggle)

        self.chat.add_assistant_message(
            "Hi, I'm your System Automation Assistant. Type a command or use the mic to get started."
        )

        self.top_bar.settings_btn.clicked.connect(self._open_settings)

    def _open_settings(self):
        if self.backend:
            from src.gui.settings_dialog import SettingsDialog
            dialog = SettingsDialog(self.backend, self)
            dialog.exec()


    def set_backend(self, backend):
        self.backend = backend
        self.backend.command_finished.connect(self._on_command_finished)
        self.backend.voice_recognized.connect(self._on_voice_recognized)
        self.backend.voice_error.connect(self._on_voice_error)
        
        if hasattr(self.backend, 'status_monitor'):
            # Set initial model in status bar
            if hasattr(self.backend.engine.parser, 'client'):
                self.status_bar.set_model(self.backend.engine.parser.client.model)
                
            self.backend.status_monitor.ollama_status_changed.connect(self._on_ollama_status_sidebar)
            self.backend.status_monitor.ollama_status_changed.connect(self._on_ollama_status_bottom_bar)
            self.backend.status_monitor.executor_status_changed.connect(self._on_executor_status_sidebar)
            self.backend.status_monitor.microphone_status_changed.connect(self._on_microphone_status_changed)
            
            self.backend.status_monitor.force_emit_all()        
            
        self.backend.engine_status_changed.connect(lambda s: self.sidebar.status_card.update_status("Automation Engine", s))
        self.backend.mode_changed.connect(lambda s: self.sidebar.status_card.update_status("Current Mode", s))
        self.backend.task_changed.connect(lambda s: self.sidebar.status_card.update_status("Current Task", s))
        self.backend.voice_status_changed.connect(lambda s: self.sidebar.status_card.update_status("Voice", s))
        
        if hasattr(self.backend, 'force_emit_all'):
            self.backend.force_emit_all()
            
        # Connect Settings Signals
        self.backend.settings.interface_visibility_changed.connect(self._on_interface_visibility_changed)
        self._on_interface_visibility_changed()
            
        # Initial population of sidebar
        history = self.backend.get_recent_actions()
        for entry in history[-20:]: # max 20
            res = entry.get("execution_result", {})
            action = entry.get("parsed_command", {}).get("action", "unknown")
            msg = res.get("message", "")
            if msg:
                from src.gui.response_formatter import ResponseFormatter
                _, summary = ResponseFormatter.format_result(action, res)
                self.sidebar.add_action(summary)

    def _on_ollama_status_sidebar(self, status: str, is_ok: bool):
        if status == "Ollama Connected":
            self.sidebar.status_card.update_status("Ollama", "Ready")
        elif status == "Ollama Offline":
            self.sidebar.status_card.update_status("Ollama", "Offline")
        elif status == "Ollama Model Unavailable":
            self.sidebar.status_card.update_status("Ollama", "Model Unavailable")
        else:
            self.sidebar.status_card.update_status("Ollama", "Error")

    def _on_interface_visibility_changed(self):
        show_status = self.backend.settings.get("interface", "show_system_status")
        show_recent = self.backend.settings.get("interface", "show_recent_actions")
        
        self.sidebar.status_card.setVisible(show_status)
        self.sidebar.actions_panel.setVisible(show_recent)

    def _on_ollama_status_bottom_bar(self, status: str, is_ok: bool):
        from .theme import SUCCESS, DANGER, WARNING
        model_name = self.backend.engine.parser.client.model if hasattr(self.backend.engine.parser, 'client') else "Unknown"
        
        if status == "Ollama Connected":
            self.status_bar.update_model_status(model_name, "Ready", SUCCESS)
        elif status == "Ollama Offline":
            self.status_bar.update_model_status(model_name, "Offline", DANGER)
        elif status == "Ollama Model Unavailable":
            self.status_bar.update_model_status(model_name, "Model Unavailable", WARNING)
        elif status == "Checking...":
            self.status_bar.update_model_status(model_name, "Checking...", WARNING)
        else:
            self.status_bar.update_model_status(model_name, "Error", DANGER)

    def _on_executor_status_sidebar(self, status: str, is_ok: bool):
        if status == "Executor Ready":
            self.sidebar.status_card.update_status("Executor", "Idle")
        elif status == "Executor Busy":
            self.sidebar.status_card.update_status("Executor", "Busy")
        elif status == "Executor Error":
            self.sidebar.status_card.update_status("Executor", "Error")
        else:
            self.sidebar.status_card.update_status("Executor", "Unavailable")

    def _on_microphone_status_changed(self, status: str, is_ok: bool):
        # Don't overwrite if Voice is actively working
        current_voice = self.sidebar.status_card.labels.get("Voice").text() if "Voice" in self.sidebar.status_card.labels else ""
        if current_voice in ["Listening", "Processing"]:
            return
            
        if status == "Microphone Ready":
            self.sidebar.status_card.update_status("Voice", "Ready")
        elif status == "Microphone Unavailable":
            self.sidebar.status_card.update_status("Voice", "Unavailable")
        else:
            self.sidebar.status_card.update_status("Voice", "Error")
                
    def _handle_voice_toggle(self, active: bool):
        if self.backend:
            if active:
                self.command_input.set_text("")
                self.command_input.input.setPlaceholderText("Listening...")
                self.command_input.input.setEnabled(False)
                self.command_input.execute_btn.setEnabled(False)
                self.backend.start_voice()
            else:
                self.command_input.input.setPlaceholderText("Processing speech...")
                self.command_input.mic_btn.setEnabled(False)
                self.backend.stop_voice()
            
    def _on_voice_recognized(self, text: str):
        self._reset_voice_ui()
        # Voice is ready again, but we should let the microphone health check or backend reset it.
        # But wait, backend doesn't know it's ready, so we set it here.
        self.sidebar.status_card.update_status("Voice", "Ready")
        self.backend.mode_changed.emit("Idle")
        self.command_input.set_text(text)
        self.command_input.focus()
        
    def _on_voice_error(self, error_msg: str):
        self._reset_voice_ui()
        self.sidebar.status_card.update_status("Voice", "Ready")
        self.backend.mode_changed.emit("Idle")
        self.chat.add_assistant_message("I couldn't understand that.\n\nPlease try again.")
        
    def _reset_voice_ui(self):
        self.command_input.reset_voice_state()

    def chat_clear(self):
        reply = QMessageBox.question(self, 'Clear Chat', 'Clear current conversation?',
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.chat.clear()
            self.chat.add_assistant_message("Hi, I'm your System Automation Assistant.\n\nType a command or press the microphone to begin.")

    def handle_command(self, text: str):
        if not text.strip(): return
        self.chat.add_user_message(text)
        
        self.chat.show_thinking()
        
        # Disable input while processing
        self.command_input.set_enabled(False)
        
        if self.backend:
            self.backend.execute(text)

    def _on_command_finished(self, result: dict):
        self.chat.hide_thinking()
        
        # Re-enable inputs
        self.command_input.set_enabled(True)
        self.command_input.focus()
        
        parsed = result.get("parsed_command", {})
        if isinstance(parsed, list):
            action = "execute_queue"
        else:
            action = parsed.get("action", "unknown")
            
        exec_result = result.get("execution_result", {})
        
        from src.gui.response_formatter import ResponseFormatter
        rich_text, summary = ResponseFormatter.format_result(action, exec_result)
        
        self.chat.stream_assistant_message(rich_text)
        self.sidebar.add_action(summary)

    def closeEvent(self, event):
        if self.backend:
            self.backend.shutdown()
        event.accept()
