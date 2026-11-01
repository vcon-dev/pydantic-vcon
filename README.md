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

Targets vCon core-05 (`draft-ietf-vcon-vcon-core-05`, syntax `"0.5.0"`).

```python
from datetime import datetime, timezone
from pydantic_vcon import VCon, Party, Dialog, Event

vcon = VCon.build_new()
vcon.add_party(Party(name="John Doe", tel="+1234567890"))
vcon.add_party(Party(name="Agent", mailto="agent@example.com"))

now = datetime.now(timezone.utc).isoformat()
# A Session is created for the first dialog. Dialog parties are contributors;
# the receivers are in Session.parties.
vcon.add_dialog(Dialog(type="text", start=now, parties=0, body="Hello",
                       encoding="none", mediatype="text/plain"))
vcon.sessions[0].parties = [0, 1]
vcon.add_event(Event(type="join", time=now, sessions=0, party=0))

print(vcon.to_json())
```

### Reading 0.4.0 vCons

`VCon.from_dict` and `VCon.build_from_json` migrate 0.4.0 input and keep the
report in `vcon.migration_report`. To migrate without building a model:

```python
from pydantic_vcon import migrate_0_4_0_to_0_5_0

vcon_dict, report = migrate_0_4_0_to_0_5_0(old_dict)   # strict=True raises instead of falling back
print(report.summary())
```

Signed (JWS) and encrypted (JWE) forms are not unwrapped by the models. The
migration takes a signed 0.4.0 envelope and migrates its payload, and the result
must be signed again.

## Features

- Full implementation of the vCon format using Pydantic models
- Type validation and automatic conversion
- JSON serialization/deserialization
- Helper methods for common operations
- Per-type Event parameter validation (core-05 table 4.3.1.5)
- Migration from 0.4.0 with a report of every inferred value

## Documentation

For detailed documentation, please visit [the documentation site](https://pydantic-vcon.readthedocs.io/).

## License

This project is licensed under the MIT License - see the LICENSE file for details. 