import os
import sys
import logging

logger = logging.getLogger(__name__)

def ensure_startup_state(enable: bool):
    """
    Creates or removes a Windows startup shortcut in shell:startup.
    Since we are running from source for development, we will create a batch script or VBS 
    that runs `python gui_main.py`. If packaged, we would point to the .exe.
    """
    try:
        startup_dir = os.path.join(os.environ.get('APPDATA', ''), r'Microsoft\Windows\Start Menu\Programs\Startup')
        if not os.path.exists(startup_dir):
            return
            
        shortcut_path = os.path.join(startup_dir, 'SystemAutomationAssistant.vbs')
        
        if enable:
            # Create a VBS script to run without a visible console window
            project_root = os.path.abspath(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
            python_exe = sys.executable
            gui_main = os.path.join(project_root, "gui_main.py")
            
            vbs_content = f'''Set WshShell = CreateObject("WScript.Shell")
WshShell.Run chr(34) & "{python_exe}" & chr(34) & " " & chr(34) & "{gui_main}" & chr(34), 0
Set WshShell = Nothing
'''
            with open(shortcut_path, 'w') as f:
                f.write(vbs_content)
            logger.info("Windows startup script created.")
        else:
            if os.path.exists(shortcut_path):
                os.remove(shortcut_path)
                logger.info("Windows startup script removed.")
                
    except Exception as e:
        logger.error(f"Failed to configure Windows startup state: {e}")
