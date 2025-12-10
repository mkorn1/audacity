#!/usr/bin/env python3
"""
Configuration management for AI Chat service
Handles API keys and other configuration
"""

import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# Load .env file from the same directory as this config file
_env_path = Path(__file__).parent / ".env"
load_dotenv(_env_path)


def get_config_value(key: str, default: str = "") -> str:
    """
    Get a configuration value from environment.

    Args:
        key: Environment variable name
        default: Default value if not set

    Returns:
        Configuration value string
    """
    return os.getenv(key, default)


def get_openai_api_key() -> Optional[str]:
    """
    Get OpenAI API key from environment variable

    Returns:
        API key string, or None if not set

    Usage:
        Set the environment variable before running:
        export OPENAI_API_KEY="sk-..."

        Or on Windows:
        set OPENAI_API_KEY=sk-...
    """
    return os.getenv("OPENAI_API_KEY")


def is_openai_configured() -> bool:
    """Check if OpenAI API key is configured"""
    return get_openai_api_key() is not None


def get_whisper_model() -> str:
    """
    Get Whisper model to use for transcription.

    Returns:
        Model name string (default: "whisper-1")
    """
    return os.getenv("WHISPER_MODEL", "whisper-1")


def is_transcription_enabled() -> bool:
    """
    Check if transcription is enabled.
    Requires AssemblyAI API key to be configured.
    """
    return is_assemblyai_configured()


def get_chat_model() -> str:
    """
    Get the OpenAI model to use for chat/intent parsing.

    Returns:
        Model name string (default: "gpt-4o-mini")
    """
    return os.getenv("CHAT_MODEL", "gpt-4o-mini")


# === AssemblyAI Configuration ===

def get_assemblyai_api_key() -> Optional[str]:
    """
    Get AssemblyAI API key from environment variable.

    Returns:
        API key string, or None if not set

    Usage:
        Set the environment variable before running:
        export ASSEMBLYAI_API_KEY="..."

        Or on Windows:
        set ASSEMBLYAI_API_KEY=...
    """
    return os.getenv("ASSEMBLYAI_API_KEY")


def is_assemblyai_configured() -> bool:
    """Check if AssemblyAI API key is configured"""
    return get_assemblyai_api_key() is not None


