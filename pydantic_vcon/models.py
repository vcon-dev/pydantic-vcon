"""Pydantic models for vCon core-05 (draft-ietf-vcon-vcon-core-05, syntax "0.5.0").

Writers emit ``"vcon": "0.5.0"``. Readers accept 0.4.0 input through
:func:`pydantic_vcon.migration.migrate_0_4_0_to_0_5_0` (see ``VCon.from_dict``).
The models accept extra members so vCon extension parameters survive a round
trip; the ``extensions`` list is checked in ``VCon.is_valid``.
"""

from __future__ import annotations

import json
import os
import re
import uuid as _uuid
import warnings
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    PrivateAttr,
    TypeAdapter,
    model_validator,
)
from typing_extensions import Annotated

SYNTAX_VERSION = "0.5.0"

# ---------------------------------------------------------------------------
# Vocabulary
# ---------------------------------------------------------------------------


class VConVersion(str, Enum):
    """Syntax version written by this library."""

    V_0_5_0 = "0.5.0"


class Encoding(str, Enum):
    """Encoding types for inline files (extensions may define more)."""

    BASE64URL = "base64url"
    JSON = "json"
    NONE = "none"


class DialogType(str, Enum):
    """Dialog types defined by core-05 (extensions may define more)."""

    RECORDING = "recording"
    TEXT = "text"
    INCOMPLETE = "incomplete"


class Disposition(str, Enum):
    """Disposition values for incomplete dialogs (extensions may define more)."""

    NO_ANSWER = "no-answer"
    CONGESTION = "congestion"
    FAILED = "failed"
    BUSY = "busy"
    HUNG_UP = "hung-up"
    VOICEMAIL_NO_MESSAGE = "voicemail-no-message"


class SessionReferenceType(str, Enum):
    """Session_Reference types (extensions may define more)."""

    CHILD = "child"
    PEER = "peer"
    PRECURSOR = "precursor"
    BREAKOUT = "breakout"


CORE_DIALOG_TYPES = ("recording", "text", "incomplete")
#: Dialog types older libraries wrote though core-05 does not define them.
#: Accepted on read with a warning, never written.
LIBRARY_DIALOG_TYPES = ("audio", "video")
#: Dialog types removed in 0.5.0 (replaced by Events and Sessions).
REMOVED_DIALOG_TYPES = ("transfer", "recording-set")
#: Dialog parameters removed in 0.5.0.
REMOVED_DIALOG_PARAMS = (
    "party_history",
    "originator",
    "transferee",
    "transferor",
    "transfer_target",
    "original",
    "consultation",
    "target_dialog",
    "recordings",
    "recording_set",
)
CORE_ENCODINGS = ("base64url", "json", "none")
CORE_DISPOSITIONS = tuple(d.value for d in Disposition)
SESSION_REFERENCE_TYPES = tuple(t.value for t in SessionReferenceType)

PARTY_EVENT_TYPES = ("join", "drop", "hold", "unhold", "mute", "unmute")
KEY_EVENT_TYPES = ("keydown", "keyup")
TRANSFER_EVENT_TYPES = (
    "consultation-start",
    "blind-transfer",
    "consultative-transfer",
    "transfer-abandoned",
)
CHANNEL_CONTRIBUTORS = "channel-contributors"
CORE_EVENT_TYPES = (
    PARTY_EVENT_TYPES + KEY_EVENT_TYPES + TRANSFER_EVENT_TYPES + (CHANNEL_CONTRIBUTORS,)
)
#: Core Event parameters, in the order of section 4.3.
EVENT_PARAMETERS = (
    "type",
    "time",
    "sessions",
    "party",
    "dialog",
    "channel",
    "contributors",
    "button",
    "transferee",
    "transfer_target",
    "consultation",
    "target_session",
)


def _event_rules(**overrides: str) -> Dict[str, str]:
    base = {
        "type": "M",
        "time": "M",
        "sessions": "M",
        "party": "M",
        "dialog": "SN",
        "channel": "X",
        "contributors": "X",
        "button": "X",
        "transferee": "X",
        "transfer_target": "X",
        "consultation": "X",
        "target_session": "X",
    }
    base.update(overrides)
    return base


#: Table c.3 (section 4.3.1.5). M must, O optional, SN should not, X must not.
EVENT_PARAMETER_RULES: Dict[str, Dict[str, str]] = {}
for _t in PARTY_EVENT_TYPES:
    EVENT_PARAMETER_RULES[_t] = _event_rules()
for _t in KEY_EVENT_TYPES:
    EVENT_PARAMETER_RULES[_t] = _event_rules(button="M")
