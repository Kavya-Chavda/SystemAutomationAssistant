import requests
import json
import logging
from typing import Dict, Any, Optional, Union, List

logger = logging.getLogger(__name__)

class OllamaClient:
    """
    Client for interacting with a local Ollama instance.
    """
    def __init__(self, host: str = "http://localhost:11434", model: str = "gemma3:4b"):
        self.host = host.rstrip('/')
        self.model = model
        self.api_url = f"{self.host}/api/generate"
        self.tags_url = f"{self.host}/api/tags"

    def get_available_models(self) -> List[str]:
        """Queries the Ollama instance for a list of available models."""
        try:
            response = requests.get(self.tags_url, timeout=5)
            response.raise_for_status()
            data = response.json()
            return [m.get("name") for m in data.get("models", []) if m.get("name")]
        except Exception as e:
            logger.error(f"Failed to fetch available models from {self.tags_url}: {e}")
            return []

    def generate(self, prompt: str, system: Optional[str] = None, force_json: bool = True) -> Optional[Union[Dict[str, Any], List[Dict[str, Any]]]]:
        """
        Sends a request to the Ollama API to generate a response based on the prompt.
        Expects a JSON response.
        
        Args:
            prompt: The user input or specific instruction.
            system: Optional system prompt to set the context and behavior.
            force_json: Whether to strictly enforce format: json at the API level.
            
        Returns:
            A parsed JSON dictionary or list of dictionaries, or None if the request/parsing fails.
        """
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False
        }
        if force_json:
            payload["format"] = "json"
        
        if system:
            payload["system"] = system

        try:
            # response = requests.post(self.api_url, json=payload)
            response = requests.post(
                self.api_url,
                json=payload,
                timeout=30
            )
            response.raise_for_status()
            
            result = response.json()
            response_text = result.get("response", "")
            
            # Clean up potential markdown formatting that some models add despite prompt instructions
            response_text = response_text.strip()
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            elif response_text.startswith("```"):
                response_text = response_text[3:]
            
            if response_text.endswith("```"):
                response_text = response_text[:-3]
                
            response_text = response_text.strip()
            logger.debug(f"Raw Response from LLM:\n{response_text}")
            try:
                parsed_json = json.loads(response_text)
                return parsed_json
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON from response. Error: {e}", exc_info=True)
                return {"error": "JSON_DECODE", "message": "Failed to parse JSON"}
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Error communicating with Ollama API at {self.api_url}: {e}", exc_info=True)
            return {"error": "OLLAMA_OFFLINE", "message": str(e)}
        except Exception as e:
            logger.error(f"Unexpected error in OllamaClient: {e}", exc_info=True)
            return {"error": "INTERNAL", "message": str(e)}
