from __future__ import annotations

from enum import Enum


class Confidence(str, Enum):
    VERIFIED = "Verified"
    INFERRED = "Inferred"
    UNKNOWN = "Unknown"


class Condition(str, Enum):
    NEW = "New"
    LIKE_NEW = "Like New"
    USED = "Used"
    FAIR = "Fair"
    PARTS = "Parts"
    UNKNOWN = "Unknown"


class TruthSource(str, Enum):
    USER_VISUAL = "User Visual"
    PHOTO = "Photo"
    USER_CONFIRMED = "User Confirmed"
    DEFAULT_LIBRARY = "Default Library"
    TONY_HISTORY = "Tony History"
    APPROVED_COMP = "Approved Comp"
    WEB_CITED = "Web (Cited)"
    MANUAL = "Manual"


class InventoryOwner(str, Enum):
    THOMAS = "Thomas"
    MINE = "Mine"
    UNASSIGNED = "Unassigned"


class ItemAction(str, Enum):
    SELL = "Sell"
    DONATE = "Donate"
    DUMP = "Dump"
    HOLD = "Hold"
    UNASSIGNED = "Unassigned"


class EvidenceSourceType(str, Enum):
    API = "api"
    URL = "url"
    SCREENSHOT = "screenshot"
    LIBRARY = "library"
    MANUAL_URL = "manual_url"


class ListingType(str, Enum):
    SOLD = "sold"
    ACTIVE = "active"
    AUCTION_ENDED = "auction_ended"


class ValuationStatus(str, Enum):
    PASSED = "passed"
    UNKNOWN_CONFIDENCE = "unknown_confidence"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    HIGH_VARIANCE = "high_variance"
    NOT_VALUED = "not_valued"


class AuditAction(str, Enum):
    CREATE = "create"
    UPDATE = "update"
    REMOVE = "remove"
    RESTORE = "restore"
    DUPLICATE = "duplicate"
    VALUE = "value"
    EXPORT = "export"
    WARN = "warn"
