"""
Configuration management for the Medical Prescription System.
Loads environment variables from .env file.
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv(path=None):
        """Fallback if python-dotenv not installed"""
        pass


@dataclass
class Neo4jConfig:
    """Neo4j connection configuration"""
    uri: str
    user: str
    password: str


@dataclass
class EdenAIConfig:
    """EdenAI API configuration"""
    api_key: str
    model: str
    base_url: str = "https://api.edenai.run/v3/llm/chat/completions"


class Config:
    """Central configuration class that loads all settings from environment"""
    
    _instance: Optional['Config'] = None
    
    def __init__(self, env_path: Optional[Path] = None):
        """
        Initialize configuration from environment variables.
        
        Args:
            env_path: Optional path to .env file. If None, searches in current 
                     directory and parent directories.
        """
        # Load .env file
        if env_path:
            load_dotenv(env_path)
        else:
            # Try to find .env in project root
            current = Path(__file__).parent.parent
            env_file = current / ".env"
            if env_file.exists():
                load_dotenv(env_file)
            else:
                load_dotenv()  # Try default locations
        
        # Neo4j configuration
        self.neo4j = Neo4jConfig(
            uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
            user=os.getenv("NEO4J_USER", "neo4j"),
            password=os.getenv("NEO4J_PASSWORD", "")
        )
        
        # EdenAI configuration
        self.edenai = EdenAIConfig(
            api_key=os.getenv("EDENAI_API_KEY", ""),
            model=os.getenv("EDENAI_MODEL", "openai/gpt-4o")
        )
    
    @classmethod
    def get_instance(cls, env_path: Optional[Path] = None) -> 'Config':
        """Get singleton instance of Config"""
        if cls._instance is None:
            cls._instance = cls(env_path)
        return cls._instance
    
    def validate(self) -> list[str]:
        """
        Validate that all required configuration is present.
        
        Returns:
            List of missing/invalid configuration keys
        """
        errors = []
        
        if not self.neo4j.password:
            errors.append("NEO4J_PASSWORD is not set")
        
        if not self.edenai.api_key:
            errors.append("EDENAI_API_KEY is not set")
        
        return errors
