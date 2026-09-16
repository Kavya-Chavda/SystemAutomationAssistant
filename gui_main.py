import sys
import os
import ctypes
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon
from src.gui.main_window import MainWindow
from src.utils.logger import setup_logger

from src.gui.backend.automation_backend import AutomationBackend

logger = setup_logger("gui_main")

def main():
    print("Launching System Automation Assistant GUI...")
    
    # Set AppUserModelID for Windows so taskbar icon is not grouped with Python generic icon
    try:
        app_id = 'mycompany.systemautomationassistant.gui.1.0'
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
    except Exception:
        pass

    app = QApplication(sys.argv)
    
    icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "app_icon.png")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    
    window = MainWindow()
    backend = AutomationBackend()
    window.set_backend(backend)
    
    settings = backend.settings
    
    # Apply startup settings
    start_minimized = settings.get("interface", "launch_minimized")
    if start_minimized:
        window.showMinimized()
    else:
        window.showMaximized()
        
    # Enforce Windows startup logic (creates/removes shortcut in shell:startup)
    from src.utils.startup_manager import ensure_startup_state
    ensure_startup_state(settings.get("interface", "start_with_windows"))
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
