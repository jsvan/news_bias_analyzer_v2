"""
Configuration settings for the OpenAI integration and article processing.
"""
import os
from typing import Dict, Any, Optional
import json
from pathlib import Path

# Default configuration
DEFAULT_CONFIG = {
    "openai": {
        "default_model": "gpt-4.1-nano",
        "fallback_model": "gpt-4.1-nano",
        "max_tokens": 4000,
        "temperature": 0.1,
        "batch_size": 5,
        "max_retries": 3,
        "retry_delay": 2,
        "timeout": 60,
        "cost_limits": {
            "daily_limit_usd": 50.0,
            "warn_at_percentage": 80,
            "throttle_requests": True
        }
    },
    "processing": {
        "default_prompt_type": "standard",  # standard, detailed, bias, narrative
        "extract_entities": True,
        "analyze_sentiment": True,
        "detect_bias": False,
        "analyze_narrative": False,
        "max_article_tokens": 8000,
        "min_article_tokens": 100,
        "save_raw_responses": True
    },
    "database": {
        "use_database": True,
        "fallback_to_files": True,
        "file_output_dir": "data/processed_articles"
    },
    "logging": {
        "level": "INFO",
        "log_api_usage": True,
        "log_to_file": True,
        "log_file": "logs/openai_processor.log",
        "rotate_logs": True,
        "max_log_size_mb": 10,
        "log_retention_days": 30
    }
}

class ProcessorConfig:
    """Configuration manager for OpenAI processor."""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize configuration, optionally loading from a file.
        
        Args:
            config_path: Path to JSON configuration file
        """
        self.config = DEFAULT_CONFIG.copy()
        self.config_path = config_path
        
        if config_path:
            self.load_config(config_path)
        
        # Override with environment variables
        self._apply_env_overrides()
    
    def load_config(self, config_path: str) -> None:
        """
        Load configuration from a JSON file.
        
        Args:
            config_path: Path to JSON configuration file
        """
        path = Path(config_path)
        if not path.exists():
            return
        
        try:
            with open(path, 'r') as f:
                user_config = json.load(f)
            
            # Merge with default config
            self._merge_configs(self.config, user_config)
        except Exception as e:
            print(f"Error loading config from {config_path}: {e}")
    
    def _merge_configs(self, base: Dict[str, Any], override: Dict[str, Any]) -> None:
        """
        Recursively merge override config into base config.
        
        Args:
            base: Base configuration dictionary
            override: Override configuration dictionary
        """
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._merge_configs(base[key], value)
            else:
                base[key] = value
    
    def _apply_env_overrides(self) -> None:
        """Apply overrides from environment variables."""
        # OpenAI API key
        if os.getenv("OPENAI_API_KEY"):
            os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")
        
        # OpenAI model
        if os.getenv("OPENAI_MODEL"):
            self.config["openai"]["default_model"] = os.getenv("OPENAI_MODEL")
        
        # Database URL
        if os.getenv("DATABASE_URL"):
            self.config["database"]["use_database"] = True
        
        # Logging level
        if os.getenv("LOG_LEVEL"):
            self.config["logging"]["level"] = os.getenv("LOG_LEVEL")
            
        # Cost limits
        if os.getenv("OPENAI_DAILY_LIMIT"):
            try:
                self.config["openai"]["cost_limits"]["daily_limit_usd"] = float(os.getenv("OPENAI_DAILY_LIMIT"))
            except (ValueError, TypeError):
                pass
    
    def get_openai_config(self) -> Dict[str, Any]:
        """Get OpenAI-specific configuration."""
        return self.config["openai"]
    
    def get_processing_config(self) -> Dict[str, Any]:
        """Get article processing configuration."""
        return self.config["processing"]
    
    def get_database_config(self) -> Dict[str, Any]:
        """Get database configuration."""
        return self.config["database"]
    
    def get_logging_config(self) -> Dict[str, Any]:
        """Get logging configuration."""
        return self.config["logging"]
    
    def get(self, path: str, default: Any = None) -> Any:
        """
        Get a configuration value by path.
        
        Args:
            path: Dot-separated path to configuration value
            default: Default value if path not found
            
        Returns:
            Configuration value or default
        """
        parts = path.split('.')
        value = self.config
        
        try:
            for part in parts:
                value = value[part]
            return value
        except (KeyError, TypeError):
            return default
    
    def set(self, path: str, value: Any) -> None:
        """
        Set a configuration value by path.
        
        Args:
            path: Dot-separated path to configuration value
            value: Value to set
        """
        parts = path.split('.')
        config = self.config
        
        for i, part in enumerate(parts[:-1]):
            if part not in config:
                config[part] = {}
            config = config[part]
        
        config[parts[-1]] = value
    
    def save(self, path: Optional[str] = None) -> None:
        """
        Save configuration to a JSON file.
        
        Args:
            path: Path to save to (if None, use the path from initialization)
        """
        save_path = path or self.config_path
        if not save_path:
            return
        
        try:
            # Create directory if needed
            Path(save_path).parent.mkdir(parents=True, exist_ok=True)
            
            with open(save_path, 'w') as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            print(f"Error saving config to {save_path}: {e}")


# Singleton instance
CONFIG = ProcessorConfig(os.getenv("PROCESSOR_CONFIG_PATH"))

def get_config() -> ProcessorConfig:
    """Get the processor configuration singleton."""
    return CONFIG