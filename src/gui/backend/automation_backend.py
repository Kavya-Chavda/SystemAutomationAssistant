import logging
from typing import Dict, Any
from PySide6.QtCore import QObject, QThread, Signal, Slot

from src.llm.ollama_client import OllamaClient
from src.core.command_parser import CommandParser
from src.core.history_manager import HistoryManager
from src.planner.resolver import CommandResolver
from src.automation.executor import Executor
from src.automation.engine import AutomationEngine
from src.nlp.preprocessor import NLPPreprocessor
from src.tools.registry import ToolRegistry
from src.tools.application_finder import ApplicationFinder
from src.planner.task_planner import TaskPlanner
from src.core.settings_manager import SettingsManager
from src.gui.confirmation_dialog import ConfirmationDialog
import queue

from src.tools.system_tools import OpenApplicationTool, CloseApplicationTool, TakeScreenshotTool, SearchWebTool, OpenUrlTool
from src.tools.filesystem_tools import (
    CreateFolderTool, CreateFileTool, RenameItemTool, DeleteItemTool,
    CopyFileTool, MoveFileTool, OpenItemTool, FindItemTool,
    ConfirmDeleteTool, CancelDeleteTool
)
from src.tools.wait_tool import WaitTool
from src.tools.desktop_tools import (
    ClickTool, DoubleClickTool, RightClickTool, TypeTextTool,
    HotkeyTool, ScrollTool, MoveMouseTool
)
from src.tools.system_control.window_tools import (
    MinimizeWindowTool, MaximizeWindowTool, RestoreWindowTool,
    GetCurrentWindowTool, ListOpenWindowsTool, IsWindowOpenTool, FocusWindowTool
)
from src.tools.system_control.volume_tools import (
    MuteVolumeTool, UnmuteVolumeTool, IncreaseVolumeTool,
    DecreaseVolumeTool, SetVolumeTool, GetVolumeStatusTool
)
from src.tools.system_control.brightness_tools import (
    IncreaseBrightnessTool, DecreaseBrightnessTool, SetBrightnessTool, GetBrightnessStatusTool
)
from src.tools.system_control.display_tools import GetDisplayStatusTool
from src.tools.system_control.wifi_tools import (
    EnableWifiTool, DisableWifiTool, GetWifiStatusTool, WifiDebugTool
)
from src.tools.system_control.hotspot_tools import GetHotspotStatusTool
from src.tools.system_control.power_tools import (
    GetBatterySaverStatusTool, ListPowerProfilesTool, GetPowerModeStatusTool, SetPowerModeTool
)
from src.tools.system_control.power_actions_tools import (
    ShutdownTool, RestartTool, SleepTool, LockScreenTool,
    ConfirmPowerActionTool, CancelPowerActionTool
)

from src.context.application_state_manager import ApplicationStateManager
from src.context.context_manager import ContextManager
from src.context.reference_resolver import ReferenceResolver
from src.context.persistence_manager import PersistenceManager

logger = logging.getLogger(__name__)

class ExecutionWorker(QObject):
    started = Signal()
    finished = Signal(dict) # result dict
    step_started = Signal(str)
    
    def __init__(self, engine: AutomationEngine):
        super().__init__()
        self.engine = engine
        self.engine.executor.on_step_start = self.step_started.emit
        self.command = ""
        
    @Slot()
    def run(self):
        self.started.emit()
        try:
            result = self.engine.process_command(self.command, source="keyboard")
            if result:
                self.finished.emit(result)
            else:
                self.finished.emit({"execution_result": {"status": "error", "message": "Command execution returned nothing."}})
        except Exception as e:
            logger.error(f"ExecutionWorker error: {e}", exc_info=True)
            self.finished.emit({
                "execution_result": {
                    "status": "failed",
                    "title": "System Error",
                    "message": "The automation engine encountered an unexpected technical error.",
                    "suggestions": [
                        "Please check logs/system.log for details.",
                        "Try repeating the command."
                    ]
                }
            })

class VoiceWorker(QObject):
    recognized = Signal(str)
    error = Signal(str)
    
    def __init__(self, settings_manager=None):
        super().__init__()
        self.settings = settings_manager
        self.listener = None
            
    @Slot()
    def listen(self):
        if not self.settings or not self.settings.get("voice", "enabled"):
            return
            
        from src.voice.voice_listener import VoiceListener
        if not self.listener:
            try:
                self.listener = VoiceListener()
            except Exception as e:
                logger.error(f"Failed to initialize VoiceListener: {e}", exc_info=True)
                self.error.emit("Voice recognition is not available or failed to initialize.")
                return
            
        mic_id = self.settings.get("voice", "microphone") if self.settings else None
        
        try:
            result = self.listener.listen(
                silence_threshold=0.015, 
                silence_duration=1.2,
                device=mic_id,
                manual_stop_only=True
            )
            if result and result.get("transcript"):
                text = result["transcript"]
                if text.strip():
                    self.recognized.emit(text)
            else:
                self.error.emit("No speech detected.")
        except Exception as e:
            logger.error(f"VoiceWorker error: {e}", exc_info=True)
            self.error.emit(str(e))
        finally:
            # Ensure listener state is reset if it crashed
            if self.listener:
                try:
                    self.listener.stop()
                except Exception:
                    pass


