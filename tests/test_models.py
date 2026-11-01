"""core-05 model rules: Session, Event table c.3, Dialog, Attachment, references."""

import json
import warnings

import pytest
from pydantic import ValidationError

from pydantic_vcon import (
    AmendedFrom,
    Analysis,
    Attachment,
    Dialog,
    DialogType,
    Encoding,
    Event,
    Party,
    RedactedFrom,
    Session,
    SessionReference,
    VCon,
)

T0 = "2022-06-21T17:53:26.000+00:00"
BASE = {"uuid": "01a16b86-9a63-8346-b9a2-279e0d16bc46", "created_at": T0}


def rec(**kw):
    d = {"type": "recording", "start": T0, "duration": 1, "parties": [0, 1],
         "mediatype": "audio/x-wav", "url": "https://e.com/a.wav", "content_hash": "sha512-x"}
    d.update(kw)
    return d


# -- builder -------------------------------------------------------------------
def test_build_new_emits_0_5_0_and_a_v8_uuid():
    v = VCon.build_new()
    assert v.vcon.value == "0.5.0" and v.uuid[14] == "8"
    assert json.loads(v.to_json())["vcon"] == "0.5.0"
    assert v.sessions is None and v.events is None


def test_vcon_parameter_is_optional():
    assert VCon.model_validate(BASE).vcon.value == "0.5.0"


def test_other_versions_are_rejected():
    with pytest.raises(ValidationError):
        VCon.model_validate(dict(BASE, vcon="0.0.2"))


def test_add_dialog_creates_or_reuses_the_session():
    v = VCon.build_new()
    v.add_party(Party(name="a"))
    v.add_party(Party(name="b"))
    i = v.add_dialog(Dialog.model_validate(rec()))
    j = v.add_dialog(Dialog.model_validate(rec()))
    assert (i, j) == (0, 1) and v.sessions[0].dialog == [0, 1]
    assert v.is_valid() == (True, [])
    VCon.model_validate(v.to_dict())


# -- session rule ---------------------------------------------------------------
def test_dialog_without_session_is_rejected():
    with pytest.raises(ValidationError, match="At least one Session"):
        VCon.model_validate(dict(BASE, parties=[{}, {}], dialog=[rec()]))


def test_events_without_session_are_rejected():
    with pytest.raises(ValidationError, match="At least one Session"):
        VCon.model_validate(dict(BASE, parties=[{}], events=[{"type": "join", "time": T0, "sessions": 0, "party": 0}]))


def test_empty_session_and_empty_dialog_placeholder_are_valid():
    v = VCon.model_validate(dict(BASE, dialog=[{}], sessions=[{}]))
    assert v.to_dict()["dialog"] == [{}] and v.to_dict()["sessions"] == [{}]
    assert v.dialog[0].is_empty


def test_no_dialog_no_events_needs_no_session():
    VCon.model_validate(dict(BASE, parties=[{}]))


def test_session_reference_types_and_required_fields():
    s = Session.model_validate({"sessions": [{"session": 1, "type": "breakout", "description": "x"}]})
    assert s.sessions[0].type == "breakout"
    with pytest.raises(ValidationError):
        SessionReference.model_validate({"session": 1})
    with pytest.raises(ValidationError):
        Session.model_validate({"duration": -1})


def test_session_with_unknown_reference_index_fails_is_valid():
    v = VCon.model_validate(dict(BASE, sessions=[{"sessions": [{"session": 5, "type": "child"}]}]))
    ok, errors = v.is_valid()
    assert not ok and "invalid session index" in errors[0]


# -- events: table c.3 ------------------------------------------------------------
M = {  # minimal valid parameters per type
    "join": {"sessions": 0, "party": 0},
    "drop": {"sessions": 0, "party": 0},
    "hold": {"sessions": 0, "party": 0},
    "unhold": {"sessions": 0, "party": 0},
    "mute": {"sessions": 0, "party": 0},
    "unmute": {"sessions": 0, "party": 0},
    "keydown": {"sessions": 0, "party": 0, "button": "1"},
    "keyup": {"sessions": 0, "party": 0, "button": "1"},
    "consultation-start": {"sessions": 0, "party": 1, "transferee": 0, "transfer_target": 2, "consultation": 1},
    "blind-transfer": {"sessions": 0, "party": 1, "transferee": 0, "transfer_target": 2, "target_session": 2},
    "consultative-transfer": {"sessions": 0, "party": 1, "transferee": 0, "transfer_target": 2,
                              "consultation": 1, "target_session": 2},
    "transfer-abandoned": {"sessions": 0, "party": 1, "transferee": 0},
    "channel-contributors": {"dialog": 0, "channel": 0},
}
OTHER = {"sessions": 0, "party": 0, "dialog": 0, "channel": 0, "contributors": 0, "button": "1",
         "transferee": 0, "transfer_target": 0, "consultation": 0, "target_session": 0}


