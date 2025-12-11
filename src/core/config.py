"""
Configuration management for freight operations platform.

Handles loading and accessing:
- Business configuration (config.yaml)
- LLM configuration (llms.json)
- Environment variables
"""

import json
import os
from pathlib import Path
from typing import Any, Optional

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


class LLMModelConfig(BaseModel):
    """Configuration for a specific LLM model."""

    provider: str
    model: str
    temperature: float = 0.2
    max_tokens: int = 4096
    timeout_seconds: int = 60


class AgentLLMConfig(BaseModel):
    """LLM configuration for a specific agent."""

    primary_model: LLMModelConfig
    fallback_model: Optional[LLMModelConfig] = None
    reasoning: str
    system_prompt_template: str
    tools_enabled: list[str] = Field(default_factory=list)


class EnvironmentSettings(BaseSettings):
    """Environment variables configuration."""

    # LLM Provider API Keys
    anthropic_api_key: Optional[str] = Field(None, alias="ANTHROPIC_API_KEY")
    openai_api_key: Optional[str] = Field(None, alias="OPENAI_API_KEY")

    # Google Maps API
    google_maps_api_key: Optional[str] = Field(None, alias="GOOGLE_MAPS_API_KEY")

    # Load Board APIs
    dat_api_key: Optional[str] = Field(None, alias="DAT_API_KEY")
    truckstop_api_key: Optional[str] = Field(None, alias="TRUCKSTOP_API_KEY")

    # Database
    database_url: str = Field("sqlite:///./freight_ops.db", alias="DATABASE_URL")

    class Config:
        """Pydantic configuration."""

        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


class ConfigManager:
    """
    Central configuration manager for the freight operations platform.

    Loads and provides access to:
    - Business configuration from config/config.yaml
    - LLM configuration from config/llms.json
    - Environment variables from .env
    """

    def __init__(self, config_dir: Optional[Path] = None) -> None:
        """
        Initialize the configuration manager.

        Args:
            config_dir: Optional path to config directory. Defaults to project root/config.
        """
        if config_dir is None:
            # Default to config/ directory in project root
            project_root = Path(__file__).parent.parent.parent
            config_dir = project_root / "config"

        self.config_dir = config_dir
        self._business_config: Optional[dict[str, Any]] = None
        self._llm_config: Optional[dict[str, Any]] = None
        self._env_settings: Optional[EnvironmentSettings] = None

    @property
    def business_config(self) -> dict[str, Any]:
        """Load and return business configuration from config.yaml."""
        if self._business_config is None:
            config_path = self.config_dir / "config.yaml"
            with open(config_path, "r") as f:
                self._business_config = yaml.safe_load(f)
        return self._business_config

    @property
    def llm_config(self) -> dict[str, Any]:
        """Load and return LLM configuration from llms.json."""
        if self._llm_config is None:
            config_path = self.config_dir / "llms.json"
            with open(config_path, "r") as f:
                self._llm_config = json.load(f)
        return self._llm_config

    @property
    def env(self) -> EnvironmentSettings:
        """Load and return environment settings."""
        if self._env_settings is None:
            self._env_settings = EnvironmentSettings()
        return self._env_settings

    def get_agent_llm_config(self, agent_name: str) -> AgentLLMConfig:
        """
        Get LLM configuration for a specific agent.

        Args:
            agent_name: Name of the agent (e.g., "dispatch", "rate_analysis")

        Returns:
            AgentLLMConfig with the agent's LLM settings

        Raises:
            KeyError: If agent configuration is not found
        """
        agent_assignments = self.llm_config.get("agent_assignments", {})
        if agent_name not in agent_assignments:
            raise KeyError(f"No LLM configuration found for agent: {agent_name}")

        agent_config = agent_assignments[agent_name]
        return AgentLLMConfig(**agent_config)

    def get_api_key(self, provider: str) -> Optional[str]:
        """
        Get API key for a specific provider.

        Args:
            provider: Provider name ("anthropic", "openai", "google_maps", etc.)

        Returns:
            API key or None if not set
        """
        provider_map = {
            "anthropic": self.env.anthropic_api_key,
            "openai": self.env.openai_api_key,
            "google_maps": self.env.google_maps_api_key,
            "dat": self.env.dat_api_key,
            "truckstop": self.env.truckstop_api_key,
        }
        return provider_map.get(provider.lower())

    def get_company_info(self) -> dict[str, Any]:
        """Get company information from business config."""
        return self.business_config.get("company", {})

    def get_equipment_config(self) -> dict[str, Any]:
        """Get equipment configuration from business config."""
        return self.business_config.get("equipment", {})

    def get_rate_thresholds(self) -> dict[str, Any]:
        """Get rate thresholds from business config."""
        return self.business_config.get("rates", {})

    def get_operating_costs(self) -> dict[str, Any]:
        """Get operating costs from business config."""
        return self.business_config.get("costs", {})


# Global config instance
_config_manager: Optional[ConfigManager] = None


def get_config() -> ConfigManager:
    """
    Get the global configuration manager instance.

    Returns:
        ConfigManager singleton instance
    """
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager
