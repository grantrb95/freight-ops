"""
Core infrastructure for the freight operations platform.

This module provides:
- Sandbox: Secure execution environment
- MCP Registry: Tool discovery and management
- Config: Configuration management
"""

from .config import ConfigManager, get_config

__all__ = ["ConfigManager", "get_config"]