@pytest.mark.parametrize("etype", sorted(M))
def test_minimal_event_is_valid(etype):
    Event.model_validate({"type": etype, "time": T0, **M[etype]})


@pytest.mark.parametrize("etype", sorted(M))
def test_each_missing_mandatory_parameter_is_rejected(etype):
    for name in M[etype]:
        params = {k: v for k, v in M[etype].items() if k != name}
        with pytest.raises(ValidationError, match=name):
            Event.model_validate({"type": etype, "time": T0, **params})


@pytest.mark.parametrize("etype", sorted(M))
def test_each_forbidden_parameter_is_rejected(etype):
    from pydantic_vcon.models import EVENT_PARAMETER_RULES

    for name, rule in EVENT_PARAMETER_RULES[etype].items():
        if rule != "X":
            continue
        with pytest.raises(ValidationError, match=name):
            Event.model_validate({"type": etype, "time": T0, **M[etype], name: OTHER[name]})


@pytest.mark.parametrize("etype", ["transfer-abandoned"])
def test_optional_parameters_are_accepted(etype):
    Event.model_validate({"type": etype, "time": T0, **M[etype], "transfer_target": 2, "consultation": 1})


def test_channel_contributors_contributors_optional_and_null():
    Event.model_validate({"type": "channel-contributors", "time": T0, "dialog": 0, "channel": 0})
    Event.model_validate({"type": "channel-contributors", "time": T0, "dialog": 0, "channel": 0, "contributors": None})
    Event.model_validate({"type": "channel-contributors", "time": T0, "dialog": 0, "channel": 1, "contributors": [0, 1]})


def test_dialog_on_party_events_only_warns():
    with pytest.warns(UserWarning, match="should not be present"):
        Event.model_validate({"type": "join", "time": T0, "sessions": 0, "party": 0, "dialog": 0})


def test_transfer_sessions_must_be_a_single_index():
    with pytest.raises(ValidationError, match="single index"):
        Event.model_validate({"type": "blind-transfer", "time": T0, **dict(M["blind-transfer"], sessions=[0, 1])})


def test_extension_event_type_only_needs_type_and_time():
    e = Event.model_validate({"type": "x-custom", "time": T0, "anything": 1})
    assert e.to_dict()["anything"] == 1


def test_event_time_is_required_and_validated():
    with pytest.raises(ValidationError):
        Event.model_validate({"type": "join", "sessions": 0, "party": 0})
    with pytest.raises(ValidationError):
        Event.model_validate({"type": "join", "time": "yesterday", "sessions": 0, "party": 0})


def test_channel_contributors_must_reference_a_recording():
    v = VCon.model_validate(dict(
        BASE, parties=[{}], sessions=[{"dialog": [0]}],
        dialog=[{"type": "text", "start": T0, "parties": 0, "body": "x", "encoding": "none", "mediatype": "text/plain"}],
        events=[{"type": "channel-contributors", "time": T0, "dialog": 0, "channel": 0}]))
    ok, errors = v.is_valid()
    assert not ok and "'recording' Dialog" in errors[0]


# -- dialog ------------------------------------------------------------------------
@pytest.mark.parametrize("t", ["recording", "text", "incomplete", DialogType.TEXT])
def test_core_dialog_types(t):
    t = getattr(t, "value", t)
    d = {"type": t, "start": T0, "parties": 0}
    if t == "incomplete":
        d["disposition"] = "no-answer"
    elif t == "text":
        d.update(body="hi", encoding="none", mediatype="text/plain")
    else:
        d.update(url="https://e.com/a", content_hash="sha512-x", mediatype="audio/ogg")
    assert Dialog.model_validate(d).type == t


@pytest.mark.parametrize("t", ["transfer", "recording-set"])
def test_removed_dialog_types_are_rejected(t):
    with pytest.raises(ValidationError, match="removed in 0.5.0"):
        Dialog.model_validate({"type": t, "start": T0})


