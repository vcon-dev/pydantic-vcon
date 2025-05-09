import uuid
from datetime import datetime

import pytest

from pydantic_vcon import (
    Analysis,
    Appended,
    Attachment,
    CivicAddress,
    Dialog,
    DialogType,
    Encoding,
    GroupItem,
    Party,
    PartyHistory,
    Redacted,
    VCon,
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
        civicaddress=CivicAddress(country="US", a1="CA", a3="San Francisco"),
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
        encoding=Encoding.JSON,
    )
    vcon.add_dialog(dialog)
    assert len(vcon.dialog) == 1
    assert vcon.dialog[0].type == DialogType.TEXT
    assert vcon.dialog[0].body == "Hello, world!"


def test_add_analysis():
    vcon = VCon.build_new()
    analysis = Analysis(
        type="sentiment", vendor="test", body={"score": 0.8}, encoding=Encoding.JSON
    )
    vcon.add_analysis(analysis)
    assert len(vcon.analysis) == 1
    assert vcon.analysis[0].type == "sentiment"
    assert vcon.analysis[0].body["score"] == 0.8


def test_add_attachment():
    vcon = VCon.build_new()
    attachment = Attachment(
        type="transcript", body="This is a transcript", encoding=Encoding.JSON
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
        encoding=Encoding.JSON,
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
        encoding=Encoding.JSON,
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
        disposition="no-answer",
    )
    vcon.add_dialog(dialog)
    is_valid, errors = vcon.is_valid()
    assert is_valid
    assert len(errors) == 0

    # Test invalid incomplete dialog (missing disposition)
    from pydantic import ValidationError

    with pytest.raises(
        ValidationError, match="disposition required for incomplete dialogs"
    ):
        dialog = Dialog(type=DialogType.INCOMPLETE, start=datetime.now(), parties=0)


def test_transfer_dialog():
    vcon = VCon.build_new()
    # Add parties for transfer
    party1 = Party(tel="+1234567890")
    party2 = Party(tel="+1987654321")
    party3 = Party(tel="+1122334455")
    vcon.add_party(party1)
    vcon.add_party(party2)
    vcon.add_party(party3)

    # Test valid transfer dialog
    dialog = Dialog(
        type=DialogType.TRANSFER,
        start=datetime.now(),
        parties=[0, 1],
        transferee=0,
        transferor=1,
        transfer_target=2,
        original=0,
        target_dialog=1,
    )
    vcon.add_dialog(dialog)
    is_valid, errors = vcon.is_valid()
    assert is_valid
    assert len(errors) == 0

    # Test invalid transfer dialog (missing required fields)
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        Dialog(type=DialogType.TRANSFER, start=datetime.now(), parties=[0, 1])


def test_external_content():
    vcon = VCon.build_new()
    party = Party(tel="+1234567890")
    vcon.add_party(party)

    # Test dialog with external content
    dialog = Dialog(
        type=DialogType.RECORDING,
        start=datetime.now(),
        parties=0,
        url="https://example.com/recording.wav",
        content_hash="sha256:abc123",
    )
    vcon.add_dialog(dialog)
    is_valid, errors = vcon.is_valid()
    assert is_valid
    assert len(errors) == 0

    # Test analysis with external content
    analysis = Analysis(
        type="transcription",
        vendor="test",
        url="https://example.com/transcript.json",
        content_hash="sha256:def456",
        encoding=Encoding.JSON,
    )
    vcon.add_analysis(analysis)
    assert len(vcon.analysis) == 1
    assert vcon.analysis[0].url == "https://example.com/transcript.json"


def test_party_history():
    vcon = VCon.build_new()
    party = Party(tel="+1234567890")
    vcon.add_party(party)

    dialog = Dialog(
        type=DialogType.TEXT,
        start=datetime.now(),
        parties=0,
        body="Hello, world!",
        encoding=Encoding.JSON,
        party_history=[
            PartyHistory(party=0, event="join", time=datetime.now()),
            PartyHistory(party=0, event="drop", time=datetime.now()),
        ],
    )
    vcon.add_dialog(dialog)
    is_valid, errors = vcon.is_valid()
    assert is_valid
    assert len(errors) == 0

    # Test party history serialization
    dialog_dict = dialog.model_dump()
    assert "party_history" in dialog_dict
    assert len(dialog_dict["party_history"]) == 2
    assert dialog_dict["party_history"][0]["event"] == "join"