class AutomationBackend(QObject):
    command_finished = Signal(dict)
    voice_recognized = Signal(str)
    voice_error = Signal(str)
    
    engine_status_changed = Signal(str)
    mode_changed = Signal(str)
    task_changed = Signal(str)
    voice_status_changed = Signal(str)
    confirm_signal = Signal(str, str) # title, message
    
    def __init__(self, settings_manager: SettingsManager = None):
        super().__init__()
        self._is_executing = False
        self.settings = settings_manager or SettingsManager()
        self.confirm_queue = queue.Queue()
        self.confirm_signal.connect(self._show_confirm_dialog)
        self.engine = self._initialize_engine()
        
        # Execution Thread
        self.exec_thread = QThread()
        self.exec_worker = ExecutionWorker(self.engine)
        self.exec_worker.moveToThread(self.exec_thread)
        self.exec_worker.started.connect(self._on_execution_started)
        self.exec_worker.finished.connect(self._on_execution_finished)
        self.exec_worker.step_started.connect(self._on_step_started)
        self.exec_thread.start()
        
        # Status Monitor
        from src.gui.backend.status_monitor import StatusMonitor
        client = self.engine.parser.client
        self.status_monitor = StatusMonitor(ollama_host=client.host, ollama_model=client.model)
        self.status_monitor.set_executor_status("Executor Ready")
        
        # Voice Thread
        self.voice_thread = QThread()
        self.voice_worker = VoiceWorker(self.settings)
        self.voice_worker.moveToThread(self.voice_thread)
        self.voice_worker.recognized.connect(self.voice_recognized)
        self.voice_worker.error.connect(self.voice_error)
        self.voice_thread.start()
        
        # Wire SettingsManager signals
        self.settings.model_changed.connect(self._on_settings_model_changed)
        self.settings.voice_enabled_changed.connect(self._on_settings_voice_enabled_changed)
        
    def force_emit_all(self):
        self.engine_status_changed.emit("Online")
        self.mode_changed.emit("Idle")
        self.task_changed.emit("None")
        
    def _on_settings_model_changed(self, new_model: str):
        if hasattr(self.engine.parser, 'client'):
            self.engine.parser.client.model = new_model
        if hasattr(self, 'status_monitor'):
            self.status_monitor.ollama_model = new_model
            # Force immediate re-check with new model
            self.status_monitor._check_ollama()
            
    def _on_settings_voice_enabled_changed(self, enabled: bool):
        if not enabled:
            self.stop_voice()
        # Voice UI state (mic button enabled/disabled) will be handled via SettingsManager signals in MainWindow
        
    @Slot(str, str)
    def _show_confirm_dialog(self, title: str, message: str):
        from PySide6.QtWidgets import QDialog
        dialog = ConfirmationDialog(title, message)
        self.confirm_queue.put(dialog.exec() == QDialog.Accepted)
        
    def _ask_confirmation_blocking(self, title: str, message: str) -> bool:
        self.confirm_signal.emit(title, message)
        return self.confirm_queue.get()
        
    def _initialize_engine(self) -> AutomationEngine:
        registry = ToolRegistry()
        app_finder = ApplicationFinder()
        
        registry.register(OpenApplicationTool(app_finder))
        registry.register(CloseApplicationTool())
        registry.register(TakeScreenshotTool())
        registry.register(SearchWebTool())
        registry.register(WaitTool())
        registry.register(OpenUrlTool())
        
        registry.register(CreateFolderTool())
        registry.register(CreateFileTool())
        registry.register(RenameItemTool())
        registry.register(DeleteItemTool())
        registry.register(CopyFileTool())
        registry.register(MoveFileTool())
        registry.register(OpenItemTool())
        registry.register(FindItemTool())
        registry.register(ConfirmDeleteTool())
        registry.register(CancelDeleteTool())
        
        registry.register(ClickTool())
        registry.register(DoubleClickTool())
        registry.register(RightClickTool())
        registry.register(TypeTextTool())
        registry.register(HotkeyTool())
        registry.register(ScrollTool())
        registry.register(MoveMouseTool())
        
        registry.register(IsWindowOpenTool())
        registry.register(FocusWindowTool())
        registry.register(MinimizeWindowTool())
        registry.register(MaximizeWindowTool())
        registry.register(RestoreWindowTool())
        registry.register(GetCurrentWindowTool())
        registry.register(ListOpenWindowsTool())
        
        registry.register(MuteVolumeTool())
        registry.register(UnmuteVolumeTool())
        registry.register(IncreaseVolumeTool())
        registry.register(DecreaseVolumeTool())
        registry.register(SetVolumeTool())
        registry.register(GetVolumeStatusTool())
        
        registry.register(IncreaseBrightnessTool())
        registry.register(DecreaseBrightnessTool())
        registry.register(SetBrightnessTool())
        registry.register(GetBrightnessStatusTool())
        
        registry.register(GetDisplayStatusTool())
        
        registry.register(EnableWifiTool())
        registry.register(DisableWifiTool())
        registry.register(GetWifiStatusTool())
        registry.register(WifiDebugTool())
        registry.register(GetHotspotStatusTool())
        registry.register(GetBatterySaverStatusTool())
        registry.register(ListPowerProfilesTool())
        registry.register(GetPowerModeStatusTool())
        registry.register(SetPowerModeTool())
        registry.register(ShutdownTool())
        registry.register(RestartTool())
        registry.register(SleepTool())
        registry.register(LockScreenTool())
        registry.register(ConfirmPowerActionTool())
        registry.register(CancelPowerActionTool())
        
        # Read initial model from settings
        initial_model = self.settings.get("ai", "model") or "gemma3:4b"
        client = OllamaClient(host="http://localhost:11434", model=initial_model)
        parser = CommandParser(client=client, registry=registry)
        resolver = CommandResolver()
        task_planner = TaskPlanner()
        
        persistence_manager = PersistenceManager()
        state_manager = ApplicationStateManager(persistence_manager)
        context_manager = ContextManager(persistence_manager)
        
        state_manager.load()
        context_manager.load()
        
        reference_resolver = ReferenceResolver(context_manager)
        
        executor = Executor(
            registry=registry, 
            state_manager=state_manager, 
            context_manager=context_manager,
            reference_resolver=reference_resolver,
            settings_manager=self.settings
        )
        executor.set_confirmation_callback(self._ask_confirmation_blocking)

        history_manager = HistoryManager()
        nlp_preprocessor = NLPPreprocessor()
        
        engine = AutomationEngine(
            parser=parser,
            resolver=resolver,
            task_planner=task_planner,
            executor=executor,
            history_manager=history_manager,
            context_manager=context_manager,
            reference_resolver=reference_resolver,
            nlp_preprocessor=nlp_preprocessor
        )
        return engine

    def execute(self, text: str):
        self.exec_worker.command = text
        # trigger run on worker thread
        from PySide6.QtCore import QMetaObject, Qt
        QMetaObject.invokeMethod(self.exec_worker, "run", Qt.QueuedConnection)

    def start_voice(self):
        self.mode_changed.emit("Listening")
        self.voice_status_changed.emit("Listening")
        from PySide6.QtCore import QMetaObject, Qt
        QMetaObject.invokeMethod(self.voice_worker, "listen", Qt.QueuedConnection)

    def stop_voice(self):
        self.mode_changed.emit("Processing")
        self.voice_status_changed.emit("Processing")
        if self.voice_worker.listener:
            self.voice_worker.listener.stop()

    @Slot()
    def _on_execution_started(self):
        self._is_executing = True
        self.engine_status_changed.emit("Busy")
        self.mode_changed.emit("Executing")
        if hasattr(self, 'status_monitor'):
            self.status_monitor.set_executor_status("Executor Busy")

    @Slot(str)
    def _on_step_started(self, desc: str):
        self.task_changed.emit(desc)

    @Slot(dict)
    def _on_execution_finished(self, result: dict):
        self._is_executing = False
        self.engine_status_changed.emit("Online")
        self.mode_changed.emit("Idle")
        self.task_changed.emit("None")
        if hasattr(self, 'status_monitor'):
            self.status_monitor.set_executor_status("Executor Ready")
        self.command_finished.emit(result)
        
    def is_executing(self) -> bool:
        """Returns True if the executor is currently processing a command."""
        return self._is_executing
        
    def get_recent_actions(self):
        return self.engine.history_manager.get_recent_commands(limit=20)
        
    def get_status(self) -> Dict[str, Any]:
        if not self.engine.context_manager:
            return {}
        return self.engine.context_manager.get_context_snapshot()

    def shutdown(self):
        self.exec_worker.deleteLater()
        self.exec_thread.quit()
        self.exec_thread.wait()
        
        self.voice_worker.deleteLater()
        self.voice_thread.quit()
        self.voice_thread.wait()
        
        if hasattr(self, 'status_monitor'):
            self.status_monitor.shutdown()
