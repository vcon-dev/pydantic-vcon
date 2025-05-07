from __future__ import annotations

from typing import Dict, List, Optional, Union, Any, Literal
from enum import Enum
from datetime import datetime
from pydantic import BaseModel, Field, field_validator, model_validator, validator
import json
import uuid


class VConVersion(str, Enum):
    """Version of the vCon format"""
    V_0_0_2 = "0.0.2"


class Encoding(str, Enum):
    """Encoding types for inline files"""
    BASE64URL = "base64url"
    JSON = "json"
    NONE = "none"


class CivicAddress(BaseModel):
    """Civic address information for a party"""
    country: Optional[str] = None
    a1: Optional[str] = None  # National subdivisions (e.g., state, province)
    a2: Optional[str] = None  # County, parish, district
    a3: Optional[str] = None  # City, township
    a4: Optional[str] = None  # Neighborhood, block
    a5: Optional[str] = None
    a6: Optional[str] = None
    prd: Optional[str] = None  # Leading street direction
    pod: Optional[str] = None  # Trailing street suffix
    sts: Optional[str] = None  # Street suffix
    hno: Optional[str] = None  # House number
    hns: Optional[str] = None  # House number suffix
    lmk: Optional[str] = None  # Landmark
    loc: Optional[str] = None  # Additional location info
    flr: Optional[str] = None  # Floor
    nam: Optional[str] = None  # Name (residence, business)
    pc: Optional[str] = None   # Postal code

    def to_dict(self) -> Dict[str, str]:
        """Convert the address to a dictionary, excluding None values"""
        return {k: v for k, v in self.model_dump().items() if v is not None}


class PartyHistory(BaseModel):
    """History of a party's participation in a dialog"""
    party: int
    event: Literal["join", "drop", "hold", "unhold", "mute", "unmute"]
    time: Union[datetime, str]

    def to_dict(self) -> Dict[str, Any]:
        """Convert the party history to a dictionary"""
        result = self.model_dump()
        if isinstance(result["time"], datetime):
            result["time"] = result["time"].isoformat()
        return result


