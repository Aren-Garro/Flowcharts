"""Pytest configuration and shared fixtures."""

import pytest
import tempfile
from pathlib import Path


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_workflow():
    """Sample workflow text for testing."""
    return """
1. Start
2. Read user input
3. Validate data
4. Check if data is valid
   - If yes: Process data
   - If no: Show error message
5. Save to database
6. End
    """


@pytest.fixture
def simple_workflow():
    """Simple linear workflow for testing."""
    return """
1. Start
2. Process data
3. End
    """


@pytest.fixture
def complex_workflow():
    """Complex workflow with nested decisions."""
    return """
User Authentication Workflow

1. Start
2. Display login page
3. Read username and password
4. Check if credentials are valid
   - If yes:
     a. Create session
     b. Redirect to dashboard
   - If no:
     a. Increment failed login counter
     b. Check if attempts exceed 3
        - If yes: Lock account
        - If no: Return to login
5. End
    """
