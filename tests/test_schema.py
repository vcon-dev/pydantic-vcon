"""Model JSON schema output is checked against Appendix C required fields and properties."""

import json
from pathlib import Path

import pytest

from pydantic_vcon import (
    Analysis,
    Attachment,
    CivicAddress,
    Dialog,
    Event,
    Party,
    RedactedFrom,
    RedactedSegments,
    RedactedString,
    Session,
    SessionId,
    SessionReference,
    VCon,
)

SCHEMA = json.loads((Path(__file__).parent / "fixtures" / "appendix-c-json-schema.json").read_text())
DEFS = SCHEMA["definitions"]

PAIRS = [
    ("Session", Session),
    ("SessionReference", SessionReference),
    ("Party", Party),
    ("Civicaddress", CivicAddress),
    ("Event", Event),
    ("Dialog", Dialog),
    ("SessionId", SessionId),
    ("Attachment", Attachment),
    ("Analysis", Analysis),
    ("RedactedString", RedactedString),
    ("RedactedSegments", RedactedSegments),
]


@pytest.mark.parametrize("name,model", PAIRS, ids=[p[0] for p in PAIRS])
def test_required_fields_match_appendix_c(name, model):
    generated = model.model_json_schema()
    assert sorted(generated.get("required", [])) == sorted(DEFS[name].get("required", []))


@pytest.mark.parametrize("name,model", PAIRS, ids=[p[0] for p in PAIRS])
def test_every_appendix_c_property_is_a_model_property(name, model):
    generated = set(model.model_json_schema()["properties"])
    assert set(DEFS[name]["properties"]) <= generated


def test_top_level_required_and_properties():
    generated = VCon.model_json_schema()
    assert sorted(generated["required"]) == sorted(SCHEMA["required"])
    assert set(SCHEMA["properties"]) <= set(generated["properties"])


def test_redacted_from_required_fields():
    assert sorted(RedactedFrom.model_json_schema()["required"]) == sorted(
        SCHEMA["properties"]["redacted_from"]["required"]
    )
    assert set(SCHEMA["properties"]["redacted_from"]["properties"]) <= set(
        RedactedFrom.model_json_schema()["properties"]
    )


def test_version_is_0_5_0_in_the_schema_and_the_model():
    assert SCHEMA["properties"]["vcon"]["const"] == "0.5.0"
    assert VCon.build_new().vcon.value == "0.5.0"