class Party(BaseModel):
    """A participant in the conversation"""
    tel: Optional[str] = None
    stir: Optional[str] = None
    mailto: Optional[str] = None
    name: Optional[str] = None
    validation: Optional[str] = None
    gmlpos: Optional[str] = None
    civicaddress: Optional[CivicAddress] = None
    uuid: Optional[str] = None
    role: Optional[str] = None
    contact_list: Optional[str] = None
    meta: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert the party to a dictionary, excluding None values"""
        result = {}
        for key, value in self.model_dump().items():
            if value is None:
                continue
            if key == "civicaddress" and value is not None:
                result[key] = value.to_dict()
            else:
                result[key] = value
        return result


class DialogType(str, Enum):
    """Types of dialog entries"""
    RECORDING = "recording"
    TEXT = "text"
    TRANSFER = "transfer"
    INCOMPLETE = "incomplete"


class Disposition(str, Enum):
    """Disposition values for incomplete dialogs"""
    NO_ANSWER = "no-answer"
    CONGESTION = "congestion"
    FAILED = "failed"
    BUSY = "busy"
    HUNG_UP = "hung-up"
    VOICEMAIL_NO_MESSAGE = "voicemail-no-message"


class Dialog(BaseModel):
    """A segment of the conversation"""
    type: DialogType
    start: Union[datetime, str]
    duration: Optional[float] = None
    parties: Union[int, List[int], List[Union[int, List[int]]]]
    originator: Optional[int] = None
    mediatype: Optional[str] = None
    filename: Optional[str] = None
    
    # Dialog content (one of the following sets)
    body: Optional[str] = None  # For inline data
    encoding: Optional[Encoding] = None  # For inline data
    
    url: Optional[str] = None  # For external data
    content_hash: Optional[Union[str, List[str]]] = None  # For external data
    
    # Additional properties
    disposition: Optional[Disposition] = None
    party_history: Optional[List[PartyHistory]] = None
    
    # Transfer-specific properties
    transferee: Optional[int] = None
    transferor: Optional[int] = None
    transfer_target: Optional[int] = None
    original: Optional[int] = None
    consultation: Optional[int] = None
    target_dialog: Optional[int] = None
    
    # Additional metadata
    campaign: Optional[str] = None
    interaction_type: Optional[str] = None
    interaction_id: Optional[str] = None
    skill: Optional[str] = None
    application: Optional[str] = None
    message_id: Optional[str] = None
    meta: Optional[Dict[str, Any]] = None

    @model_validator(mode='before')
    def validate_dialog_fields(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        dialog_type = values.get('type')
        if not dialog_type:
            return values
            
        # Validate disposition for incomplete dialogs
        if dialog_type == DialogType.INCOMPLETE:
            if not values.get('disposition'):
                raise ValueError("disposition required for incomplete dialogs")
            if values.get('body') is not None or values.get('url') is not None:
                raise ValueError("body or url should not be present for incomplete dialogs")
        else:
            if values.get('disposition') is not None:
                raise ValueError("disposition should not be present for non-incomplete dialogs")
            
            # For recording or text dialogs, validate content is provided
            if dialog_type in [DialogType.RECORDING, DialogType.TEXT]:
                has_inline = values.get('body') is not None and values.get('encoding') is not None
                has_external = values.get('url') is not None and values.get('content_hash') is not None
                
                if not (has_inline or has_external):
                    raise ValueError("Dialog must have either inline (body + encoding) or external (url + content_hash) content")
        
        return values

    @field_validator('transferee', 'transferor', 'transfer_target', 'original', 'consultation', 'target_dialog')
    def validate_transfer_fields(cls, v, info):
        # Validate transfer fields are provided for transfer dialogs
        values = info.data
        if values.get('type') == DialogType.TRANSFER and v is None:
            field_name = info.field_name
            if field_name in ['transferee', 'transferor', 'transfer_target', 'original', 'target_dialog']:
                raise ValueError(f"{field_name} required for transfer dialogs")

        # Validate transfer fields are NOT provided for non-transfer dialogs
        if values.get('type') != DialogType.TRANSFER and v is not None:
            raise ValueError(f"{info.field_name} should not be present for non-transfer dialogs")
        
        return v

    def to_dict(self) -> Dict[str, Any]:
        """Convert the dialog to a dictionary, excluding None values"""
        result = {}
        for key, value in self.model_dump().items():
            if value is None:
                continue
                
            if key == 'start' and isinstance(value, datetime):
                result[key] = value.isoformat()
            elif key == 'party_history' and value is not None:
                result[key] = [p.to_dict() for p in value]
            else:
                result[key] = value
                
        return result


class Analysis(BaseModel):
    """Analysis of the conversation"""
    type: str
    dialog: Optional[Union[int, List[int]]] = None
    mediatype: Optional[str] = None
    filename: Optional[str] = None
    vendor: str
    product: Optional[str] = None
    schema: Optional[str] = None
    
    # Analysis content
    body: Optional[Any] = None  # Can be dict, list, or str
    encoding: Encoding
    
    # Alternative for external content
    url: Optional[str] = None
    content_hash: Optional[Union[str, List[str]]] = None

    @model_validator(mode='after')
    def validate_analysis_content(self) -> 'Analysis':
        # Either inline (body) or external (url + content_hash) content must be provided
        has_inline = self.body is not None
        has_external = self.url is not None and self.content_hash is not None
        
        if not (has_inline or has_external):
            raise ValueError("Analysis must have either inline (body) or external (url + content_hash) content")
            
        # If encoding is json, validate body is valid JSON
        if self.encoding == Encoding.JSON and has_inline:
            body = self.body
            if not isinstance(body, (dict, list)):
                # In a real implementation, we would try to parse this if it's a string
                # but for this model we'll just verify it's a compatible type
                raise ValueError("JSON body must be a dict or list")
                
        return self


class Attachment(BaseModel):
    """Attachment for the conversation"""
    type: str
    start: Optional[datetime] = None
    party: Optional[int] = None
    mediatype: Optional[str] = None
    filename: Optional[str] = None
    dialog: Optional[int] = None
    
    # Attachment content
    body: Optional[Union[str, Dict[str, Any], List[Any]]] = None  # Allow dict/list for JSON content
    encoding: Optional[Encoding] = None
    
    # Alternative for external content
    url: Optional[str] = None
    content_hash: Optional[Union[str, List[str]]] = None

    @model_validator(mode='after')
    def validate_attachment_content(self) -> 'Attachment':
        # Either inline (body + encoding) or external (url + content_hash) content must be provided
        has_inline = self.body is not None and self.encoding is not None
        has_external = self.url is not None and self.content_hash is not None
        
        if not (has_inline or has_external):
            raise ValueError("Attachment must have either inline (body + encoding) or external (url + content_hash) content")
            
        return self


class GroupItem(BaseModel):
    """Reference to another vCon in a group"""
    uuid: Optional[str] = None
    
    # vCon content
    body: Optional[str] = None
    encoding: Optional[Literal["json"]] = None
    
    # Alternative for external content
    url: Optional[str] = None
    content_hash: Optional[Union[str, List[str]]] = None

    @model_validator(mode='after')
    def validate_group_item_content(self) -> 'GroupItem':
        # Either uuid, inline (body + encoding) or external (url + content_hash) content must be provided
        has_uuid = self.uuid is not None
        has_inline = self.body is not None and self.encoding is not None
        has_external = self.url is not None and self.content_hash is not None
        
        if not (has_uuid or has_inline or has_external):
            raise ValueError("GroupItem must have either uuid, inline (body + encoding), or external (url + content_hash) content")
            
        return self


class Redacted(BaseModel):
    """Reference to an unredacted or less redacted vCon"""
    uuid: str
    type: Optional[str] = None
    
    # vCon content
    body: Optional[str] = None
    encoding: Optional[Encoding] = None
    
    # Alternative for external content
    url: Optional[str] = None
    content_hash: Optional[Union[str, List[str]]] = None


class Appended(BaseModel):
    """Reference to a prior vCon version"""
    uuid: Optional[str] = None
    
    # vCon content
    body: Optional[str] = None
    encoding: Optional[Encoding] = None
    
    # Alternative for external content
    url: Optional[str] = None
    content_hash: Optional[Union[str, List[str]]] = None

    @model_validator(mode='after')
    def validate_appended_content(self) -> 'Appended':
        # Either uuid, inline (body + encoding) or external (url + content_hash) content must be provided
        has_uuid = self.uuid is not None
        has_inline = self.body is not None and self.encoding is not None
        has_external = self.url is not None and self.content_hash is not None
        
        if not (has_uuid or has_inline or has_external):
            raise ValueError("Appended must have either uuid, inline (body + encoding), or external (url + content_hash) content")
            
        return self


class VCon(BaseModel):
    """Virtual Conversation Container"""
    vcon: VConVersion = VConVersion.V_0_0_2
    uuid: str
    created_at: Union[datetime, str]
    updated_at: Optional[Union[datetime, str]] = None
    subject: Optional[str] = None
    
    # Mutually exclusive: Only one of these can be provided
    redacted: Optional[Redacted] = None
    appended: Optional[Appended] = None
    group: Optional[List[GroupItem]] = None
    
    # Core content
    parties: List[Party] = Field(default_factory=list)
    dialog: Optional[List[Dialog]] = Field(default_factory=list)
    analysis: Optional[List[Analysis]] = Field(default_factory=list)
    attachments: Optional[List[Attachment]] = Field(default_factory=list)
    
    # Additional metadata
    meta: Optional[Dict[str, Any]] = None

    @field_validator('created_at', 'updated_at')
    def validate_date_format(cls, v):
        """Validate date fields are in ISO 8601 format"""
        if isinstance(v, str):
            try:
                return datetime.fromisoformat(v)
            except ValueError:
                raise ValueError("Dates must be valid ISO 8601 format")
        return v

    @model_validator(mode='after')
    def validate_mutually_exclusive_fields(self) -> 'VCon':
        """Validate that only one of redacted, appended, or group is provided"""
        count = 0
        if self.redacted is not None:
            count += 1
        if self.appended is not None:
            count += 1
        if self.group is not None and len(self.group) > 0:
            count += 1
            
        if count > 1:
            raise ValueError("Only one of redacted, appended, or group can be provided")
            
        return self

    @classmethod
    def build_new(cls) -> 'VCon':
        """Create a new vCon with default values"""
        from uuid import uuid4
        
        return cls(
            uuid=str(uuid4()),
            vcon=VConVersion.V_0_0_2,
            created_at=datetime.now().isoformat(),
            parties=[],
            dialog=[],
            analysis=[],
            attachments=[]
        )

    @classmethod
    def build_from_json(cls, json_string: str) -> 'VCon':
        """Create a vCon from a JSON string"""
        import json
        vcon_dict = json.loads(json_string)
        return cls(**vcon_dict)

    def add_party(self, party: Party) -> None:
        """Add a party to the vCon"""
        self.parties.append(party)

    def find_party_index(self, by: str, val: str) -> Optional[int]:
        """Find the index of a party by a key-value pair"""
        for i, party in enumerate(self.parties):
            party_dict = party.model_dump()
            if by in party_dict and party_dict[by] == val:
                return i
        return None

    def add_dialog(self, dialog: Dialog) -> None:
        """Add a dialog to the vCon"""
        if self.dialog is None:
            self.dialog = []
        self.dialog.append(dialog)

    def find_dialog(self, by: str, val: str) -> Optional[Dialog]:
        """Find a dialog by a key-value pair"""
        if self.dialog is None:
            return None
            
        for dialog_item in self.dialog:
            dialog_dict = dialog_item.model_dump()
            if by in dialog_dict and dialog_dict[by] == val:
                return dialog_item
        return None

    def add_analysis(self, analysis: Analysis) -> None:
        """Add analysis to the vCon"""
        if self.analysis is None:
            self.analysis = []
        self.analysis.append(analysis)

    def find_analysis_by_type(self, type: str) -> Optional[Analysis]:
        """Find analysis by type"""
        if self.analysis is None:
            return None
            
        for analysis_item in self.analysis:
            if analysis_item.type == type:
                return analysis_item
        return None

    def add_attachment(self, attachment: Attachment) -> None:
        """Add an attachment to the vCon"""
        if self.attachments is None:
            self.attachments = []
        self.attachments.append(attachment)

    def find_attachment_by_type(self, type: str) -> Optional[Attachment]:
        """Find an attachment by type"""
        if self.attachments is None:
            return None
            
        for attachment_item in self.attachments:
            if attachment_item.type == type:
                return attachment_item
        return None

    def add_tag(self, tag_name: str, tag_value: str) -> None:
        """Add a tag to the vCon"""
        tags_attachment = self.find_attachment_by_type("tags")
        
        if tags_attachment is None:
            # Create a new tags attachment
            tags_attachment = Attachment(
                type="tags",
                body={},  # Initialize with empty dict instead of list
                encoding=Encoding.JSON
            )
            self.add_attachment(tags_attachment)
        
        # Update the tags
        if isinstance(tags_attachment.body, dict):
            tags_attachment.body[tag_name] = tag_value
        else:
            # If body is not a dict (shouldn't happen), initialize it
            tags_attachment.body = {tag_name: tag_value}
        
        self.updated_at = datetime.now()

    def get_tag(self, tag_name: str) -> Optional[str]:
        """Get a tag value by name"""
        tags_attachment = self.find_attachment_by_type("tags")
        if tags_attachment is None or not isinstance(tags_attachment.body, dict):
            return None
            
        return tags_attachment.body.get(tag_name)

    def to_json(self) -> str:
        """Convert the vCon to a JSON string"""
        def datetime_handler(obj):
            if isinstance(obj, datetime):
                return obj.isoformat()
            raise TypeError(f"Object of type {type(obj)} is not JSON serializable")
        
        return json.dumps(self.model_dump(exclude_none=True), default=datetime_handler)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the vCon to a dictionary"""
        return self.model_dump(exclude_none=True)
    
    def dumps(self) -> str:
        """Alias for to_json()"""
        return self.to_json()

    def is_valid(self) -> tuple[bool, list[str]]:
        """
        Validate the vCon according to the standard.
        
        Returns a tuple containing (is_valid, list_of_errors)
        """
        errors = []
        
        # Check required fields
        required_fields = ["uuid", "vcon", "created_at"]
        for field in required_fields:
            if getattr(self, field, None) is None:
                errors.append(f"Missing required field: {field}")
        
        # Validate created_at format
        if hasattr(self, "created_at"):
            if not isinstance(self.created_at, (datetime, str)):
                errors.append("Invalid created_at format. Must be ISO 8601 datetime string")
        
        # Validate parties
        if hasattr(self, "parties"):
            if not isinstance(self.parties, list):
                errors.append("parties must be a list")
        
        # Validate dialogs
        if hasattr(self, "dialog") and self.dialog:
            for i, dialog in enumerate(self.dialog):
                # Check dialog parties reference valid party indices
                if hasattr(dialog, "parties"):
                    party_indices = dialog.parties
                    party_count = len(self.parties)
                    
                    # Handle different party formats
                    if isinstance(party_indices, int):
                        if party_indices < 0 or party_indices >= party_count:
                            errors.append(f"Dialog at index {i} references invalid party index: {party_indices}")
                    elif isinstance(party_indices, list):
                        for idx in party_indices:
                            if isinstance(idx, int) and (idx < 0 or idx >= party_count):
                                errors.append(f"Dialog at index {i} references invalid party index: {idx}")
                
                # Check mimetype is valid
                if hasattr(dialog, "mimetype") and dialog.mimetype:
                    if dialog.type not in ["incomplete", "transfer"] and not dialog.mimetype:
                        errors.append(f"Dialog {i} missing required mimetype")
        
        # Validate analysis
        if hasattr(self, "analysis") and self.analysis:
            for i, analysis in enumerate(self.analysis):
                # Validate dialog references
                if hasattr(analysis, "dialog") and analysis.dialog is not None:
                    dialog_count = len(self.dialog) if self.dialog else 0
                    
                    if isinstance(analysis.dialog, int):
                        if analysis.dialog < 0 or analysis.dialog >= dialog_count:
                            errors.append(f"Analysis at index {i} references invalid dialog index: {analysis.dialog}")
                    elif isinstance(analysis.dialog, list):
                        for dialog_idx in analysis.dialog:
                            if not isinstance(dialog_idx, int) or dialog_idx < 0 or dialog_idx >= dialog_count:
                                errors.append(f"Analysis at index {i} references invalid dialog index: {dialog_idx}")
        
        return len(errors) == 0, errors 