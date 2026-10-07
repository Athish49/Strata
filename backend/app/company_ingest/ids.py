import uuid

UUID_NAMESPACE = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")


def stable_uuid(*parts: str) -> uuid.UUID:
    """UUIDv5 over '|'.join(parts). Same inputs always produce same output."""
    return uuid.uuid5(UUID_NAMESPACE, "|".join(parts))
