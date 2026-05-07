#!/bin/bash

export FLASK_DEBUG=1
export FLASK_APP=app.py
export FLASK_ENV=development
export STUDIO_BASE_DIR=~/studioVI-LAB

. .venv/bin/activate
flask --app app run --host=localhost --port=5000



def deserialize_metadata(metadata: Dict[str, Any], deserializationDepth: int = 0) -> Dict[str, Any]:
    """
    Deserializes a metadata dictionary by pruning nested objects based on deserialization thresholds.

    This function recursively traverses the input metadata dictionary and removes any nested objects 
    that specify a `deserializationThreshold` value greater than the given `deserializationDepth`. 
    If a threshold is encountered and the provided depth is insufficient, the corresponding object 
    (and its children) will be replaced with an empty dictionary. Additionally, the `deserializationThreshold` 
    key is removed from the final output.

    Args:
        metadata (Dict[str, Any]): The metadata dictionary to process. Must be a dictionary.
        deserializationDepth (int): The maximum depth at which deserialization is allowed. Must be a non-negative integer.

    Returns:
        dict: A pruned version of the original metadata, with restricted structures removed. Returns None if the input is invalid.

    Notes:
        - Any non-dictionary or non-list items are preserved as-is.
        - If `metadata` is not a dictionary or if `deserializationDepth` is not an integer, `None` is returned.
        - Negative value of `deserializationThreshold` is considered a maximum threshold,
          which means that the object will be removed regardless of the deserialization depth.
    """
    if not isinstance(metadata, dict):
        logging.debug(f"Provided metadata cannot be deserialized, invalid type: {type(metadata).__name__}")
        return None
    
    if not isinstance(deserializationDepth, int):
        logging.debug(f"Deserialization depth cannot be set, invalid type: {type(deserializationDepth).__name__}")
        return None
    
    def prune_object(obj: Any) -> Any:
        if isinstance(obj, dict):
            if "deserializationThreshold" in obj:
                deserializationThreshold = obj["deserializationThreshold"]
                if isinstance(deserializationThreshold, int):
                    logging.debug(f"Deserialization threshold set to a new value: {deserializationThreshold}")
                    if deserializationThreshold < 0:
                        logging.debug(f"Negative deserialization threshold, ignoring deserialization depth, removing object")
                        return {}
                    if deserializationDepth < deserializationThreshold:
                        logging.debug(f"Deserialization threshold exceeds deserialization depth, removing object")
                        return {}

            filtered_obj = {}
            logging.debug(f"Rebuilding metadata object with keys: {", ".join(obj.keys())}")
            for key, value in obj.items():
                if key == "deserializationThreshold":
                    logging.debug(f"Deserialization threshold key 'deserializationThreshold' filtered out")
                    continue
                logging.debug(f"Pruning key and re-indexing its value: {key}")
                filtered_obj[key] = prune_object(value)
            return filtered_obj
        elif isinstance(obj, list):
            return [prune_object(item) for item in obj]

        return obj

    logging.debug(f"Attempting to prune metadata object with deserialization depth: {deserializationDepth}")
    return prune_object(metadata)


























def process_keys(obj: dict, keys: List[str], strict: bool = False) -> Dict[str, List[str]]:
    """
    Processes a list of hierarchical metadata keys and maps them to their corresponding base keys 
    in a provided dictionary. Supports wildcard-based prioritization (`**` and `*`) and recursive key matching.

    This function is primarily used to prepare a mapping of keys for metadata deserialization or filtering. 
    It breaks down dot-separated keys into root keys and subkeys (e.g., "user.name" → "user": ["name"]) 
    and handles special wildcard patterns:
    
        - Keys starting with `**` are given highest priority.
        - Keys starting with `*` are given second priority.
        - Other keys follow in alphanumeric order.

    If a key cannot be found and `strict` is `True`, a `KeyError` is raised. Otherwise, missing keys are silently ignored.

    Parameters:
        obj (dict): The dictionary whose keys are matched against the input list.
        keys (List[str]): List of dot-separated string keys to process.
        strict (bool): Whether to enforce strict matching (raise `KeyError` on missing keys).

    Returns:
        processed_keys (Dict[str, List[str]]): A dictionary mapping top-level keys in `obj` (or wildcards `*`, `**`) 
        to their corresponding subkeys to extract or filter.

    Raises:
        KeyError: If `strict` is `True` and no part of the key exists in `obj`.

    Example:
        >>> obj = {"user": {"name": "Alice"}, "system": {"os": "Linux"}}
        >>> keys = ["user.name", "system.os", "**.debug"]
        >>> process_keys(obj, keys)
        {
            "user": ["name"],
            "system": ["os"],
            "**": ["debug"]
        }
    """
    logging.debug(f"Sorting keys by WildCards('**', '*') first and Alphanumeric values second to prioritize the WildCards and avoid repetead matches")
    sorted_keys = sorted(keys, key=lambda x: (0 if x.startswith("**") else 1 if x.startswith("*") else 2, x))
    logging.debug(f"Sorted keys: {", ".join(obj.keys())}")
    processed_keys = {}
    for key in sorted_keys:
        original_key = key
        logging.debug(f"Attempting to match key: {original_key}")
        while key not in obj.keys() and key != "*" and key != "**":
            logging.debug(f"Full key couldn't be matched to an entry. Attempting to split the key and match the parts")
            key_parts = key.rsplit('.', 1)
            logging.debug(f"Key successfully split into: {original_key} -> '{key_parts[0]}' and '{key_parts[1] if key_parts[1] else ''}'")
            if len(key_parts) == 1 or key_parts[0] == '':
                if strict:
                    logging.debug(f"Key '{key}' not found in the provided metadata, raising 'KeyError' as the existence of the provided keys is enforced strictly")
                    raise KeyError(f"Key '{key}' not found in the provided metadata")
                logging.debug(f"Key '{key}' not found in the provided metadata, skipping the key as the existence of the provided keys is not enforced strictly")
                break
            logging.debug(f"Key was split successfully. Remapping the root of the split as the key to use in the further attempts to match: {key_parts[0]}")
            key = key_parts[0]

        if key in obj or key == "*" or key == "**":
            if key not in processed_keys:
                logging.debug(f"Key hasn't been re-indexed yet. Indexing: {key}")
                processed_keys[key] = []

            next_step_key = None
            logging.debug(f"Extracting a sub-key from the original: {original_key}")
            if original_key.startswith(key + "."):
                next_step_key = original_key[len(key) + 1:]
                if len(next_step_key) > 1:
                    logging.debug(f"Sub-key extracted successfully: {next_step_key}")

            if next_step_key and next_step_key != '':
                if "**" in processed_keys and next_step_key in processed_keys["**"]: 
                    logging.debug(f"Sub-key has already been captured by the WildCard('**'). Skipping...")
                    continue
                if "*" in processed_keys and next_step_key in processed_keys["*"]:
                    logging.debug(f"Sub-key has already been captured by the WildCard('*'). Skipping...")
                    continue
                if key in processed_keys and next_step_key in processed_keys[key]:
                    logging.debug(f"Sub-key is a duplicate - it has already been captured. Skipping...")
                    continue
                logging.debug(f"Sub-key has been captured and indexed under the key: {key}")
                processed_keys[key].append(next_step_key)
            else:
                logging.debug(f"Failed to extract a sub-key. Skipping...")

    logging.debug(f"Returning processed keys as a valid JSON dictionary: \n{json.dumps(processed_keys, indent=4)}")
    return processed_keys
    