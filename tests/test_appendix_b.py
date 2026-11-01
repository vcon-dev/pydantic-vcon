"""Every Appendix B example parses, validates against Appendix C and round-trips."""

import base64
import json
import warnings
from pathlib import Path

import jsonschema
import pytest

from pydantic_vcon import VCon

FIXTURES = Path(__file__).parent / "fixtures"
SCHEMA = json.loads((FIXTURES / "appendix-c-json-schema.json").read_text())
EXAMPLES = sorted((FIXTURES / "appendix-b").glob("B*.json"))
ENVELOPES = {"B6-signed.json", "B7-encrypted.json"}
PLAIN = [p for p in EXAMPLES if p.name not in ENVELOPES]


def load(path):
    return json.loads(path.read_text())


def test_all_nine_examples_are_present():
    assert [p.name[:2] for p in EXAMPLES] == [f"B{i}" for i in range(1, 10)]


@pytest.mark.parametrize("path", PLAIN, ids=lambda p: p.name)
def test_example_parses_and_round_trips(path):
    src = load(path)
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        v = VCon.model_validate(src)
    assert v.to_dict() == src
    assert VCon.model_validate(v.to_dict()).to_dict() == src
    assert VCon.model_validate_json(v.to_json()).to_dict() == src


@pytest.mark.parametrize("path", PLAIN, ids=lambda p: p.name)
def test_example_passes_cross_reference_checks(path):
    ok, errors = VCon.model_validate(load(path)).is_valid()
    assert ok, errors


@pytest.mark.parametrize("path", PLAIN, ids=lambda p: p.name)
def test_model_output_validates_against_appendix_c(path):
    out = VCon.model_validate(load(path)).to_dict()
    jsonschema.Draft7Validator(SCHEMA).validate(out)


def test_b6_signed_payload_parses_and_round_trips():
    env = load(FIXTURES / "appendix-b" / "B6-signed.json")
    raw = env["payload"]
    payload = json.loads(base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)))
    v = VCon.model_validate(payload)
    assert v.to_dict() == payload
    jsonschema.Draft7Validator(SCHEMA).validate(v.to_dict())


@pytest.mark.parametrize("name", sorted(ENVELOPES))
def test_signed_and_encrypted_envelopes_are_not_unsigned_vcons(name):
    with pytest.raises(ValueError, match="signed or encrypted"):
        VCon.model_validate(load(FIXTURES / "appendix-b" / name))


def test_b8_and_b9_use_the_renamed_references():
    assert VCon.model_validate(load(next(p for p in EXAMPLES if p.name.startswith("B8")))).redacted_from
    assert VCon.model_validate(load(next(p for p in EXAMPLES if p.name.startswith("B9")))).amended_from


def test_lawful_basis_gap_in_the_examples():
    """No Appendix B example carries a lawful_basis attachment; none is invented."""
    missing = [p.name for p in PLAIN if not VCon.model_validate(load(p)).has_lawful_basis()]
    assert missing == [p.name for p in PLAIN]