@pytest.mark.parametrize("name", ["party_history", "originator", "transferee", "transferor",
                                  "transfer_target", "original", "consultation", "target_dialog",
                                  "recordings", "recording_set"])
def test_removed_dialog_fields_are_rejected(name):
    with pytest.raises(ValidationError, match="removed in 0.5.0"):
        Dialog.model_validate(rec(**{name: 1}))


def test_audio_video_accepted_on_read_with_a_warning():
    with pytest.warns(UserWarning, match="not defined by core-05"):
        Dialog.model_validate(rec(type="audio"))


def test_extension_dialog_type_needs_the_extensions_entry():
    v = VCon.model_validate(dict(BASE, sessions=[{"dialog": [0]}], dialog=[{"type": "x-thing", "start": T0}]))
    assert not v.is_valid()[0]
    ok = VCon.model_validate(dict(BASE, extensions=["x-thing"], sessions=[{"dialog": [0]}],
                                  dialog=[{"type": "x-thing", "start": T0}]))
    assert ok.is_valid()[0]


def test_incomplete_needs_disposition_and_no_content():
    with pytest.raises(ValidationError, match="disposition required"):
        Dialog.model_validate({"type": "incomplete", "start": T0, "parties": 0})
    with pytest.raises(ValidationError, match="must not have"):
        Dialog.model_validate({"type": "incomplete", "disposition": "busy", "mediatype": "audio/ogg"})


def test_typeless_nonempty_dialog_is_rejected():
    with pytest.raises(ValidationError, match="type is required"):
        Dialog.model_validate({"start": T0})


def test_dialog_content_rules():
    with pytest.raises(ValidationError, match="content_hash"):
        Dialog.model_validate(rec(content_hash=None))
    with pytest.raises(ValidationError, match="encoding"):
        Dialog.model_validate({"type": "text", "body": "x", "mediatype": "text/plain"})
    with pytest.raises(ValidationError, match="mediatype"):
        Dialog.model_validate({"type": "text", "body": "x", "encoding": "none"})
    with pytest.raises(ValidationError, match="string"):
        Dialog.model_validate({"type": "text", "body": {"a": 1}, "encoding": "none", "mediatype": "text/plain"})
    Dialog.model_validate({"type": "text", "body": {"a": 1}, "encoding": Encoding.JSON, "mediatype": "application/json"})


def test_dialog_parties_allow_null_channel_slots():
    d = Dialog.model_validate(rec(parties=[0, None, [1, 2]]))
    assert d.to_dict()["parties"] == [0, None, [1, 2]] or d.parties == [0, None, [1, 2]]


def test_redacted_segments():
    d = Dialog.model_validate(rec(redacted_segments=[{"start": T0, "end": T0, "parties": [0]}]))
    assert d.redacted_segments[0].parties == [0]
    with pytest.raises(ValidationError):
        Dialog.model_validate(rec(redacted_segments=[{"start": T0}]))


# -- attachments ----------------------------------------------------------------------
def att(**kw):
    d = {"purpose": "x", "start": T0, "party": 0, "body": "b", "encoding": "none", "mediatype": "text/plain"}
    d.update(kw)
    return d


def test_attachment_needs_party_and_dialog_or_session():
    Attachment.model_validate(att(dialog=0))
    Attachment.model_validate(att(session=0))
    Attachment.model_validate(att(session=[0, 1]))
    with pytest.raises(ValidationError, match="dialog or session"):
        Attachment.model_validate(att())
    with pytest.raises(ValidationError):
        Attachment.model_validate(att(session=0, party=None))


def test_legacy_attachment_type_is_a_deprecated_read_alias():
    with pytest.warns(DeprecationWarning):
        d = att(session=0, type="old")
        del d["purpose"]
        a = Attachment.model_validate(d)
    assert a.purpose == "old"


def test_default_attachment_scope_only_with_exactly_one_session():
    v = VCon.model_validate(dict(BASE, parties=[{}], sessions=[{}]))
    a = v.create_attachment(party=0, purpose="x", body="b", encoding="none", mediatype="text/plain")
    assert a.session == 0 and a.dialog is None
    v.add_session(Session())
    with pytest.raises(ValueError, match="no default scope"):
        v.create_attachment(party=0, purpose="x", body="b", encoding="none", mediatype="text/plain")
    b = v.create_attachment(party=0, dialog=3, purpose="x", body="b", encoding="none", mediatype="text/plain")
    assert b.dialog == 3 and b.session is None  # a dialog index is never widened to a Session


