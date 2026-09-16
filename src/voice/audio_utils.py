import sounddevice as sd
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

def get_available_microphones() -> List[Dict[str, str]]:
    """
    Returns a list of dictionaries with 'id' and 'name' for each available input device.
    Uses sounddevice to query devices dynamically without blocking the GUI.
    """
    try:
        devices = sd.query_devices()
        input_devices = []
        for i, device in enumerate(devices):
            if device['max_input_channels'] > 0:
                input_devices.append({
                    "id": str(i),
                    "name": device['name']
                })
        return input_devices
    except Exception as e:
        logger.error(f"Error querying audio devices: {e}")
        return []

def get_default_microphone() -> str:
    """Returns the ID of the default microphone, or 'default' if unknown."""
    try:
        default_input = sd.default.device[0]
        if default_input is not None:
            return str(default_input)
    except Exception:
        pass
    return "default"
