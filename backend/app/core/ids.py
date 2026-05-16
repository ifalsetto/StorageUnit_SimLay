import base64
import hashlib
import uuid


def new_uuid(prefix: str | None = None) -> str:
    value = str(uuid.uuid4())
    return f"{prefix}_{value}" if prefix else value


def make_run_short(seed: str) -> str:
    """Stable short ID derived from run_id/profile seed. Stored on run for deterministic handles."""
    digest = hashlib.sha1(seed.encode("utf-8")).digest()
    return base64.b32encode(digest).decode("ascii")[:6]


def padded_sequence(seq: int, width: int = 3) -> str:
    return str(seq).zfill(width)


def generate_handle(run_short: str, sequence: int, prefix: str = "ITEM", width: int = 3) -> str:
    return f"{prefix}-{run_short}-{padded_sequence(sequence, width)}"


def generate_sku(run_short: str, sequence: int, prefix: str = "FT-GEN", width: int = 3) -> str:
    return f"{prefix}-{run_short}-{padded_sequence(sequence, width)}"
