# config/config_manager.py
"""
Configuration Manager for iMat – reads settings from JSON and environment.
Provides a single access point for all application settings.
"""

import os
import json
from typing import Any, Dict, Optional
from pathlib import Path


class ConfigManager:
    """Central configuration manager with dot-notation access."""

    _instance = None
    _config: Dict[str, Any] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load_all()
        return cls._instance

    def _load_all(self) -> None:
        """Load all configuration sources."""
        self._config = {}
        self._load_json_config()
        self._load_env_file()
        self._load_env_vars()

    def _load_json_config(self) -> None:
        """Load settings from app_config.json."""
        config_dir = Path(__file__).parent
        config_file = config_dir / "app_config.json"

        if config_file.exists():
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    self._config.update(json.load(f))
            except (json.JSONDecodeError, IOError):
                pass  # Silently ignore malformed config

    def _load_env_file(self) -> None:
        """Load settings from .env file."""
        config_dir = Path(__file__).parent
        env_file = config_dir / ".env"

        if env_file.exists():
            try:
                with open(env_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#') and '=' in line:
                            key, value = line.split('=', 1)
                            key = key.strip().lower()
                            value = value.strip().strip('"').strip("'")
                            # Map env vars to config keys
                            self._config[key] = self._parse_value(value)
            except IOError:
                pass

    def _load_env_vars(self) -> None:
        """Override with system environment variables."""
        for key, value in os.environ.items():
            if key.startswith('IMAT_'):
                config_key = key[5:].lower()
                self._config[config_key] = self._parse_value(value)

    @staticmethod
    def _parse_value(value: str) -> Any:
        """Convert string to appropriate Python type."""
        # Boolean
        if value.lower() in ('true', 'yes', '1'):
            return True
        if value.lower() in ('false', 'no', '0'):
            return False
        # Integer
        try:
            return int(value)
        except ValueError:
            pass
        # Float
        try:
            return float(value)
        except ValueError:
            pass
        # String
        return value

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value using dot notation.
        Example: config.get('auto_backup.enabled')
        """
        keys = key.split('.')
        value = self._config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
                if value is None:
                    return default
            else:
                return default
        return value

    def set(self, key: str, value: Any) -> None:
        """
        Set a configuration value using dot notation.
        Example: config.set('auto_backup.enabled', True)
        """
        keys = key.split('.')
        target = self._config
        for k in keys[:-1]:
            if k not in target:
                target[k] = {}
            target = target[k]
        target[keys[-1]] = value

    def get_all(self) -> Dict[str, Any]:
        """Return all configuration as a flat dictionary."""
        return self._config.copy()

    def reload(self) -> None:
        """Force reload all configuration."""
        self._load_all()

    def save_json(self) -> bool:
        """Save current configuration back to app_config.json."""
        config_dir = Path(__file__).parent
        config_file = config_dir / "app_config.json"
        try:
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(self._config, f, indent=4, ensure_ascii=False)
            return True
        except IOError:
            return False

    # ------------------------------------------------------------------
    # Convenience shortcuts
    # ------------------------------------------------------------------
    @property
    def company(self) -> str:
        return self.get('company', 'iMat International')

    @property
    def project_name(self) -> str:
        return self.get('project_name', 'Default Project')

    @property
    def project_code(self) -> str:
        return self.get('project_code', '001')

    @property
    def version(self) -> str:
        return self.get('version', '2.0.0')

    @property
    def is_license_required(self) -> bool:
        return self.get('license_required', True)

    @property
    def default_theme(self) -> str:
        return self.get('default_theme', 'light')

    @property
    def openai_api_key(self) -> str:
        return self.get('openai_api_key', '')

    @property
    def is_ai_enabled(self) -> bool:
        return self.get('ai.enabled', False)

    @property
    def database_path(self) -> str:
        return self.get('database.path', 'aimat.db')


# ------------------------------------------------------------------
# Global instance
# ------------------------------------------------------------------
config = ConfigManager()