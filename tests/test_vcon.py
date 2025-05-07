import pytest
from datetime import datetime
from pydantic_vcon import (
    VCon, Party, Dialog, DialogType, Encoding, Analysis,
    Attachment, CivicAddress, PartyHistory
)

def test_create_new_vcon():
    vcon = VCon.build_new()
    assert vcon.uuid is not None
    assert vcon.vcon == "0.0.2"
    assert isinstance(vcon.created_at, (datetime, str))
    assert vcon.parties == []
    assert vcon.dialog == []
    assert vcon.analysis == []
    assert vcon.attachments == []

def test_add_party():
    vcon = VCon.build_new()
    party = Party(
        tel="+1234567890",
        name="John Doe",
        civicaddress=CivicAddress(
            country="US",
            a1="CA",
            a3="San Francisco"
        )
    )
    vcon.add_party(party)
    assert len(vcon.parties) == 1
    assert vcon.parties[0].tel == "+1234567890"
    assert vcon.parties[0].name == "John Doe"
    assert vcon.parties[0].civicaddress.country == "US"

def test_add_dialog():
    vcon = VCon.build_new()
    party = Party(tel="+1234567890")
    vcon.add_party(party)
    
    dialog = Dialog(
        type=DialogType.TEXT,
        start=datetime.now(),
        parties=0,
        body="Hello, world!",
        encoding=Encoding.JSON
    )
    vcon.add_dialog(dialog)
    assert len(vcon.dialog) == 1
    assert vcon.dialog[0].type == DialogType.TEXT
    assert vcon.dialog[0].body == "Hello, world!"

def test_add_analysis():
    vcon = VCon.build_new()
    analysis = Analysis(
        type="sentiment",
        vendor="test",
        body={"score": 0.8},
        encoding=Encoding.JSON
    )
    vcon.add_analysis(analysis)
    assert len(vcon.analysis) == 1
    assert vcon.analysis[0].type == "sentiment"
    assert vcon.analysis[0].body["score"] == 0.8

def test_add_attachment():
    vcon = VCon.build_new()
    attachment = Attachment(
        type="transcript",
        body="This is a transcript",
        encoding=Encoding.JSON
    )
    vcon.add_attachment(attachment)
    assert len(vcon.attachments) == 1
    assert vcon.attachments[0].type == "transcript"
    assert vcon.attachments[0].body == "This is a transcript"

def test_add_tag():
    vcon = VCon.build_new()
    vcon.add_tag("category", "support")
    vcon.add_tag("priority", "high")
    
    tags_attachment = vcon.find_attachment_by_type("tags")
    assert tags_attachment is not None
    assert isinstance(tags_attachment.body, dict)
    assert tags_attachment.body["category"] == "support"
    assert tags_attachment.body["priority"] == "high"
    
    assert vcon.get_tag("category") == "support"
    assert vcon.get_tag("priority") == "high"
    assert vcon.get_tag("nonexistent") is None

def test_serialization():
    vcon = VCon.build_new()
    party = Party(tel="+1234567890", name="John Doe")
    vcon.add_party(party)
    
    dialog = Dialog(
        type=DialogType.TEXT,
        start=datetime.now(),
        parties=0,
        body="Hello, world!",
        encoding=Encoding.JSON
    )
    vcon.add_dialog(dialog)
    
    # Test to_dict
    vcon_dict = vcon.to_dict()
    assert vcon_dict["uuid"] == vcon.uuid
    assert len(vcon_dict["parties"]) == 1
    assert len(vcon_dict["dialog"]) == 1
    
    # Test to_json
    json_str = vcon.to_json()
    assert isinstance(json_str, str)
    assert vcon.uuid in json_str
    assert "John Doe" in json_str
    assert "Hello, world!" in json_str

def test_validation():
    vcon = VCon.build_new()
    is_valid, errors = vcon.is_valid()
    assert is_valid
    assert len(errors) == 0
    
    # Test invalid party reference
    dialog = Dialog(
        type=DialogType.TEXT,
        start=datetime.now(),
        parties=999,  # Invalid party index
        body="Hello, world!",
        encoding=Encoding.JSON
    )
    vcon.add_dialog(dialog)
    
    is_valid, errors = vcon.is_valid()
    assert not is_valid
    assert any("references invalid party index" in error for error in errors)

def test_incomplete_dialog():
    vcon = VCon.build_new()
    party = Party(tel="+1234567890")
    vcon.add_party(party)
    
    # Test valid incomplete dialog
    dialog = Dialog(
        type=DialogType.INCOMPLETE,
        start=datetime.now(),
        parties=0,
        disposition="no-answer"
    )
    vcon.add_dialog(dialog)
    is_valid, errors = vcon.is_valid()
    assert is_valid
    assert len(errors) == 0
    
    # Test invalid incomplete dialog (missing disposition)
    from pydantic import ValidationError
    with pytest.raises(ValidationError, match="disposition required for incomplete dialogs"):
        dialog = Dialog(
            type=DialogType.INCOMPLETE,
            start=datetime.now(),
            parties=0
        ) 