EVENT_PARAMETER_RULES["consultation-start"] = _event_rules(
    transferee="M", transfer_target="M", consultation="M"
)
EVENT_PARAMETER_RULES["blind-transfer"] = _event_rules(
    transferee="M", transfer_target="M", target_session="M"
)
EVENT_PARAMETER_RULES["consultative-transfer"] = _event_rules(
    transferee="M", transfer_target="M", consultation="M", target_session="M"
)
EVENT_PARAMETER_RULES["transfer-abandoned"] = _event_rules(
    transferee="M", transfer_target="O", consultation="O"
)
EVENT_PARAMETER_RULES[CHANNEL_CONTRIBUTORS] = _event_rules(
    sessions="X", party="X", dialog="M", channel="M", contributors="O"
)
del _t

#: Extension names this library recognises from how they show up in a vCon.
KNOWN_ATTACHMENT_PURPOSE_EXTENSIONS = {
    "lawful_basis": "lawful_basis",
    "wtf_transcription": "wtf_transcription",
}
KNOWN_ANALYSIS_TYPE_EXTENSIONS = {"wtf_transcription": "wtf_transcription"}

_REDACTED_REF_RE = re.compile(r"__REDACTED_REF_(\d{1,5})(?!\d)")
_DATETIME = TypeAdapter(datetime)


# ---------------------------------------------------------------------------
# Shared types and helpers
# ---------------------------------------------------------------------------


def _check_date(v: Any) -> Any:
    """Accept a datetime or an RFC 3339 string; keep strings exactly as given."""
    if isinstance(v, str):
        try:
            _DATETIME.validate_python(v)
        except Exception:
            raise ValueError("Dates must be valid ISO 8601 / RFC 3339 format")
    return v


Index = Annotated[int, Field(ge=0)]
DateTime = Annotated[Union[datetime, str], AfterValidator(_check_date)]
IndexOrList = Union[Index, List[Index]]
ContentHash = Union[str, List[str]]


def _plain(v: Any) -> Any:
    return v.value if isinstance(v, Enum) else v


def _as_list(v: Any) -> List[Any]:
    if v is None:
        return []
    return v if isinstance(v, list) else [v]


def _is_empty(v: Any) -> bool:
    return v is None


