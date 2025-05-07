# pydantic-vcon

A Pydantic-based implementation of the vCon (Virtual Conversation Container) format.

## Installation

```bash
# Using pip
pip install pydantic-vcon

# Using Poetry
poetry add pydantic-vcon
```

## Development

This project uses Poetry for dependency management and packaging.

```bash
# Install Poetry (if not already installed)
curl -sSL https://install.python-poetry.org | python3 -

# Clone the repository
git clone https://github.com/howethomas/pydantic-vcon.git
cd pydantic-vcon

# Install dependencies
poetry install

# Run tests
poetry run pytest

# Format code
poetry run black .
poetry run isort .

# Type checking
poetry run mypy .

# Linting
poetry run ruff check .
```

## Quick Start

```python
from pydantic_vcon import VCon, Party, Dialog, DialogType, Encoding
from datetime import datetime

# Create a new vCon
vcon = VCon.build_new()

# Add a party
party = Party(
    tel="+1234567890",
    name="John Doe"
)
vcon.add_party(party)

# Add a dialog
dialog = Dialog(
    type=DialogType.TEXT,
    start=datetime.now(),
    parties=0,  # Reference to the first party
    body="Hello, world!",
    encoding=Encoding.JSON
)
vcon.add_dialog(dialog)

# Convert to JSON
json_str = vcon.to_json()
```

## Features

- Full implementation of the vCon format using Pydantic models
- Type validation and automatic conversion
- JSON serialization/deserialization
- Helper methods for common operations
- Comprehensive validation

## Documentation

For detailed documentation, please visit [the documentation site](https://pydantic-vcon.readthedocs.io/).

## License

This project is licensed under the MIT License - see the LICENSE file for details. 