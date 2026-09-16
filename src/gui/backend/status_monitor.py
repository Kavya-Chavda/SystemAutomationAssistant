import logging
import requests
from PySide6.QtCore import QObject, QThread, Signal, Slot, QTimer
import sounddevice as sd

logger = logging.getLogger(__name__)

class HealthCheckWorker(QObject):
    """
    Background worker that performs blocking health checks
    so the GUI thread is not interrupted.
    """
    ollama_checked = Signal(str)  # Returns status string
    microphone_checked = Signal(str) # Returns status string

    def __init__(self, ollama_host: str, ollama_model: str):
        super().__init__()
        self.ollama_host = ollama_host.rstrip('/')
        self.ollama_model = ollama_model

    @Slot()
    def check_all(self):
        self._check_ollama()
        self._check_microphone()

    def _check_ollama(self):
        try:
            response = requests.get(f"{self.ollama_host}/api/tags", timeout=2.0)
            response.raise_for_status()
            data = response.json()
            models = data.get("models", [])
            model_names = [m.get("name") for m in models]
            
            # Check if exactly matching or matching the base name (e.g. gemma3:4b)
            # Sometimes Ollama appends :latest if not specified.
            found = False
            target_model = self.ollama_model
            if ":" not in target_model:
                target_model += ":latest"
                
            for m in model_names:
                if m == self.ollama_model or m == target_model:
                    found = True
                    break
                    
            if found:
                self.ollama_checked.emit("Ollama Connected")
            else:
                self.ollama_checked.emit("Ollama Model Unavailable")
                
        except requests.exceptions.RequestException:
            self.ollama_checked.emit("Ollama Offline")
        except Exception as e:
            logger.error(f"Ollama health check error: {e}", exc_info=True)
            self.ollama_checked.emit("Ollama Error")

    def _check_microphone(self):
        try:
            # Query devices to see if there is any working input device
            devices = sd.query_devices()
            has_input = any(d.get('max_input_channels', 0) > 0 for d in devices)
            if has_input:
                self.microphone_checked.emit("Microphone Ready")
            else:
                self.microphone_checked.emit("Microphone Unavailable")
        except Exception as e:
            logger.error(f"Microphone health check error: {e}", exc_info=True)
            self.microphone_checked.emit("Microphone Error")


class StatusMonitor(QObject):
    """
    Central source of truth for component health statuses.
    """
    ollama_status_changed = Signal(str, bool)  # text, is_ok
    microphone_status_changed = Signal(str, bool) # text, is_ok
    executor_status_changed = Signal(str, bool) # text, is_ok

    def __init__(self, ollama_host: str, ollama_model: str, parent=None):
        super().__init__(parent)
        
        self._current_ollama = "Checking..."
        self._current_microphone = "Checking..."
        self._current_executor = "Checking..."
        
        # Setup worker thread
        self.worker_thread = QThread()
        self.worker = HealthCheckWorker(ollama_host, ollama_model)
        self.worker.moveToThread(self.worker_thread)
        
        self.worker.ollama_checked.connect(self._on_ollama_checked)
        self.worker.microphone_checked.connect(self._on_microphone_checked)
        
        self.worker_thread.start()
        
        # Setup polling timer
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._trigger_checks)
        self.timer.start(3000) # 3 seconds interval
        
        # Initial trigger
        self._trigger_checks()

    def _trigger_checks(self):
        from PySide6.QtCore import QMetaObject, Qt
        QMetaObject.invokeMethod(self.worker, "check_all", Qt.QueuedConnection)

    @Slot(str)
    def _on_ollama_checked(self, status: str):
        if status != self._current_ollama:
            logger.info(f"Ollama status changed: {self._current_ollama} -> {status}")
            self._current_ollama = status
            is_ok = status == "Ollama Connected"
            self.ollama_status_changed.emit(status, is_ok)

    @Slot(str)
    def _on_microphone_checked(self, status: str):
        if status != self._current_microphone:
            logger.info(f"Microphone status changed: {self._current_microphone} -> {status}")
            self._current_microphone = status
            is_ok = status == "Microphone Ready"
            self.microphone_status_changed.emit(status, is_ok)

    def set_executor_status(self, status: str):
        """Called by AutomationBackend when executor state changes."""
        if status != self._current_executor:
            logger.info(f"Executor status changed: {self._current_executor} -> {status}")
            self._current_executor = status
            is_ok = status in ("Executor Ready", "Executor Busy")
            self.executor_status_changed.emit(status, is_ok)

    def force_emit_all(self):
        """Re-emit current states for newly connected UI components."""
        self.ollama_status_changed.emit(self._current_ollama, self._current_ollama == "Ollama Connected")
        self.microphone_status_changed.emit(self._current_microphone, self._current_microphone == "Microphone Ready")
        self.executor_status_changed.emit(self._current_executor, self._current_executor in ("Executor Ready", "Executor Busy"))

    def shutdown(self):
        self.timer.stop()
        self.worker.deleteLater()
        self.worker_thread.quit()
        self.worker_thread.wait()
