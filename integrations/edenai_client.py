"""
EdenAI LLM client for the Medical Prescription System.
Handles API calls to EdenAI for LLM-based operations.
"""

import json
import time
from typing import Optional

import requests

from shared.config import Config


class EdenAIClient:
    """
    Client for calling EdenAI LLM API.
    """
    
    def __init__(self, config: Optional[Config] = None):
        """
        Initialize EdenAI client.
        
        Args:
            config: Configuration object. If None, uses singleton instance.
        """
        self.config = config or Config.get_instance()
        self.base_url = self.config.edenai.base_url
        self.api_key = self.config.edenai.api_key
        self.model = self.config.edenai.model
        
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
    
    def call_llm(
        self, 
        prompt: str, 
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 2000,
        retries: int = 3
    ) -> str:
        """
        Call the LLM with a prompt.
        
        Args:
            prompt: User message/prompt
            system_prompt: Optional system message for context
            temperature: Sampling temperature (lower = more deterministic)
            max_tokens: Maximum tokens in response
            retries: Number of retry attempts on failure
            
        Returns:
            LLM response text
            
        Raises:
            Exception: If all retries fail
        """
        messages = []
        
        if system_prompt:
            messages.append({
                "role": "system",
                "content": system_prompt
            })
        
        messages.append({
            "role": "user", 
            "content": prompt
        })
        
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        
        last_error = None
        for attempt in range(retries):
            try:
                response = requests.post(
                    self.base_url,
                    headers=self.headers,
                    json=payload,
                    timeout=60
                )
                response.raise_for_status()
                
                data = response.json()
                
                # Extract content from response
                # EdenAI follows OpenAI format
                if "choices" in data and len(data["choices"]) > 0:
                    return data["choices"][0]["message"]["content"]
                else:
                    raise ValueError(f"Unexpected response format: {data}")
                    
            except requests.exceptions.RequestException as e:
                last_error = e
                if attempt < retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                continue
            except (KeyError, IndexError, ValueError) as e:
                last_error = e
                break
        
        raise Exception(f"LLM call failed after {retries} attempts: {last_error}")
    
    def call_llm_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.2
    ) -> dict:
        """
        Call LLM and parse response as JSON.
        
        Args:
            prompt: User message (should request JSON output)
            system_prompt: Optional system message
            temperature: Lower for more consistent JSON
            
        Returns:
            Parsed JSON as dictionary
        """
        # Add JSON instruction if not in system prompt
        if system_prompt:
            system_prompt = system_prompt + "\n\nIMPORTANT: Respond ONLY with valid JSON, no additional text."
        else:
            system_prompt = "You are a helpful assistant. Respond ONLY with valid JSON, no additional text."
        
        response = self.call_llm(prompt, system_prompt, temperature)
        
        # Try to extract JSON from response
        response = response.strip()
        
        # Handle markdown code blocks
        if response.startswith("```json"):
            response = response[7:]
        elif response.startswith("```"):
            response = response[3:]
        if response.endswith("```"):
            response = response[:-3]
        
        response = response.strip()
        
        try:
            return json.loads(response)
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse LLM response as JSON: {e}\nResponse was: {response[:500]}")