class _Base(BaseModel):
    """Common configuration: extension parameters are kept."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    def to_dict(self) -> Dict[str, Any]:
        """JSON-ready dict without ``None`` values."""
        return self.model_dump(mode="json", exclude_none=True, by_alias=True)


def _check_content(obj: Any, what: str) -> None:
    """Inline/external content rules shared by Dialog, Attachment and Analysis."""
    body = getattr(obj, "body", None)
    encoding = _plain(getattr(obj, "encoding", None))
    if getattr(obj, "url", None) is not None and getattr(obj, "content_hash", None) is None:
        raise ValueError(f"{what} with url must include content_hash")
    if body is not None and body != "":
        if encoding is None:
            raise ValueError(f"{what} with a body must include encoding")
        if hasattr(obj, "mediatype") and not isinstance(obj, Analysis) and obj.mediatype is None:
            raise ValueError(f"{what} with a body must include mediatype")
    if encoding in ("base64url", "none") and body is not None and not isinstance(body, str):
        raise ValueError(f"{what} body must be a string when encoding is {encoding}")


# ---------------------------------------------------------------------------
# Party
# ---------------------------------------------------------------------------


class CivicAddress(_Base):
    """Civic address information for a party"""

    country: Optional[str] = None
    a1: Optional[str] = None
    a2: Optional[str] = None
    a3: Optional[str] = None
    a4: Optional[str] = None
    a5: Optional[str] = None
    a6: Optional[str] = None
    prd: Optional[str] = None
    pod: Optional[str] = None
    sts: Optional[str] = None
    hno: Optional[str] = None
    hns: Optional[str] = None
    lmk: Optional[str] = None
    loc: Optional[str] = None
    flr: Optional[str] = None
    nam: Optional[str] = None
    pc: Optional[str] = None


class Party(_Base):
    """A participant in the conversation. An empty Party Object stands for an unknown party."""

    tel: Optional[str] = None
    sip: Optional[str] = None
    stir: Optional[str] = None
    mailto: Optional[str] = None
    name: Optional[str] = None
    did: Optional[str] = None
    validation: Optional[str] = None
    gmlpos: Optional[str] = None
    civicaddress: Optional[CivicAddress] = None
    uuid: Optional[str] = None
    type: Optional[str] = None
    org: Optional[str] = None
    dept: Optional[str] = None


# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------


class SessionId(_Base):
    """SESSION-ID with local and remote parts"""

    local: Optional[str] = None
    remote: Optional[str] = None


class SessionReference(_Base):
    """Relationship of another Session to the containing Session (4.2.8)."""

    session: Index
    type: str
    description: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def _plain_type(cls, data: Any) -> Any:
        if isinstance(data, dict) and isinstance(data.get("type"), Enum):
            data = dict(data, type=data["type"].value)
        return data


class Session(_Base):
    """Scope for dialog and events (4.2). A Session with no parameters is permitted."""

    start: Optional[DateTime] = None
    duration: Optional[float] = Field(default=None, ge=0)
    parties: Optional[List[Index]] = None  # the receivers
    originator: Optional[Index] = None  # only when not the first party
    session_id: Optional[SessionId] = None
    sessions: Optional[List[SessionReference]] = None
    dialog: Optional[List[Index]] = None


# ---------------------------------------------------------------------------
# Event
# ---------------------------------------------------------------------------


class Event(_Base):
    """A point-in-time occurrence (4.3) with per-type parameter rules (table c.3)."""

    type: str
    time: DateTime
    sessions: Optional[IndexOrList] = None
    party: Optional[Index] = None
    dialog: Optional[IndexOrList] = None
    channel: Optional[Index] = None
    contributors: Optional[Union[Index, List[Index]]] = None
    button: Optional[str] = None
    transferee: Optional[Index] = None
    transfer_target: Optional[Index] = None
    consultation: Optional[Index] = None
    target_session: Optional[Index] = None

    @model_validator(mode="before")
    @classmethod
    def _plain_type(cls, data: Any) -> Any:
        if isinstance(data, dict) and isinstance(data.get("type"), Enum):
            data = dict(data, type=data["type"].value)
        return data

    @model_validator(mode="after")
    def _check_parameters(self) -> "Event":
        rules = EVENT_PARAMETER_RULES.get(self.type)
        if rules is None:
            return self  # extension-defined type: only type and time are known
        problems: List[str] = []
        for name, rule in rules.items():
            present = getattr(self, name) is not None
            if rule == "M" and not present:
                problems.append(f"{name} must be present in {self.type} events")
            elif rule == "X" and present:
                problems.append(f"{name} must not be present in {self.type} events")
            elif rule == "SN" and present:
                warnings.warn(
                    f"{name} should not be present in {self.type} events", UserWarning, stacklevel=2
                )
        if self.type in TRANSFER_EVENT_TYPES and isinstance(self.sessions, list):
            problems.append(f"sessions must be a single index in {self.type} events")
        if problems:
            raise ValueError("; ".join(problems))
        return self


# ---------------------------------------------------------------------------
# Dialog
# ---------------------------------------------------------------------------


class RedactedSegments(_Base):
    """An audiovisual segment of a recording which was redacted (4.5.12)."""

    start: DateTime
    end: DateTime
    parties: Optional[List[Index]] = None


class Dialog(_Base):
    """A segment of the conversation. ``Dialog()`` is the empty placeholder ``{}`` (4.5.1)."""

    type: Optional[str] = None
    start: Optional[DateTime] = None
    duration: Optional[float] = Field(default=None, ge=0)
    # Contributors only; receivers are in the Session. A null slot marks a channel with no contributor.
    parties: Optional[Union[Index, List[Optional[Union[Index, List[Index]]]]]] = None
    mediatype: Optional[str] = None
    filename: Optional[str] = None
    body: Optional[Any] = None
    encoding: Optional[str] = None
    url: Optional[str] = None
    content_hash: Optional[ContentHash] = None
    disposition: Optional[str] = None
    session_id: Optional[
        Union[SessionId, List[Union[SessionId, List[SessionId]]]]
    ] = None
    application: Optional[str] = None
    message_id: Optional[str] = None
    redacted_segments: Optional[List[RedactedSegments]] = None

    @model_validator(mode="before")
    @classmethod
    def _plain_enums(cls, data: Any) -> Any:
        if isinstance(data, dict):
            data = {k: (_plain(v) if k in ("type", "encoding", "disposition") else v)
                    for k, v in data.items()}
        return data

    @property
    def is_empty(self) -> bool:
        """True for the empty placeholder Dialog Object."""
        return not self.model_dump(exclude_none=True)

    @model_validator(mode="after")
    def _check_dialog(self) -> "Dialog":
        if self.type is None:
            if not self.is_empty:
                raise ValueError("type is required unless the Dialog Object is empty")
            return self
        extra = set(self.model_extra or {})
        removed = [p for p in REMOVED_DIALOG_PARAMS if p in extra]
        if removed:
            raise ValueError(
                f"Dialog parameters removed in 0.5.0: {removed}; use Sessions and Events "
                "(migrate 0.4.0 input with migrate_0_4_0_to_0_5_0)"
            )
        if self.type in REMOVED_DIALOG_TYPES:
            raise ValueError(
                f"Dialog type '{self.type}' was removed in 0.5.0; use Sessions and Events "
                "(migrate 0.4.0 input with migrate_0_4_0_to_0_5_0)"
            )
        if self.type in LIBRARY_DIALOG_TYPES:
            warnings.warn(
                f"Dialog type '{self.type}' is not defined by core-05; read as 'recording'",
                UserWarning,
                stacklevel=2,
            )
        if self.type == "incomplete":
            if self.disposition is None:
                raise ValueError("disposition required for incomplete dialogs")
            forbidden = [
                f for f in ("mediatype", "filename", "body", "encoding", "url",
                            "content_hash", "message_id", "redacted_segments")
                if getattr(self, f) is not None
            ]
            if forbidden:
                raise ValueError(f"incomplete dialogs must not have: {forbidden}")
        _check_content(self, "Dialog")
        return self


# ---------------------------------------------------------------------------
# Analysis and Attachment
# ---------------------------------------------------------------------------


class Analysis(_Base):
    """Analysis of the conversation (4.7)."""

    type: str
    dialog: Optional[IndexOrList] = None
    sessions: Optional[IndexOrList] = None
    attachment: Optional[IndexOrList] = None
    analysis: Optional[IndexOrList] = None
    mediatype: Optional[str] = None
    filename: Optional[str] = None
    vendor: str
    product: Optional[str] = None
    schema_: Optional[str] = Field(default=None, alias="schema")
    body: Optional[Any] = None
    encoding: Optional[str] = None
    url: Optional[str] = None
    content_hash: Optional[ContentHash] = None

    @model_validator(mode="before")
    @classmethod
    def _plain_enums(cls, data: Any) -> Any:
        if isinstance(data, dict) and isinstance(data.get("encoding"), Enum):
            data = dict(data, encoding=data["encoding"].value)
        return data

    @model_validator(mode="after")
    def _check_analysis(self) -> "Analysis":
        _check_content(self, "Analysis")
        return self


class Attachment(_Base):
    """Ancillary document (4.6). Needs a party and a dialog or a session."""

    purpose: Optional[str] = None
    start: DateTime
    party: Index
    dialog: Optional[Index] = None
    session: Optional[IndexOrList] = None
    mediatype: Optional[str] = None
    filename: Optional[str] = None
    body: Optional[Any] = None
    encoding: Optional[str] = None
    url: Optional[str] = None
    content_hash: Optional[ContentHash] = None

    @model_validator(mode="before")
    @classmethod
    def _legacy_and_enums(cls, data: Any) -> Any:
        if isinstance(data, dict):
            data = dict(data)
            if isinstance(data.get("encoding"), Enum):
                data["encoding"] = data["encoding"].value
            if "type" in data and "purpose" not in data:
                warnings.warn(
                    "Attachment 'type' is the 0.4.0 name; read as 'purpose'",
                    DeprecationWarning,
                    stacklevel=2,
                )
                data["purpose"] = data.pop("type")
        return data

    @model_validator(mode="after")
    def _check_attachment(self) -> "Attachment":
        if self.dialog is None and self.session is None:
            raise ValueError("Attachment must have at least one of dialog or session")
        if isinstance(self.session, list) and not self.session:
            raise ValueError("Attachment session must not be empty")
        _check_content(self, "Attachment")
        return self

    @property
    def type(self) -> Optional[str]:  # read-only alias for the old name
        return self.purpose


# ---------------------------------------------------------------------------
# Top-level references
# ---------------------------------------------------------------------------


class GroupItem(_Base):
    """Reference to another vCon in a group (``group`` is reserved for extension)."""

    uuid: Optional[str] = None
    body: Optional[str] = None
    encoding: Optional[Encoding] = None
    url: Optional[str] = None
    content_hash: Optional[ContentHash] = None

    @model_validator(mode="after")
    def _check(self) -> "GroupItem":
        has_inline = self.body is not None and self.encoding is not None
        has_external = self.url is not None and self.content_hash is not None
        if not (self.uuid is not None or has_inline or has_external):
            raise ValueError(
                "GroupItem must have either uuid, inline (body + encoding), "
                "or external (url + content_hash) content"
            )
        return self


class RedactedFrom(_Base):
    """Reference to the unredacted or less redacted vCon (4.1.8)."""

    type: str
    uuid: Optional[str] = None
    url: Optional[str] = None
    content_hash: Optional[ContentHash] = None

    @model_validator(mode="after")
    def _check(self) -> "RedactedFrom":
        if self.url is not None and self.content_hash is None:
            raise ValueError("redacted_from with url must include content_hash")
        return self


class AmendedFrom(_Base):
    """Reference to the prior vCon instance version (4.1.9)."""

    uuid: Optional[str] = None
    url: Optional[str] = None
    content_hash: Optional[ContentHash] = None

    @model_validator(mode="after")
    def _check(self) -> "AmendedFrom":
        if self.url is None and self.uuid is None:
            raise ValueError("amended_from must include uuid, or an external reference (url)")
        if self.url is not None and self.content_hash is None:
            raise ValueError("amended_from with url must include content_hash")
        return self


#: Deprecated names for the renamed 0.4.0 classes.
Redacted = RedactedFrom
Appended = AmendedFrom


class RedactedString(_Base):
    """A substring replaced by ``__REDACTED_REF_#`` (4.8)."""

    ref: int = Field(ge=1, le=99999)
    type: Optional[str] = None
    orig: Optional[str] = None


