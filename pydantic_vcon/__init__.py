"""
pydantic-vcon - A Pydantic-based implementation of the vCon format
"""

from .models import (
    Analysis,
    Appended,
    Attachment,
    CivicAddress,
    Dialog,
    DialogType,
    Disposition,
    Encoding,
    GroupItem,
    Party,
    PartyHistory,
    Redacted,
    VCon,
    VConVersion,
)

__version__ = "0.0.2"
__all__ = [
    "VCon",
    "VConVersion",
    "Party",
    "Dialog",
    "DialogType",
    "Analysis",
    "Attachment",
    "GroupItem",
    "Redacted",
    "Appended",
    "Encoding",
    "Disposition",
    "CivicAddress",
    "PartyHistory",
]