def test_find_methods():
    vcon = VCon.build_new()

    # Add parties with different attributes
    party1 = Party(tel="+1234567890", name="John")
    party2 = Party(tel="+1987654321", name="Jane")
    vcon.add_party(party1)
    vcon.add_party(party2)

    # Test finding party by tel
    assert vcon.find_party_index("tel", "+1234567890") == 0
    assert vcon.find_party_index("tel", "+1987654321") == 1
    assert vcon.find_party_index("tel", "+9999999999") is None

    # Add dialogs with different types
    dialog1 = Dialog(
        type=DialogType.TEXT,
        start=datetime.now(),
        parties=0,
        body="Hello",
        encoding=Encoding.JSON,
    )
    dialog2 = Dialog(
        type=DialogType.RECORDING,
        start=datetime.now(),
        parties=1,
        body="Recording",
        encoding=Encoding.JSON,
    )
    vcon.add_dialog(dialog1)
    vcon.add_dialog(dialog2)

    # Test finding dialog by type
    found_dialog = vcon.find_dialog("type", DialogType.TEXT)
    assert found_dialog is not None
    assert found_dialog.body == "Hello"

    # Add analyses with different types
    analysis1 = Analysis(
        type="sentiment", vendor="test1", body={"score": 0.8}, encoding=Encoding.JSON
    )
    analysis2 = Analysis(
        type="transcription",
        vendor="test2",
        body={"text": "Hello"},
        encoding=Encoding.JSON,
    )
    vcon.add_analysis(analysis1)
    vcon.add_analysis(analysis2)

    # Test finding analysis by type
    found_analysis = vcon.find_analysis_by_type("sentiment")
    assert found_analysis is not None
    assert found_analysis.body["score"] == 0.8


def test_datetime_handling():
    vcon = VCon.build_new()

    # Test with datetime object
    now = datetime.now()
    vcon.created_at = now
    vcon_dict = vcon.model_dump()
    assert isinstance(vcon_dict["created_at"], datetime)

    # Test with string datetime
    vcon.created_at = "2024-03-20T12:00:00"
    vcon_dict = vcon.model_dump()
    assert vcon_dict["created_at"] == "2024-03-20T12:00:00"

    # Test with updated_at
    vcon.updated_at = now
    vcon_dict = vcon.model_dump()
    assert isinstance(vcon_dict["updated_at"], datetime)


def test_mutually_exclusive_fields():
    vcon = VCon.build_new()

    # Test that redacted and appended are mutually exclusive
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        VCon(
            vcon="0.0.2",
            uuid=str(uuid.uuid4()),
            created_at=datetime.now(),
            redacted=Redacted(uuid=str(uuid.uuid4())),
            appended=Appended(uuid=str(uuid.uuid4())),
        )

    # Test that group and redacted are mutually exclusive
    with pytest.raises(ValidationError):
        VCon(
            vcon="0.0.2",
            uuid=str(uuid.uuid4()),
            created_at=datetime.now(),
            redacted=Redacted(uuid=str(uuid.uuid4())),
            group=[GroupItem(uuid=str(uuid.uuid4()))],
        )


def test_json_serialization_edge_cases():
    vcon = VCon.build_new()

    # Test with special characters in body
    dialog = Dialog(
        type=DialogType.TEXT,
        start=datetime.now(),
        parties=0,
        body="Special chars: \n\t\r\"'\\",
        encoding=Encoding.JSON,
    )
    vcon.add_dialog(dialog)

    # Test serialization and deserialization
    json_str = vcon.to_json()
    new_vcon = VCon.build_from_json(json_str)
    assert new_vcon.dialog[0].body == "Special chars: \n\t\r\"'\\"

    # Test with None values
    vcon.meta = None
    vcon.subject = None
    json_str = vcon.to_json()
    new_vcon = VCon.build_from_json(json_str)
    assert new_vcon.meta is None
    assert new_vcon.subject is None


def test_validation_edge_cases():
    """Test validation edge cases."""
    # Test invalid created_at format
    with pytest.raises(ValueError):
        VCon(created_at="invalid-date", uuid=str(uuid.uuid4()))

    # Test invalid party reference in dialog
    test_vcon = VCon.build_new()
    with pytest.raises(ValueError):
        test_vcon.add_dialog(
            Dialog(
                type=DialogType.TEXT,
                start=datetime.now(),
                parties=[{"party_id": "nonexistent"}],
                body="test",
                encoding=Encoding.JSON,
            )
        )