def test_add_tag_follows_the_scope_rules():
    v = VCon.model_validate(dict(BASE, parties=[{}], sessions=[{}]))
    v.add_tag("a", "1")
    v.add_tag("b", "2")
    assert v.get_tag("a") == "1" and v.get_tag("b") == "2" and len(v.attachments) == 1
    assert v.attachments[0].session == 0
    v2 = VCon.build_new()
    v2.add_party(Party())
    with pytest.raises(ValueError):
        v2.add_tag("a", "1")


def test_no_lawful_basis_is_added_or_invented():
    v = VCon.build_new()
    assert not v.has_lawful_basis() and v.attachments == []
    v.add_party(Party())
    v.add_session(Session())
    v.add_attachment(Attachment.model_validate(att(purpose="lawful_basis", session=0)))
    assert v.has_lawful_basis()
    assert not v.is_valid()[0]  # lawful_basis is an extension and must be listed
    v.extensions = ["lawful_basis"]
    assert v.is_valid()[0]


# -- analysis, redaction, amendment -----------------------------------------------------
def test_analysis_references_and_self_reference():
    v = VCon.model_validate(dict(BASE, parties=[{}], sessions=[{}], analysis=[
        {"type": "summary", "vendor": "v", "sessions": 0, "analysis": 0, "body": "x", "encoding": "none"}]))
    ok, errors = v.is_valid()
    assert not ok and "itself" in errors[0]
    with pytest.raises(ValidationError):
        Analysis.model_validate({"type": "summary"})


def test_redacted_from_and_amended_from_are_exclusive():
    with pytest.raises(ValidationError, match="mutually exclusive"):
        VCon.model_validate(dict(BASE, redacted_from={"type": "PII", "uuid": "u"}, amended_from={"uuid": "u"}))


def test_redacted_from_requires_type_and_hash_with_url():
    with pytest.raises(ValidationError):
        RedactedFrom.model_validate({"uuid": "u"})
    with pytest.raises(ValidationError, match="content_hash"):
        RedactedFrom.model_validate({"type": "PII", "url": "https://e.com/x"})
    with pytest.raises(ValidationError, match="uuid"):
        AmendedFrom.model_validate({})
    AmendedFrom.model_validate({"url": "https://e.com/x", "content_hash": "sha512-x"})


def test_old_names_are_deprecated_read_aliases():
    with pytest.warns(DeprecationWarning, match="redacted_from"):
        v = VCon.model_validate(dict(BASE, redacted={"type": "PII", "uuid": "u"}))
    assert v.redacted_from.uuid == "u" and "redacted" not in v.to_dict()
    with pytest.warns(DeprecationWarning, match="amended_from"):
        v = VCon.model_validate(dict(BASE, amended={"uuid": "u"}))
    assert v.to_dict()["amended_from"] == {"uuid": "u"}


def test_redacted_strings_refs_must_be_declared():
    v = VCon.model_validate(dict(BASE, subject="call __REDACTED_REF_7"))
    assert not v.is_valid()[0]
    v = VCon.model_validate(dict(BASE, subject="call __REDACTED_REF_7", redacted_strings=[{"ref": 7, "type": "UNSPECIFIED"}]))
    assert v.is_valid()[0]
    with pytest.raises(ValidationError):
        VCon.model_validate(dict(BASE, redacted_strings=[{"ref": 0}]))


def test_critical_must_be_listed_in_extensions():
    v = VCon.model_validate(dict(BASE, critical=["x"]))
    assert not v.is_valid()[0]
    assert VCon.model_validate(dict(BASE, critical=["x"], extensions=["x"])).is_valid()[0]


def test_extension_parameters_survive_a_round_trip():
    src = dict(BASE, vcon="0.5.0", parties=[{"name": "a", "x-extra": 1}], x_top="y")
    assert VCon.model_validate(src).to_dict() == src


def test_invalid_party_index_is_reported():
    v = VCon.model_validate(dict(BASE, parties=[{}], sessions=[{"parties": [3], "dialog": [0]}],
                                 dialog=[rec(parties=[5])]))
    errors = v.is_valid()[1]
    assert any("party index: 3" in e for e in errors) and any("party index: 5" in e for e in errors)


def test_unreferenced_dialog_is_a_warning_not_an_error():
    v = VCon.model_validate(dict(BASE, parties=[{}, {}], sessions=[{}], dialog=[rec()]))
    errors, warns = v.check()
    assert not errors and any("not referenced" in w for w in warns)
