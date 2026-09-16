import logging
from typing import Dict, Any, Union, List

from src.tools.registry import ToolRegistry

# Type hinting
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from src.context.application_state_manager import ApplicationStateManager
    from src.context.context_manager import ContextManager
    from src.context.reference_resolver import ReferenceResolver

logger = logging.getLogger("system_assistant")

class Executor:
    """
    Executes automation actions based on parsed JSON commands dynamically 
    using the ToolRegistry.
    """
    def __init__(self, registry: ToolRegistry, state_manager: 'ApplicationStateManager' = None, context_manager: 'ContextManager' = None, reference_resolver: 'ReferenceResolver' = None, settings_manager=None):
        self.registry = registry
        self.state_manager = state_manager
        self.context_manager = context_manager
        self.reference_resolver = reference_resolver
        self.settings = settings_manager
        self.on_step_start = None
        self.confirmation_callback = None

    def set_confirmation_callback(self, callback):
        self.confirmation_callback = callback

    def _sync_active_apps(self) -> None:
        if self.state_manager and self.context_manager:
            self.context_manager.sync_active_apps(
                self.state_manager.get_current_active_app(),
                self.state_manager.get_last_active_app()
            )

    def execute(self, command_json: Union[Dict[str, Any], List[Dict[str, Any]]], stop_on_failure: bool = True) -> Dict[str, Any]:
        """
        Routes the parsed JSON command(s) to the appropriate Tool in the registry.
        """
        if isinstance(command_json, list):
            return self._execute_queue(command_json, stop_on_failure)

        return self._execute_single(command_json)

    def _execute_single(self, command_json: Dict[str, Any], is_part_of_queue: bool = False) -> Dict[str, Any]:
        action = command_json.get("action")
        parameters = command_json.get("parameters", {})
        
        if not is_part_of_queue and self.on_step_start:
            self.on_step_start(self._get_action_description(command_json))

        if not action or action == "unknown":
            return {
                "status": "failed", 
                "title": "Unknown Action",
                "message": "Unknown or unsupported action.",
                "metadata": {},
                "suggestions": []
            }
            
        if action == "unsupported":
            msg = parameters.get("message", "This action is not supported.")
            return {
                "status": "failed", 
                "title": "Unsupported Action",
                "message": msg,
                "metadata": {},
                "suggestions": []
            }

        try:
            if action == "error":
                return {
                    "status": "failed",
                    "error_type": parameters.get("error_type", "INTERNAL"),
                    "title": parameters.get("title", "Error"),
                    "message": parameters.get("message", "An unexpected error occurred."),
                    "suggestions": parameters.get("suggestions", [])
                }
                
            if action == "clarify":
                # The Planner has requested clarification from the user
                message = parameters.get("message", "Could you please clarify your request?")
                return {"status": "success", "message": f"Clarification needed: {message}"}
                
            if action == "resolve_disambiguation":
                if self.context_manager:
                    pending = self.context_manager.state.get("pending_disambiguation")
                    if pending:
                        selected_index = parameters.get("selected_index")
                        matches = pending.get("matches", [])
                        if 1 <= selected_index <= len(matches):
                            selected_match = matches[selected_index - 1]
                            target_key = pending.get("target_key", "item_name")
                            
                            # Reconstruct command
                            reconstructed_cmd = {
                                "action": pending["action"],
                                "parameters": pending["parameters"]
                            }
                            reconstructed_cmd["parameters"][target_key] = selected_match
                            
                            # Clear state
                            self.context_manager.state["pending_disambiguation"] = None
                            self.context_manager.save()
                            
                            # Recursively execute
                            return self._execute_single(reconstructed_cmd, is_part_of_queue=is_part_of_queue)
                        else:
                            return {"status": "failed", "message": f"Invalid selection.\nPlease choose a number between 1 and {len(matches)}."}
                return {"status": "failed", "message": "No pending disambiguation state found."}
                
            if action == "unsupported_feature":
                feature = parameters.get("feature")
                if feature == "night_light":
                    return {
                        "status": "failed",
                        "message": "Windows Night Light cannot be controlled safely through documented Windows APIs. This feature is intentionally unsupported."
                    }
                return {
                    "status": "failed",
                    "message": "This feature is intentionally unsupported."
                }
                
            if action == "debug_context":
                if self.context_manager:
                    snapshot = self.context_manager.get_context_snapshot()
                    fs_state = snapshot.get("filesystem_state", {})
                    sys_state = snapshot.get("system_state", {})
                    
                    app_active = snapshot.get("current_active_app") or "None"
                    app_opened = snapshot.get("last_opened_app") or "None"
                    app_focused = snapshot.get("last_focused_app") or "None"
                    
                    file_created = fs_state.get("last_created_file") or "None"
                    folder_created = fs_state.get("last_created_folder") or "None"
                    file_found = fs_state.get("last_found_file") or "None"
                    
                    vol = sys_state.get("volume_level")
                    vol_str = f"{vol}%" if vol is not None else "Unknown"
                    bright = sys_state.get("brightness_level")
                    bright_str = f"{bright}%" if bright is not None else "Unknown"
                    wifi = sys_state.get("wifi_connected")
                    wifi_str = "Connected" if wifi else ("Disconnected" if wifi is False else "Unknown")
                    power = sys_state.get("power_plan") or "Unknown"
                    res = sys_state.get("primary_resolution") or "Unknown"
                    
                    msg = (
                        "**Application**\n"
                        f"• Active Window: {app_active}\n"
                        f"• Last Opened: {app_opened}\n"
                        f"• Last Focused: {app_focused}\n\n"
                        "**Files**\n"
                        f"• Last Created File: {file_created}\n"
                        f"• Last Created Folder: {folder_created}\n"
                        f"• Last Found File: {file_found}\n\n"
                        "**System**\n"
                        f"• Volume: {vol_str}\n"
                        f"• Brightness: {bright_str}\n"
                        f"• Wi-Fi: {wifi_str}\n"
                        f"• Power Plan: {power}\n"
                        f"• Resolution: {res}"
                    )
                    
                    return {
                        "status": "success", 
                        "title": "Current Session", 
                        "message": msg,
                        "suggestions": ["Show system state", "Clear context"]
                    }
                else:
                    return {"status": "failed", "title": "Context Unavailable", "message": "ContextManager not initialized."}
                    
            if action == "debug_state":
                if self.state_manager:
                    import json
                    self.state_manager.refresh_all()
                    self._sync_active_apps()
                    snapshot = self.state_manager.states
                    def _serialize(obj):
                        if hasattr(obj, 'isoformat'): return obj.isoformat()
                        return str(obj)
                    formatted = json.dumps(snapshot, indent=2, default=_serialize)
                    return {"status": "success", "title": "System State Snapshot", "message": f"State Snapshot:\n{formatted}"}
                else:
                    return {"status": "failed", "title": "State Unavailable", "message": "ApplicationStateManager not initialized."}
                    
            if action == "get_current_app":
                if self.state_manager:
                    self.state_manager.refresh_active_window()
                    self._sync_active_apps()
                    current = self.state_manager.get_current_active_app()
                    if current:
                        return {"status": "success", "title": "Current Application", "message": f"The currently active application is {current}."}
                    return {"status": "success", "title": "Current Application", "message": "No active application is currently being tracked."}
                return {"status": "failed", "title": "System Error", "message": "ApplicationStateManager not initialized."}
                
            if action == "get_previous_app":
                if self.state_manager:
                    app = self.state_manager.get_last_active_app()
                    if app:
                        return {"status": "success", "title": "Previous Application", "message": f"The previously active application was {app}."}
                    return {"status": "success", "title": "Previous Application", "message": "No previous application is being tracked."}
                return {"status": "failed", "title": "System Error", "message": "ApplicationStateManager not initialized."}
                
            if action == "get_opened_history":
                if self.context_manager:
                    history = self.context_manager.get_open_history()
                    if history:
                        msg = "Opened Apps History:\n" + "\n".join(f"{i+1}. {app}" for i, app in enumerate(history))
                        return {"status": "success", "message": msg}
                    return {"status": "success", "message": "Opened Apps History:\nNo apps have been opened yet."}
                return {"status": "failed", "message": "ContextManager not initialized."}
                
            if action == "get_focused_history":
                if self.context_manager:
                    history = self.context_manager.get_focus_history()
                    if history:
                        msg = "Focused Apps History:\n" + "\n".join(f"{i+1}. {app}" for i, app in enumerate(history))
                        return {"status": "success", "message": msg}
                    return {"status": "success", "message": "Focused Apps History:\nNo apps have been focused yet."}
                return {"status": "failed", "message": "ContextManager not initialized."}
                
            if action == "get_closed_history":
                if self.context_manager:
                    history = self.context_manager.get_close_history()
                    if history:
                        msg = "Closed Apps History:\n" + "\n".join(f"{i+1}. {app}" for i, app in enumerate(history))
                        return {"status": "success", "message": msg}
                    return {"status": "success", "message": "Closed Apps History:\nNo apps have been closed yet."}
                return {"status": "failed", "message": "ContextManager not initialized."}
                
            if action == "reject_custom_path":
                return {"status": "failed", "message": "Custom filesystem locations are not supported yet. All files and folders are created inside automation_workspace."}
                    
            # State-Aware Validation Intercepts
            
            # --- START CONFIRMATION INTERCEPTS ---
            requires_confirmation = False
            confirm_title = "Confirm Action"
            confirm_msg = "Are you sure you want to proceed?"
            
            is_manual_mode = self.settings and self.settings.get("automation", "execution_mode") == "manual"
            
            if is_manual_mode:
                requires_confirmation = True
                confirm_title = "Manual Execution Mode"
                confirm_msg = f"Allow execution of: {action}?"
            elif self.settings:
                if action == "delete_item" and self.settings.get("automation", "confirm_delete"):
                    requires_confirmation = True
                    confirm_title = "Confirm Delete"
                    item = parameters.get("item_name", "this item")
                    confirm_msg = f"Are you sure you want to delete '{item}'?"
                elif action in ["shutdown_pc", "restart_pc"] and self.settings.get("automation", "confirm_shutdown_restart"):
                    requires_confirmation = True
                    confirm_title = "Confirm Power Action"
                    confirm_msg = f"Are you sure you want to {action.split('_')[0]} the PC?"
                # Bulk file operations - copy_file/move_file are mostly single files right now, 
                # but if we add bulk in future we can intercept here.
                    
            if requires_confirmation and self.confirmation_callback:
                # Pause and wait for GUI to return a boolean
                approved = self.confirmation_callback(confirm_title, confirm_msg)
                if not approved:
                    return {
                        "status": "cancelled",
                        "title": "Action Cancelled",
                        "message": "The action was cancelled by the user."
                    }
            # --- END CONFIRMATION INTERCEPTS ---
            
            if action == "open_application":
                app_name = parameters.get("application_name")
                if self.state_manager and app_name:
                    self.state_manager.refresh_app_state(app_name)
                    if self.state_manager.is_running(app_name):
                        logger.info(f"{app_name.title()} is already running. Skipping execution.")
                        if self.context_manager:
                            self.context_manager.mark_action_success(action)
                            self.context_manager.mark_app_opened(app_name)
                        return {"status": "info", "title": "Application Already Running", "message": f"{app_name.title()} is already running."}
                        
            elif action == "close_application":
                app_name = parameters.get("application_name")
                if self.state_manager and app_name:
                    self.state_manager.refresh_app_state(app_name)
                    if not self.state_manager.is_running(app_name):
                        logger.info(f"{app_name.title()} is already closed. Skipping execution.")
                        if self.context_manager:
                            self.context_manager.mark_action_success(action)
                            self.context_manager.mark_app_closed(app_name)
                        return {"status": "info", "title": "Application Not Running", "message": f"{app_name.title()} is already closed."}
                        
            elif action == "focus_window":
                window_name = parameters.get("window_name")
                if self.state_manager and window_name:
                    self.state_manager.refresh_app_state(window_name)
                    self._sync_active_apps()
                    if self.state_manager.is_focused(window_name):
                        logger.info(f"{window_name.title()} is already focused. Skipping execution.")
                        if self.context_manager:
                            self.context_manager.mark_action_success(action)
                            self.context_manager.mark_app_focused(window_name)
                        return {"status": "info", "title": "Window Already Focused", "message": f"{window_name.title()} is already the active window."}
                
            if action == "confirm_power_action":
                if self.context_manager:
                    snapshot = self.context_manager.get_context_snapshot()["system_state"]
                    parameters["pending_action"] = snapshot.get("pending_power_action")
                    
            # Execute dynamically via Tool Registry
            result = self.registry.execute_tool(action, context_manager=self.context_manager, **parameters)
            
            # Intercept ambiguous results from tools
            if result.get("status") == "ambiguous":
                if self.context_manager:
                    import datetime
                    
                    # Try to reconstruct the original prompt if it was stored in ContextManager earlier
                    # But the engine usually already updated last_command!
                    prompt = self.context_manager.state.get("last_command", f"{action} operation")
                    
                    self.context_manager.state["pending_disambiguation"] = {
                        "action": action,
                        "parameters": parameters,
                        "matches": result.get("matches", []),
                        "target_key": result.get("target_key", "item_name"),
                        "created_at": datetime.datetime.now().isoformat(),
                        "prompt": prompt
                    }
                    self.context_manager.save()
                    
                    matches_str = "\n".join(f"{i+1}. {m}" for i, m in enumerate(result.get("matches", [])))
                    result["message"] = f"I found {len(result.get('matches', []))} matching items."
                    result["status"] = "interactive"
                    result["title"] = "Multiple Matches Found"
                    return result
            
            # Fallback logic for open_application
            if action == "open_application" and result.get("status") == "application_not_found":
                fallback_url = parameters.get("fallback_url")
                if fallback_url:
                    logger.info(f"Application not found. Executing fallback URL: {fallback_url}")
                    result = self.registry.execute_tool("open_url", url=fallback_url)
                    # Modify message to indicate fallback
                    if result.get("status") == "success":
                        result["message"] = f"Application not found. Opened fallback website: {fallback_url}"
                        # If we fallback, the action effectively becomes open_url
                        action = "open_url"
                        parameters = {"url": fallback_url}

            if result.get("status") == "success":
                # Handle fallback scenarios where open_application turns into open_url
                if action == "open_application" and "fallback" in result.get("message", "").lower():
                    action = "open_url"
                    
            if result.get("status") in ["success", "partial_success", "info"]:
                if self.context_manager:
                    self.context_manager.mark_action_success(action)
                    if action in ["create_folder", "create_file", "rename_item", "copy_file", "move_file", "open_workspace_item", "open_folder", "open_file"]:
                        # Handle filesystem context
                        item_name = result.get("item_name")
                        if item_name:
                            if action == "create_folder":
                                self.context_manager.update_filesystem_state("last_created_folder", item_name)
                            elif action == "create_file":
                                self.context_manager.update_filesystem_state("last_created_file", item_name)
                            elif action in ["open_workspace_item", "open_folder"]:
                                self.context_manager.update_filesystem_state("last_opened_folder", item_name)
                
                if action == "open_application":
                    app_name = parameters.get("application_name")
                    if self.state_manager:
                        self.state_manager.refresh_app_state(app_name)
                    if self.context_manager and app_name:
                        self.context_manager.mark_app_opened(app_name)
                elif action == "close_application":
                    app_name = parameters.get("application_name")
                    if self.state_manager:
                        self.state_manager.refresh_app_state(app_name)
                    if self.context_manager and app_name:
                        self.context_manager.mark_app_closed(app_name)
                elif action in ["focus_window", "minimize_window", "maximize_window", "restore_window"]:
                    window_name = parameters.get("window_name")
                    if self.state_manager and window_name:
                        self.state_manager.mark_focused(window_name)
                        self._sync_active_apps()
                    if self.context_manager and window_name:
                        self.context_manager.mark_app_focused(window_name)
                        
                if action in ["minimize_window", "maximize_window", "restore_window", "get_current_window", "list_open_windows"]:
                    if self.context_manager:
                        if "window" in result:
                            win = result["window"]
                            self.context_manager.update_system_state("current_window_title", win.get("title", ""))
                            self.context_manager.update_system_state("current_window_app", win.get("app_name", ""))
                            self.context_manager.update_system_state("current_window_handle", win.get("hwnd", 0))
                        
                        if action in ["minimize_window", "maximize_window", "restore_window", "focus_window"]:
                            action_type = action.split('_')[0]
                            self.context_manager.update_system_state("last_window_action", action_type)
                            
                        if "count" in result:
                            self.context_manager.update_system_state("open_windows_count", result["count"])
                
                elif action in ["mute_volume", "unmute_volume", "increase_volume", "decrease_volume", "set_volume", "volume_status"]:
                    if self.context_manager and "volume_level" in result and "is_muted" in result:
                        self.context_manager.update_system_state("volume_level", result["volume_level"])
                        self.context_manager.update_system_state("is_muted", result["is_muted"])
                        
                elif action in ["increase_brightness", "decrease_brightness", "set_brightness", "brightness_status"]:
                    if self.context_manager and "brightness_level" in result:
                        self.context_manager.update_system_state("brightness_level", result["brightness_level"])
                        
                elif action == "display_status":
                    if self.context_manager and "display_monitor_count" in result:
                        self.context_manager.update_system_state("display_monitor_count", result.get("display_monitor_count"))
                        self.context_manager.update_system_state("primary_resolution", result.get("primary_resolution"))
                        self.context_manager.update_system_state("primary_refresh_rate", result.get("primary_refresh_rate"))
                        
                elif action in ["enable_wifi", "disable_wifi", "wifi_status"]:
                    if self.context_manager and "wifi_enabled" in result:
                        self.context_manager.update_system_state("wifi_enabled", result.get("wifi_enabled"))
                        self.context_manager.update_system_state("wifi_connected", result.get("wifi_connected"))
                        self.context_manager.update_system_state("wifi_name", result.get("wifi_name"))
                
                elif action == 'hotspot_status':
                    if self.context_manager and 'hotspot_enabled' in result:
                        self.context_manager.update_system_state("hotspot_enabled", result['hotspot_enabled'])
                elif action in ['battery_saver_status', 'list_power_profiles', 'power_status', 'set_power_mode']:
                    if self.context_manager:
                        if 'battery_saver_enabled' in result:
                            self.context_manager.update_system_state("battery_saver_enabled", result['battery_saver_enabled'])
                        if 'power_plan' in result:
                            self.context_manager.update_system_state("power_plan", result['power_plan'])
                        if 'available_power_profiles' in result:
                            self.context_manager.update_system_state("available_power_profiles", result['available_power_profiles'])
                
                elif action in ["shutdown_pc", "restart_pc"]:
                    if self.context_manager and "pending_power_action" in result:
                        self.context_manager.update_system_state("pending_power_action", result["pending_power_action"])
                        
                elif action in ["sleep_pc", "lock_screen", "confirm_power_action"]:
                    if self.context_manager and result.get("status") == "success":
                        if "last_power_action" in result:
                            self.context_manager.update_system_state("last_power_action", result["last_power_action"])
                        if result.get("clear_pending"):
                            self.context_manager.update_system_state("pending_power_action", None)
                            
                elif action == "cancel_power_action":
                    if self.context_manager and result.get("clear_pending"):
                        self.context_manager.update_system_state("pending_power_action", None)
                    result["status"] = "cancelled"
                    result["title"] = "Operation Cancelled"
                    result["message"] = "The power action was cancelled.\nNothing has been changed."
                
                elif action == "get_current_window":
                    if self.state_manager:
                        self.state_manager.refresh_active_window()
                        self._sync_active_apps()
                    title = result.get("window", {}).get("title")
                    if self.context_manager and title:
                        self.context_manager.update_active_window(title)
            
            if result.get("status") not in ["success", "completed", "partial_success", "interactive", "info", "cancelled"]:
                if self.context_manager:
                    self.context_manager.mark_action_failed(action)
            
            # Inject action name to result for formatting if not explicitly passed
            if "action" not in result:
                result["action"] = action
                
            return result
        except Exception as e:
            if self.context_manager:
                self.context_manager.mark_action_failed(action)
            logger.error(f"Error executing {action}: {e}", exc_info=True)
            return {
                "status": "failed", 
                "title": "System Error",
                "message": f"The automation engine encountered a technical error while executing '{action.replace('_', ' ')}'.",
                "suggestions": [
                    "Try repeating the command",
                    "Try rephrasing your request",
                    "Ensure you have necessary permissions"
                ]
            }

    def _get_action_description(self, cmd: Dict[str, Any]) -> str:
        action = cmd.get("action", "unknown")
        params = cmd.get("parameters", {})
        
        if action == "open_application":
            app_name = params.get("application_name", "Application")
            return f"Opening {app_name.title()}"
        elif action == "close_application":
            app_name = params.get("application_name", "Application")
            return f"Closing {app_name.title()}"
        elif action == "search_web":
            return f"Searching web for '{params.get('query', '')}'"
        elif action == "get_current_window":
            return "Getting current window status"
        elif action == "is_window_open":
            return f"Checking if {params.get('window_name', 'window')} is open"
        elif action == "focus_window":
            return f"Focusing window: {params.get('window_name', 'window').title()}"
        elif action == "minimize_window":
            return f"Minimizing window: {params.get('window_name', 'window').title()}"
        elif action == "maximize_window":
            return f"Maximizing window: {params.get('window_name', 'window').title()}"
        elif action == "restore_window":
            return f"Restoring window: {params.get('window_name', 'window').title()}"

        elif action == "list_open_windows":
            return "Listing open windows"
        elif action == "wait":
            wait_type = params.get("wait_type", "seconds")
            if wait_type == "seconds":
                return f"Waiting {params.get('seconds', 0)} seconds..."
            elif wait_type == "window":
                window_name = params.get("window_name", "window").title()
                timeout = params.get("timeout", 30)
                return f"Waiting for {window_name} window (timeout {timeout}s)..."
            elif wait_type == "window_closed":
                window_name = params.get("window_name", "window").title()
                timeout = params.get("timeout", 30)
                return f"Waiting for {window_name} window to close (timeout {timeout}s)..."
            elif wait_type == "app":
                app_name = params.get("app_name", "app").title()
                timeout = params.get("timeout", 30)
                return f"Waiting for {app_name} application (timeout {timeout}s)..."
            elif wait_type == "app_closed":
                app_name = params.get("app_name", "app").title()
                timeout = params.get("timeout", 30)
                return f"Waiting for {app_name} application to close (timeout {timeout}s)..."
        elif action == "create_folder":
            return f"Creating folder '{params.get('folder_name', 'folder')}'"
        elif action == "create_file":
            return f"Creating file '{params.get('file_name', 'file')}'"
        elif action == "rename_item":
            return f"Renaming '{params.get('source_name', '')}' to '{params.get('target_name', '')}'"
        elif action == "delete_item":
            return f"Deleting '{params.get('item_name', '')}'"
        elif action == "copy_file":
            return f"Copying '{params.get('source_name', '')}' to '{params.get('target_name', '')}'"
        elif action == "move_file":
            return f"Moving '{params.get('source_name', '')}' to '{params.get('target_path', '')}'"
        elif action == "open_workspace_item":
            return f"Opening workspace item '{params.get('item_name', '')}'"
        elif action == "reject_custom_path":
            return "Rejecting custom filesystem path"
        elif action == "mute_volume":
            return "Muting system volume"
        elif action == "unmute_volume":
            return "Unmuting system volume"
        elif action == "increase_volume":
            return "Increasing system volume" # Executor doesn't have old_vol/new_vol here since it's just desc, but wait. _execute_single gets the result *after* _get_action_description. So we can't easily put it in _get_action_description. Let's just return "Increasing system volume". Actually, the result message has it, so the result message prints "Volume increased successfully." I will modify the message from the tool.
        elif action == "decrease_volume":
            return "Decreasing system volume"
        elif action == "set_volume":
            return f"Setting volume to {params.get('level', 0)}%"
        elif action == "volume_status":
            return "Getting volume status"
        elif action == "increase_brightness":
            return "Increasing brightness"
        elif action == "decrease_brightness":
            return "Decreasing brightness"
        elif action == "set_brightness":
            return f"Setting brightness to {params.get('level', 0)}%"
        elif action == "brightness_status":
            return "Getting brightness status"
        elif action == "display_status":
            cmd = self.context_manager.state.get("last_command", "").lower()
            if "primary" in cmd:
                return "Getting primary monitor information"
            elif "monitor" in cmd:
                return "Getting monitor information"
            return "Getting display status"
        elif action == "enable_wifi":
            return "Enabling WiFi"
        elif action == "disable_wifi":
            return "Disabling WiFi"
        elif action == "wifi_status":
            return "Getting WiFi status"
        elif action == "wifi_debug":
            return "Running WiFi diagnostics"
        elif action == "hotspot_status":
            return "Getting Mobile Hotspot status"
        elif action == "battery_saver_status":
            return "Getting Battery Saver status"
        elif action == "list_power_profiles":
            return "Listing available power profiles"
        elif action == "power_status":
            return "Getting current power status"
        elif action == "set_power_mode":
            mode = params.get('mode', 'unknown')
            return f"Switching to {mode.title()} power mode"
        elif action == "shutdown_pc":
            return "Initiating PC shutdown"
        elif action == "restart_pc":
            return "Initiating PC restart"
        elif action == "sleep_pc":
            return "Putting PC to sleep"
        elif action == "lock_screen":
            return "Locking screen"
        elif action == "confirm_power_action":
            action_type = params.get("action_type", "unknown")
            return f"Confirming pending {action_type}"
        elif action == "cancel_power_action":
            return "Cancelling pending power action"
        elif action == "unsupported_feature":
            feature_name = params.get('feature', 'unknown')
            if feature_name == "bluetooth":
                return "Bluetooth toggling requires Administrator privileges and is intentionally unsupported."
            elif feature_name == "hotspot":
                return "Mobile Hotspot control requires Administrator privileges and is intentionally unsupported."
            elif feature_name == "airplane_mode":
                return "Airplane Mode control requires Administrator privileges and is intentionally unsupported."
            elif feature_name == "battery_saver":
                return "Battery Saver toggling requires Administrator privileges and is intentionally unsupported."
            elif feature_name == "fan_mode":
                return "Fan mode telemetry is vendor-specific and is intentionally unsupported."
            return f"Intercepting unsupported feature: {feature_name}"
        else:
            return f"Executing {action.replace('_', ' ').title()}"

    def _execute_queue(self, commands: List[Dict[str, Any]], stop_on_failure: bool = True) -> Dict[str, Any]:
        total_steps = len(commands)
        successful = 0
        failed = 0
        results = []

        for i, cmd in enumerate(commands, 1):

            action = cmd.get("action", "unknown")
            desc = self._get_action_description(cmd)
            
            logger.info(f"Queue step {i}/{total_steps}: {desc}")
            
            if self.on_step_start:
                self.on_step_start(desc)
            
            result = self._execute_single(cmd, is_part_of_queue=True)
            
            is_success = result.get("status") in ["success", "completed", "partial_success", "info", "interactive"]
            
            if is_success:
                successful += 1
                logger.info(f"Queue step {i} success: {result.get('message', '')}")
            else:
                failed += 1
                logger.error(f"Queue step {i} failed: {result.get('message', 'Unknown error')}", exc_info=True)
                
            results.append({
                "step": i,
                "action": action,
                "result": result
            })
            
            if not is_success and stop_on_failure:
                logger.warning(f"Queue aborted at step {i} due to failure.")
                break

        return {
            "status": "completed" if failed == 0 else ("failed" if stop_on_failure else "partial_success"),
            "total_steps": total_steps,
            "successful": successful,
            "failed": failed,
            "results": results,
            "aborted": failed > 0 and stop_on_failure
        }