def test_analysis_validation():
    vcon = VCon.build_new()
    party = Party(tel="+1234567890")
    vcon.add_party(party)

    dialog = Dialog(
        type=DialogType.TEXT,
        start=datetime.now(),
        parties=0,
        body="Hello",
        encoding=Encoding.JSON,
    )
    vcon.add_dialog(dialog)

    # Test analysis with invalid dialog reference
    analysis = Analysis(
        type="sentiment",
        vendor="test",
        dialog=999,  # Invalid dialog index
        body={"score": 0.8},
        encoding=Encoding.JSON,
    )
    vcon.add_analysis(analysis)
    is_valid, errors = vcon.is_valid()
    assert not is_valid
    assert any("references invalid dialog index" in error for error in errors)

    # Test analysis with invalid dialog list
    analysis = Analysis(
        type="sentiment",
        vendor="test",
        dialog=[0, 999],  # One valid, one invalid
        body={"score": 0.8},
        encoding=Encoding.JSON,
    )
    vcon.add_analysis(analysis)
    is_valid, errors = vcon.is_valid()
    assert not is_valid
    assert any("references invalid dialog index" in error for error in errors)


def test_content_validation():
    # Test dialog content validation
    with pytest.raises(ValueError, match="Dialog must have either inline"):
        Dialog(type=DialogType.TEXT, start=datetime.now(), parties=0)

    # Test analysis content validation
    with pytest.raises(ValueError, match="Analysis must have either inline"):
        Analysis(type="sentiment", vendor="test", encoding=Encoding.JSON)

    # Test attachment content validation
    with pytest.raises(ValueError, match="Attachment must have either inline"):
        Attachment(type="transcript")

    # Test group item content validation
    with pytest.raises(ValueError, match="GroupItem must have either uuid"):
        GroupItem()

    # Test appended content validation
    with pytest.raises(ValueError, match="Appended must have either uuid"):
        Appended()


def test_json_validation():
    # Test invalid JSON body in analysis
    with pytest.raises(ValueError, match="JSON body must be a dict or list"):
        Analysis(
            type="sentiment",
            vendor="test",
            body="invalid-json",  # String is not valid for JSON encoding
            encoding=Encoding.JSON,
        )


def test_utility_methods():
    vcon = VCon.build_new()

    # Test dumps method (alias for to_json)
    json_str = vcon.dumps()
    assert isinstance(json_str, str)
    assert vcon.uuid in json_str

    # Test find_dialog with None dialog list
    vcon.dialog = None
    assert vcon.find_dialog("type", DialogType.TEXT) is None

    # Test find_analysis with None analysis list
    vcon.analysis = None
    assert vcon.find_analysis_by_type("sentiment") is None

    # Test find_attachment with None attachments list
    vcon.attachments = None
    assert vcon.find_attachment_by_type("transcript") is None

    # Test add_dialog with None dialog list
    vcon.dialog = None
    dialog = Dialog(
        type=DialogType.TEXT,
        start=datetime.now(),
        parties=0,
        body="Hello",
        encoding=Encoding.JSON,
    )
    vcon.add_dialog(dialog)
    assert len(vcon.dialog) == 1

    # Test add_analysis with None analysis list
    vcon.analysis = None
    analysis = Analysis(
        type="sentiment", vendor="test", body={"score": 0.8}, encoding=Encoding.JSON
    )
    vcon.add_analysis(analysis)
    assert len(vcon.analysis) == 1

    # Test add_attachment with None attachments list
    vcon.attachments = None
    attachment = Attachment(
        type="transcript", body="This is a transcript", encoding=Encoding.JSON
    )
    vcon.add_attachment(attachment)
    assert len(vcon.attachments) == 1


def test_civic_address():
    # Test civic address with all fields
    address = CivicAddress(
        country="US",
        a1="CA",
        a2="San Francisco County",
        a3="San Francisco",
        a4="Downtown",
        a5="Financial District",
        a6="Block 1",
        prd="N",
        pod="St",
        sts="Ave",
        hno="123",
        hns="A",
        lmk="City Hall",
        loc="Near Market St",
        flr="5",
        nam="Acme Corp",
        pc="94105",
    )

    # Test to_dict method
    address_dict = address.to_dict()
    assert len(address_dict) == 17
    assert address_dict["country"] == "US"
    assert address_dict["a1"] == "CA"

    # Test with only required fields
    address = CivicAddress(country="US")
    address_dict = address.to_dict()
    assert len(address_dict) == 1
    assert address_dict["country"] == "US"


def test_party_history_serialization():
    # Test with datetime
    now = datetime.now()
    history = PartyHistory(party=0, event="join", time=now)
    history_dict = history.to_dict()
    assert history_dict["time"] == now.isoformat()

    # Test with string time
    history = PartyHistory(party=0, event="join", time="2024-03-20T12:00:00")
    history_dict = history.to_dict()
    assert history_dict["time"] == "2024-03-20T12:00:00"