# ---------------------------------------------------------------------------
# VCon
# ---------------------------------------------------------------------------


def _uuid8() -> str:
    """A version 8 UUID (the draft says SHOULD be v8), from random bytes."""
    b = bytearray(os.urandom(16))
    b[6] = (b[6] & 0x0F) | 0x80
    b[8] = (b[8] & 0x3F) | 0x80
    return str(_uuid.UUID(bytes=bytes(b)))


def _idx_ok(value: Any, count: int) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and 0 <= value < count


class VCon(_Base):
    """Virtual Conversation Container, core-05 (syntax 0.5.0)."""

    vcon: Optional[VConVersion] = VConVersion.V_0_5_0
    uuid: str
    extensions: Optional[List[str]] = None
    critical: Optional[List[str]] = None
    created_at: DateTime
    updated_at: Optional[DateTime] = None
    subject: Optional[str] = None

    # Mutually exclusive
    redacted_from: Optional[RedactedFrom] = None
    amended_from: Optional[AmendedFrom] = None
    redacted_strings: Optional[List[RedactedString]] = None
    group: Optional[List[GroupItem]] = None

    sessions: Optional[List[Session]] = None
    parties: List[Party] = Field(default_factory=list)
    events: Optional[List[Event]] = None
    dialog: Optional[List[Dialog]] = Field(default_factory=list)
    analysis: Optional[List[Analysis]] = Field(default_factory=list)
    attachments: Optional[List[Attachment]] = Field(default_factory=list)

    _migration_report: Any = PrivateAttr(default=None)

    # -- validation ------------------------------------------------------
    @model_validator(mode="before")
    @classmethod
    def _version_and_renames(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        if data.get("vcon") == "0.4.0":
            raise ValueError(
                "vcon 0.4.0 input must be migrated first: use VCon.from_dict() or "
                "pydantic_vcon.migrate_0_4_0_to_0_5_0()"
            )
        if "payload" in data and "signatures" in data or "ciphertext" in data:
            raise ValueError(
                "signed or encrypted vCon: verify and decrypt it, then validate the unsigned payload"
            )
        data = dict(data)
        for old, new in (("redacted", "redacted_from"), ("amended", "amended_from")):
            if old in data:
                if new in data:
                    raise ValueError(f"both '{old}' and '{new}' are present")
                warnings.warn(
                    f"'{old}' is the 0.4.0 name; read as '{new}'", DeprecationWarning, stacklevel=2
                )
                data[new] = data.pop(old)
        return data

    @model_validator(mode="after")
    def _check_vcon(self) -> "VCon":
        if self.redacted_from is not None and self.amended_from is not None:
            raise ValueError("redacted_from and amended_from are mutually exclusive")
        if (self.dialog or self.events) and not self.sessions:
            raise ValueError(
                "At least one Session Object must exist if the events array or the dialog array "
                "contains Objects"
            )
        return self

    # -- construction ----------------------------------------------------
    @classmethod
    def build_new(cls) -> "VCon":
        """Create a new vCon with default values (no lawful basis attachment is added)."""
        return cls(
            uuid=_uuid8(),
            created_at=datetime.now(timezone.utc).isoformat(),
            parties=[],
            dialog=[],
            analysis=[],
            attachments=[],
        )

    @classmethod
    def from_dict(cls, data: Dict[str, Any], migrate_legacy: bool = True, strict: bool = False) -> "VCon":
        """Build from a dict. A 0.4.0 vCon is migrated (the report is kept in ``migration_report``).

        Signed or encrypted forms are never migrated here; decode them first.
        """
        report = None
        if (
            migrate_legacy
            and isinstance(data, dict)
            and data.get("vcon") == "0.4.0"
        ):
            from .migration import migrate_0_4_0_to_0_5_0

            data, report = migrate_0_4_0_to_0_5_0(data, strict=strict)
        obj = cls.model_validate(data)
        obj._migration_report = report
        return obj

    @classmethod
    def build_from_json(cls, json_string: str, migrate_legacy: bool = True) -> "VCon":
        """Create a vCon from a JSON string (0.4.0 input is migrated)."""
        return cls.from_dict(json.loads(json_string), migrate_legacy=migrate_legacy)

    @property
    def migration_report(self) -> Any:
        """The MigrationReport when this vCon was migrated on load, else None."""
        return self._migration_report

    # -- editing ---------------------------------------------------------
    def add_party(self, party: Party) -> int:
        """Add a party; returns its index."""
        self.parties.append(party)
        return len(self.parties) - 1

    def find_party_index(self, by: str, val: str) -> Optional[int]:
        for i, party in enumerate(self.parties):
            if party.model_dump().get(by) == val:
                return i
        return None

    def add_session(self, session: Session) -> int:
        """Add a Session; returns its index."""
        if self.sessions is None:
            self.sessions = []
        self.sessions.append(session)
        return len(self.sessions) - 1

    def add_dialog(self, dialog: Dialog, session: Optional[int] = None) -> int:
        """Add a Dialog and list it in a Session; returns the Dialog index.

        With ``session`` the Dialog is listed in that Session. Without it, the
        only Session is used; if there is none, one is created holding only the
        Dialog's start. With several Sessions and no ``session`` the Dialog is
        left unlisted and ``check()`` warns.
        """
        if self.dialog is None:
            self.dialog = []
        self.dialog.append(dialog)
        idx = len(self.dialog) - 1
        if dialog.is_empty:
            return idx
        if session is None:
            if not self.sessions:
                self.add_session(Session(start=dialog.start))
                session = 0
            elif len(self.sessions) == 1:
                session = 0
        if session is not None:
            if not _idx_ok(session, len(self.sessions or [])):
                raise ValueError(f"no Session at index {session}")
            s = self.sessions[session]
            s.dialog = (s.dialog or []) + [idx]
        return idx

    def find_dialog(self, by: str, val: str) -> Optional[Dialog]:
        for item in self.dialog or []:
            if item.model_dump().get(by) == val:
                return item
        return None

    def add_event(self, event: Event) -> int:
        if self.events is None:
            self.events = []
        self.events.append(event)
        return len(self.events) - 1

    def add_analysis(self, analysis: Analysis) -> int:
        if self.analysis is None:
            self.analysis = []
        self.analysis.append(analysis)
        return len(self.analysis) - 1

    def find_analysis_by_type(self, type: str) -> Optional[Analysis]:
        for item in self.analysis or []:
            if item.type == type:
                return item
        return None

    def create_attachment(
        self,
        *,
        party: int,
        dialog: Optional[int] = None,
        session: Optional[IndexOrList] = None,
        **fields: Any,
    ) -> Attachment:
        """Build an Attachment. With neither ``dialog`` nor ``session`` it is scoped to the
        only Session when exactly one exists; otherwise the caller must pass a scope.
        A dialog index is never widened to a Session.
        """
        if dialog is None and session is None:
            if len(self.sessions or []) != 1:
                raise ValueError(
                    "attachment needs dialog or session: the vCon has "
                    f"{len(self.sessions or [])} Sessions, so no default scope applies"
                )
            session = 0
        fields.setdefault("start", datetime.now(timezone.utc).isoformat())
        return Attachment(party=party, dialog=dialog, session=session, **fields)

    def add_attachment(self, attachment: Attachment) -> int:
        if self.attachments is None:
            self.attachments = []
        self.attachments.append(attachment)
        return len(self.attachments) - 1

    def find_attachment_by_purpose(self, purpose: str) -> Optional[Attachment]:
        for item in self.attachments or []:
            if item.purpose == purpose:
                return item
        return None

    find_attachment_by_type = find_attachment_by_purpose  # old name

    def has_lawful_basis(self) -> bool:
        """True when an attachment has purpose ``lawful_basis``."""
        return any(a.purpose == "lawful_basis" for a in self.attachments or [])

    def add_tag(
        self,
        tag_name: str,
        tag_value: str,
        party: int = 0,
        dialog: Optional[int] = None,
        session: Optional[IndexOrList] = None,
    ) -> None:
        """Add a tag to the ``tags`` attachment (created on first use, default scope rules apply)."""
        tags = self.find_attachment_by_purpose("tags")
        if tags is None:
            tags = self.create_attachment(
                purpose="tags", party=party, dialog=dialog, session=session,
                body={}, encoding="json", mediatype="application/json",
            )
            self.add_attachment(tags)
        if isinstance(tags.body, dict):
            tags.body[tag_name] = tag_value
        else:
            tags.body = {tag_name: tag_value}
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def get_tag(self, tag_name: str) -> Optional[str]:
        tags = self.find_attachment_by_purpose("tags")
        if tags is None or not isinstance(tags.body, dict):
            return None
        return tags.body.get(tag_name)

    # -- output ----------------------------------------------------------
    def to_dict(self) -> Dict[str, Any]:
        """JSON-ready dict; unset empty arrays are left out."""
        out = self.model_dump(mode="json", exclude_none=True, by_alias=True)
        for key in ("parties", "dialog", "analysis", "attachments"):
            if out.get(key) == [] and key not in self.model_fields_set:
                del out[key]
        return out

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    def dumps(self) -> str:
        return self.to_json()

    # -- checks ----------------------------------------------------------
    def check(self) -> Tuple[List[str], List[str]]:
        """Cross-reference and extension checks. Returns ``(errors, warnings)``."""
        errors: List[str] = []
        warns: List[str] = []
        nparty = len(self.parties)
        ndialog = len(self.dialog or [])
        nsession = len(self.sessions or [])
        nattach = len(self.attachments or [])
        nanalysis = len(self.analysis or [])

        def check_idx(label: str, value: Any, count: int, noun: str) -> None:
            for v in _as_list(value):
                if v is None:
                    continue
                if not _idx_ok(v, count):
                    errors.append(f"{label} references invalid {noun} index: {v}")

        for i, d in enumerate(self.dialog or []):
            for p in _as_list(d.parties):
                for q in (p if isinstance(p, list) else [p]):
                    check_idx(f"Dialog at index {i}", q, nparty, "party")
        referenced = set()
        for i, s in enumerate(self.sessions or []):
            label = f"Session at index {i}"
            check_idx(label, s.parties, nparty, "party")
            check_idx(label, s.originator, nparty, "party")
            check_idx(label, s.dialog, ndialog, "dialog")
            for ref in s.sessions or []:
                check_idx(label, ref.session, nsession, "session")
            referenced.update(s.dialog or [])
            if s.parties and s.originator is not None and s.originator == s.parties[0]:
                warns.append(f"{label} has originator equal to its first party (4.2.4)")
            for x in s.dialog or []:
                if _idx_ok(x, ndialog) and self.dialog[x].is_empty:
                    warns.append(f"{label} lists dialog {x}, an empty placeholder Dialog")
        for i, d in enumerate(self.dialog or []):
            if not d.is_empty and i not in referenced:
                warns.append(f"Dialog at index {i} is not referenced by any Session Object")
        for i, e in enumerate(self.events or []):
            label = f"Event at index {i}"
            check_idx(label, e.sessions, nsession, "session")
            for name in ("party", "transferee", "transfer_target"):
                check_idx(label, getattr(e, name), nparty, "party")
            check_idx(label, e.contributors, nparty, "party")
            check_idx(label, e.dialog, ndialog, "dialog")
            check_idx(label, e.consultation, nsession, "session")
            check_idx(label, e.target_session, nsession, "session")
            if e.type == CHANNEL_CONTRIBUTORS and isinstance(e.dialog, int) and _idx_ok(e.dialog, ndialog):
                if self.dialog[e.dialog].type != "recording":
                    errors.append(f"{label} of type 'channel-contributors' must reference a 'recording' Dialog")
        for i, a in enumerate(self.attachments or []):
            label = f"Attachment at index {i}"
            check_idx(label, a.party, nparty, "party")
            check_idx(label, a.dialog, ndialog, "dialog")
            check_idx(label, a.session, nsession, "session")
            if isinstance(a.dialog, int) and _idx_ok(a.dialog, ndialog) and self.dialog[a.dialog].is_empty:
                warns.append(f"{label} references dialog {a.dialog}, an empty placeholder Dialog")
        for i, a in enumerate(self.analysis or []):
            label = f"Analysis at index {i}"
            check_idx(label, a.dialog, ndialog, "dialog")
            check_idx(label, a.sessions, nsession, "session")
            check_idx(label, a.attachment, nattach, "attachment")
            check_idx(label, a.analysis, nanalysis, "analysis")
            if i in _as_list(a.analysis):
                errors.append(f"{label} must not reference itself in analysis")
            if all(getattr(a, k) is None for k in ("dialog", "sessions", "attachment", "analysis")):
                warns.append(f"{label} should have at least one of dialog, sessions, attachment or analysis")

        # extensions (4.1.3)
        listed = list(self.extensions or [])
        for name in self.critical or []:
            if name not in listed:
                errors.append(f"Extension '{name}' is listed in critical but not in extensions")
        used, unnamed = extensions_in_use(self.to_dict())
        for name in sorted(used):
            if name not in listed:
                errors.append(f"Extension '{name}' is in use but is not listed in the extensions parameter")
        if unnamed and not listed:
            errors.append(
                "Values outside the core vocabulary are in use but the extensions parameter "
                "lists no extension: " + "; ".join(unnamed)
            )

        # redacted_strings (4.1.16)
        declared = set()
        for n, rs in enumerate(self.redacted_strings or []):
            if rs.ref in declared:
                errors.append(f"redacted_strings[{n}] duplicates ref {rs.ref}")
            declared.add(rs.ref)
        found: set = set()
        _scan_redacted_refs({k: v for k, v in self.to_dict().items() if k != "redacted_strings"}, found)
        for ref in sorted(found - declared):
            errors.append(f"__REDACTED_REF_{ref} appears in the vCon but has no entry in redacted_strings")
        return errors, warns

    def is_valid(self) -> Tuple[bool, List[str]]:
        """Return ``(is_valid, errors)``. Structural rules fail at construction; this adds
        cross-reference and extension checks."""
        errors, _ = self.check()
        return len(errors) == 0, errors


def _scan_redacted_refs(obj: Any, found: set) -> None:
    if isinstance(obj, str):
        for m in _REDACTED_REF_RE.finditer(obj):
            found.add(int(m.group(1)))
    elif isinstance(obj, list):
        for v in obj:
            _scan_redacted_refs(v, found)
    elif isinstance(obj, dict):
        for v in obj.values():
            _scan_redacted_refs(v, found)


def extensions_in_use(vcon: Dict[str, Any]) -> Tuple[set, List[str]]:
    """Find the vCon extensions a vCon dict uses.

    Returns ``(names, unnamed)``: names of extensions this library recognises
    (``lawful_basis``, ``wtf_transcription``), and a description of each use of
    a value outside the core vocabulary whose extension cannot be identified.
    """
    names: set = set()
    unnamed: List[str] = []
    for i, att in enumerate(_as_list(vcon.get("attachments"))):
        if isinstance(att, dict):
            purpose = att.get("purpose")
            if purpose in KNOWN_ATTACHMENT_PURPOSE_EXTENSIONS:
                names.add(KNOWN_ATTACHMENT_PURPOSE_EXTENSIONS[purpose])
            enc = att.get("encoding")
            if enc is not None and enc not in CORE_ENCODINGS:
                unnamed.append(f"attachments[{i}] encoding '{enc}'")
    for i, an in enumerate(_as_list(vcon.get("analysis"))):
        if isinstance(an, dict):
            if an.get("type") in KNOWN_ANALYSIS_TYPE_EXTENSIONS:
                names.add(KNOWN_ANALYSIS_TYPE_EXTENSIONS[an["type"]])
            enc = an.get("encoding")
            if enc is not None and enc not in CORE_ENCODINGS:
                unnamed.append(f"analysis[{i}] encoding '{enc}'")
    for i, d in enumerate(_as_list(vcon.get("dialog"))):
        if isinstance(d, dict) and d:
            enc = d.get("encoding")
            if enc is not None and enc not in CORE_ENCODINGS:
                unnamed.append(f"dialog[{i}] encoding '{enc}'")
            disp = d.get("disposition")
            if d.get("type") == "incomplete" and disp is not None and disp not in CORE_DISPOSITIONS:
                unnamed.append(f"dialog[{i}] disposition '{disp}'")
            t = d.get("type")
            if t is not None and t not in CORE_DIALOG_TYPES and t not in LIBRARY_DIALOG_TYPES:
                unnamed.append(f"dialog[{i}] type '{t}'")
    for i, e in enumerate(_as_list(vcon.get("events"))):
        if isinstance(e, dict):
            t = e.get("type")
            if t is not None and t not in CORE_EVENT_TYPES:
                unnamed.append(f"events[{i}] type '{t}'")
    for i, s in enumerate(_as_list(vcon.get("sessions"))):
        if isinstance(s, dict):
            for j, ref in enumerate(_as_list(s.get("sessions"))):
                if isinstance(ref, dict):
                    t = ref.get("type")
                    if t is not None and t not in SESSION_REFERENCE_TYPES:
                        unnamed.append(f"sessions[{i}].sessions[{j}] type '{t}'")
    return names, unnamed
