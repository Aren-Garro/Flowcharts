"""Python version compatibility checker.

This module ensures the application runs on compatible Python versions.
Python 3.14+ has breaking changes in Pydantic v1 that affect spaCy.
"""

import sys
import warnings
from typing import Tuple

MIN_PYTHON_VERSION = (3, 9)
MAX_PYTHON_VERSION = (3, 13)  # Python 3.14 breaks spaCy/pydantic compatibility
RECOMMENDED_VERSION = (3, 12)


def get_python_version() -> Tuple[int, int, int]:
    """Get current Python version as tuple."""
    return sys.version_info[:3]


def check_python_version(raise_error: bool = True) -> bool:
    """Check if current Python version is compatible.

    Args:
        raise_error: If True, raises SystemExit on incompatibility.
                    If False, returns boolean and shows warning.

    Returns:
        bool: True if compatible, False otherwise.
    """
    current_version = get_python_version()
    major, minor, patch = current_version

    version_str = f"{major}.{minor}.{patch}"
    min_str = f"{MIN_PYTHON_VERSION[0]}.{MIN_PYTHON_VERSION[1]}"
    max_str = f"{MAX_PYTHON_VERSION[0]}.{MAX_PYTHON_VERSION[1]}"
    rec_str = f"{RECOMMENDED_VERSION[0]}.{RECOMMENDED_VERSION[1]}"

    # Check if version is too old
    if (major, minor) < MIN_PYTHON_VERSION:
        message = (
            f"\n{'='*70}\n"
            f"ERROR: Python {version_str} is not supported\n"
            f"{'='*70}\n\n"
            f"This application requires Python {min_str} or newer (but not 3.14+).\n\n"
            f"Please upgrade your Python installation:\n"
            f"  https://www.python.org/downloads/\n\n"
            f"Recommended version: Python {rec_str}\n"
            f"{'='*70}\n"
        )
        if raise_error:
            sys.exit(message)
        else:
            warnings.warn(message)
            return False

    # Check if version is too new (3.14+)
    if (major, minor) > MAX_PYTHON_VERSION:
        message = (
            f"\n{'='*70}\n"
            f"ERROR: Python {version_str} is not compatible\n"
            f"{'='*70}\n\n"
            f"Python 3.14+ has breaking changes that affect spaCy and Pydantic.\n\n"
            f"This application requires Python {min_str} to {max_str}.\n\n"
            f"Please install a compatible Python version:\n"
            f"  • Download Python {rec_str}: https://www.python.org/downloads/\n"
            f"  • Or use a virtual environment with Python {rec_str}\n\n"
            f"Quick fix:\n"
            f"  py -{RECOMMENDED_VERSION[0]}.{RECOMMENDED_VERSION[1]} -m venv venv\n"
            f"  venv\\Scripts\\activate  # Windows\n"
            f"  source venv/bin/activate  # Linux/Mac\n"
            f"  pip install iso-flowchart-generator\n\n"
            f"Recommended version: Python {rec_str}\n"
            f"{'='*70}\n"
        )
        if raise_error:
            sys.exit(message)
        else:
            warnings.warn(message)
            return False

    # Warn if not using recommended version
    if (major, minor) != RECOMMENDED_VERSION:
        warnings.warn(
            f"\nYou are using Python {version_str}. "
            f"While compatible, Python {rec_str} is recommended for best stability.\n",
            UserWarning
        )

    return True


def get_version_info() -> dict:
    """Get detailed version information.

    Returns:
        dict: Version information including compatibility status.
    """
    current = get_python_version()
    is_compatible = check_python_version(raise_error=False)

    return {
        "current_version": f"{current[0]}.{current[1]}.{current[2]}",
        "min_version": f"{MIN_PYTHON_VERSION[0]}.{MIN_PYTHON_VERSION[1]}",
        "max_version": f"{MAX_PYTHON_VERSION[0]}.{MAX_PYTHON_VERSION[1]}",
        "recommended_version": f"{RECOMMENDED_VERSION[0]}.{RECOMMENDED_VERSION[1]}",
        "is_compatible": is_compatible,
        "is_recommended": (current[0], current[1]) == RECOMMENDED_VERSION,
    }


if __name__ == "__main__":
    # Run version check when executed directly
    info = get_version_info()
    print(f"\nPython Version Check")
    print(f"{'='*50}")
    print(f"Current version:     {info['current_version']}")
    print(f"Minimum version:     {info['min_version']}")
    print(f"Maximum version:     {info['max_version']}")
    print(f"Recommended version: {info['recommended_version']}")
    print(f"Compatible:          {info['is_compatible']}")
    print(f"Recommended:         {info['is_recommended']}")
    print(f"{'='*50}\n")

    if not info['is_compatible']:
        sys.exit(1)
