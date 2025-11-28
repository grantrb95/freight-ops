#!/usr/bin/env python3
"""
Initialize the freight operations platform.

This script sets up the project by:
- Creating necessary directories
- Checking for required environment variables
- Validating configuration files
- Setting up the database (if needed)
- Running initial health checks
"""

import os
import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv


def check_python_version() -> bool:
    """Verify Python version is 3.12 or higher."""
    if sys.version_info < (3, 12):
        print(f"❌ Python 3.12+ required. Current version: {sys.version}")
        return False
    print(f"✅ Python version: {sys.version_info.major}.{sys.version_info.minor}")
    return True


def check_env_file() -> bool:
    """Check if .env file exists."""
    env_path = Path(".env")
    if not env_path.exists():
        print("❌ .env file not found")
        print("   Run: cp .env.example .env")
        print("   Then edit .env with your API keys")
        return False
    print("✅ .env file exists")
    return True


def load_and_validate_env() -> bool:
    """Load environment variables and check critical ones."""
    load_dotenv()

    critical_vars = [
        "ANTHROPIC_API_KEY",
        "DAT_API_KEY",
        "TRUCKSTOP_API_KEY",
        "GOOGLE_MAPS_API_KEY",
    ]

    optional_vars = [
        "OPENAI_API_KEY",
        "DATABASE_URL",
        "REDIS_URL",
    ]

    missing = []
    for var in critical_vars:
        value = os.getenv(var)
        if not value or value.startswith("your_") or value.startswith("sk-xxx"):
            missing.append(var)

    if missing:
        print(f"❌ Missing or placeholder API keys: {', '.join(missing)}")
        print("   Edit .env file with actual API keys")
        return False

    print(f"✅ All critical environment variables set")

    # Check optional
    optional_missing = []
    for var in optional_vars:
        value = os.getenv(var)
        if not value or value.startswith("your_") or value.startswith("sk-xxx"):
            optional_missing.append(var)

    if optional_missing:
        print(f"⚠️  Optional variables not set: {', '.join(optional_missing)}")

    return True


def check_config_files() -> bool:
    """Validate configuration files exist and are valid."""
    config_files = {
        "config/config.yaml": "Main configuration",
        "config/llms.json": "LLM configuration",
    }

    for file_path, description in config_files.items():
        path = Path(file_path)
        if not path.exists():
            print(f"❌ {description} not found: {file_path}")
            return False
        print(f"✅ {description} exists")

    # Validate YAML
    try:
        with open("config/config.yaml") as f:
            config = yaml.safe_load(f)
            if not config:
                print("❌ config.yaml is empty")
                return False
            print(f"✅ config.yaml is valid YAML")
    except Exception as e:
        print(f"❌ Error parsing config.yaml: {e}")
        return False

    return True


def create_data_directories() -> bool:
    """Create necessary data directories."""
    directories = [
        "data/cache",
        "data/logs",
        "data/exports",
        "logs",
    ]

    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)

    print(f"✅ Created {len(directories)} data directories")
    return True


def test_imports() -> bool:
    """Test that critical packages can be imported."""
    required_packages = [
        "anthropic",
        "pydantic",
        "yaml",
        "dotenv",
    ]

    missing = []
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing.append(package)

    if missing:
        print(f"❌ Missing packages: {', '.join(missing)}")
        print("   Run: uv sync")
        return False

    print("✅ All required packages installed")
    return True


def display_next_steps():
    """Show user what to do next."""
    print("\n" + "=" * 60)
    print("🎉 Project initialization complete!")
    print("=" * 60)
    print("\nNext steps:")
    print("\n1. Review and customize config/config.yaml for your business")
    print("2. Review agent assignments in config/llms.json")
    print("3. Test the setup:")
    print("   python scripts/test_setup.py")
    print("\n4. Start developing:")
    print("   - Create agents in src/agents/")
    print("   - Add MCP tools in src/tools/")
    print("   - Define data models in src/data/models/")
    print("\n5. Run example notebook:")
    print("   jupyter notebook notebooks/getting_started.ipynb")
    print("\n" + "=" * 60)


def main():
    """Run all initialization checks."""
    print("=" * 60)
    print("Freight Operations Platform - Initialization")
    print("=" * 60)
    print()

    checks = [
        ("Python version", check_python_version),
        (".env file", check_env_file),
        ("Environment variables", load_and_validate_env),
        ("Configuration files", check_config_files),
        ("Data directories", create_data_directories),
        ("Package imports", test_imports),
    ]

    passed = 0
    failed = 0

    for name, check_func in checks:
        print(f"\nChecking {name}...")
        if check_func():
            passed += 1
        else:
            failed += 1

    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)

    if failed == 0:
        display_next_steps()
        return 0
    else:
        print("\n❌ Some checks failed. Please fix the issues above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
