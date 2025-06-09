import uuid

def is_valid_uuid_v4(uuid_string: str) -> bool:
    try:
        uuid_obj = uuid.UUID(uuid_string)
        return uuid_obj.version == 4  # Ensure it's UUID v4
    except ValueError:
        return False