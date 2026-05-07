from flask import current_app as app
from typing import Any, Dict, List
from pathlib import Path
import logging
import json

def find_metadata_files(base_dir: str=None, metadata_file: str=None, metadata_identifier: List[str]=None, metadata_accepted_types: List[str]=None):
    """
    Recursively scans a base directory for metadata files and indexes them into a registry.

    A metadata file is considered valid if:
    - Its filename matches `metadata_file`.
    - It contains a string value at the path specified by `metadata_identifier`.
    - It contains a string `type` field that matches one of the accepted types.

    Args:
        base_dir (str, optional): The directory to start the search in. Defaults to `app.config["STUDIO_BASE_DIR"]`.
        metadata_file (str, optional): The name of metadata files to look for. Defaults to `app.config["METADATA_FILE_NAME"]`.
        metadata_identifier (List[str], optional): The list of keys that point to a unique identifier in the metadata. Defaults to `app.config["METADATA_IDENTIFIER"]`.
        metadata_accepted_types (List[str], optional): List of accepted type values for metadata. Defaults to `app.config["METADATA_ACCEPTED_TYPES"]`.

    Returns:
        dict: A dictionary indexed by metadata type and identifier containing metadata content and file paths,
                    or `None` if no valid metadata files are found.
    """
    metadata_map = {}

    if not base_dir or not isinstance(base_dir, str):
        base_dir = app.config["STUDIO_BASE_DIR"]
        logging.debug(f"Base directory was not provided or is not a valid string, defaulting to: {base_dir}")

    if not metadata_file or not isinstance(metadata_file, str):
        metadata_file = app.config["METADATA_FILE_NAME"]
        logging.debug(f"Metadata file name was not provided or is not a valid string, defaulting to: {metadata_file}")

    if not metadata_identifier or not isinstance(metadata_identifier, str):
        metadata_identifier = app.config["METADATA_IDENTIFIER"]
        logging.debug(f"Metadata identifier was not provided or is not a valid string, defaulting to: {metadata_identifier}")

    if (not metadata_accepted_types or not isinstance(metadata_accepted_types, list)
        or not all(isinstance(type, str) for type in metadata_accepted_types)):
        metadata_accepted_types = app.config["METADATA_ACCEPTED_TYPES"]
        logging.debug(f"Metadata accepted types were not provided or are invalid, defaulting to: {', '.join(metadata_accepted_types)}")

    base_dir_path = Path(base_dir)
    if not base_dir_path.exists() or not base_dir_path.is_dir():
        logging.debug(f"Base directory '{base_dir}' does not exist or is not a directory!")
        return None
    
    for path in base_dir_path.rglob(metadata_file):
        try:
            metadata = read_metadata_from_file(path)
            if not isinstance(metadata, dict):
                logging.debug(f"Failed to validate and extract serialized metadata from file")
                continue

            key = read_metadata_property(metadata, metadata_identifier)
            if not isinstance(key, str):
                logging.debug(f"No type identifier found thus not a valid metadata file")
                continue

            type = read_metadata_property(metadata, "type")
            if not isinstance(type, str):
                logging.debug(f"No type key found thus not a valid metadata file")
                continue

            if type not in metadata_accepted_types:
                logging.debug(f"Type '{type}' is not officially supported")
                continue

            if type not in metadata_map:
                logging.debug(f"New component type defined: {type}")
                metadata_map[type] = {}

            if key in metadata_map[type]:
                logging.debug(f"{type.capitalize()} '{key}' has already been defined by {metadata_map[type][key]['path']}")
                continue
            
            metadata_map[type][key] = {
                "data": metadata,
                "path": str(path.resolve()),
                "basedir": str(path.resolve().parent)
            }
            logging.debug(f"Successfully indexed {type} '{key}' from metadata file: {path}")
        except Exception as e:
            logging.debug(f"Unexpected exception occured while analyzing {path}: {e}")
            continue
    
    if not metadata_map:
        logging.debug(f"No metadata files found in '{base_dir}' with accepted types: {', '.join(metadata_accepted_types)}")
        return None

    logging.debug(f"Successfully indexed metadata files in '{base_dir}' with accepted types: {', '.join(metadata_accepted_types)}")
    return metadata_map

def filter_metadata_properties(metadata: dict,  keys: List[str], depth: int=0):
    """
    Filters out specific keys from a metadata dictionary based on the provided list of keys.

    Parameters:
        metadata (dict): The metadata dictionary to filter.
        keys (List[str]): List of keys to exclude from the metadata.
        depth (int): The depth of the metadata structure to consider for filtering.

    Returns:
        dict: Filtered dictionary based on the provided list of keys,
                    or `None` in case of a failure.
    """
    if not isinstance(metadata, dict):
        logging.debug(f"Provided object is not a valid metadata object")
        return None
    
    if not isinstance(keys, list) or not all(isinstance(key, str) for key in keys):
        logging.debug(f"Provided keys object is invalid, must be a list of strings")
        return None
    
    if not isinstance(depth, int) or (depth < 0 and depth != -1):
        logging.debug(f"Provided depth is not a valid integer value, defaulting to 0")
        depth = 0

    filtered_metadata = {}
    logging.debug(f"Rebuilding metadata object excluding keys: {", ".join(keys())}")
    for key, value in metadata.items():
        if key not in keys:
            logging.debug(f"Re-indexing the value of key: {key}")
            filtered_metadata[key] = value
    return filtered_metadata

def extract_metadata_properties(metadata: dict,  keys: List[str], strict: bool=False):
    """
    Extracts specific keys from a metadata dictionary based on the provided list of keys.
    
    Parameters:
        metadata (dict): The metadata dictionary to filter.
        keys (List[str]): List of keys to include or exclude considering the mode.
        strict (bool): Raises KeyError for any missing keys if set to True.

    Returns:
        dict: Filtered dictionary based on the provided list of keys,
                    or `None` in case of a failure.
    """
    if not isinstance(metadata, dict):
        logging.debug(f"Provided object is not a valid metadata object")
        return None
    
    if not isinstance(keys, list) or not all(isinstance(key, str) for key in keys):
        logging.debug(f"Provided keys object is invalid, must be a list of strings")
        return None
    
    if not isinstance(strict, bool):
        logging.debug(f"Provided strict mode is not a valid boolean value, defaulting to False")
        strict = False

    if strict:
        logging.debug(f"Strict mode enabled, checking for required key(s): {keys}")
        missing_keys = [key for key in keys if key not in metadata]
        if missing_keys:
            logging.debug(f"Missing required key(s): {', '.join(missing_keys)}")
            return None

    included = {key: metadata[key] for key in keys if key in metadata}
    logging.debug(f"Included key(s): {list(included.keys())}")
    return included

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
    If a key is duplicated (i.e., the same key appears more than once in the input list), it is only processed once.
    If a subkey has already been captured by a wildcard, it is not added again to avoid duplication.
    If '**' or '*' can be matched to the root of a key, they are treated as valid keys.

    Parameters:
        obj (dict): The dictionary whose keys are matched against the input list.
        keys (List[str]): List of dot-separated string keys to process.
        strict (bool): Whether to enforce strict matching (raise `KeyError` on missing keys).

    Returns:
        A tuple containing:
            processed_keys (Dict[str, List[str]]): A dictionary mapping top-level keys in `obj` excluding the wildcards.
            wildcard_keys (List[str] | None): List of subkeys associated with the wildcard `*`, or `None` if not used.
            joker_keys (List[str] | None): List of subkeys associated with the wildcard `**`, or `None` if not used.

    Raises:
        KeyError: If `strict` is `True` and no part of the key exists in `obj`.

    Example:
        >>> obj = {"user": {"name": "Alice"}, "system": {"os": "Linux"}}
        >>> keys = ["user.name", "system.os", "**.debug"]
        >>> process_keys(obj, keys, True)
        {
            "user": ["name"],
            "system": ["os"],
            "**": ["debug"]
        }
    """
    logging.debug(f"Sorting keys by WildCards('**', '*') first and Alphanumeric values second to prioritize the WildCards and avoid repetead matches")
    sorted_keys = sorted(keys, key=lambda x: (0 if x.startswith("**") else 1 if x.startswith("*") else 2, x))
    logging.debug(f"Sorted keys: {", ".join(obj.keys())}")
    exact_match_keys = {}
    wildcard_keys = None
    joker_keys  =  None
    for key in sorted_keys:
        original_key = key
        while True:
            logging.debug(f"Attempting to match key: '{key}'")
            while key not in obj.keys() and key not in {"*", "**"}:
                logging.debug(f"Full key couldn't be matched to an entry. Attempting to split the key and match the root part")
                key_parts = key.rsplit('.', 1)
                logging.debug(f"Key successfully split into: '{key}' -> '{key_parts[0]}' and '{key_parts[1] if len(key_parts) > 1 else ''}'")
                if key_parts[0] == key:
                    if strict:
                        logging.debug(f"Key '{key}' not found in the provided metadata, raising 'KeyError' as the existence of the provided keys is enforced strictly")
                        raise KeyError(f"Key '{key}' not found in the provided metadata")
                    logging.debug(f"Key '{key}' not found in the provided metadata, skipping the key as the existence of the provided keys is not enforced strictly")
                    break
                logging.debug(f"Key was split successfully. Remapping the root of the split as the key to use in the further attempts to match: '{key_parts[0]}'")
                key = key_parts[0]

            if key in obj or key in {"*", "**"}:
                next_step_key = None
                logging.debug(f"Extracting a sub-key from the original key: '{original_key}'")
                if original_key.startswith(key + "."):
                    next_step_key = original_key[len(key) + 1:]
                    if next_step_key is not None:
                        logging.debug(f"Sub-key extracted successfully: '{next_step_key}'")
                    else:
                        logging.debug(f"Couldn't extract a valid sub-key from: '{key}'")

                if key not in obj:
                    if key == "*":
                        if wildcard_keys is None:
                            logging.debug(f"WildCard('*') detected, initializing the wildcard keys list")
                            wildcard_keys = []
                        if next_step_key:
                            logging.debug(f"Successfully indexed a new sub-key under the WildCard('*'): '{next_step_key}'")
                            wildcard_keys.append(next_step_key)
                        break

                    if key == "**":
                        if joker_keys is None and next_step_key is not None:
                            logging.debug(f"WildCard('**') detected, initializing the joker keys list with the first sub-key: '{next_step_key}'")
                            joker_keys = [next_step_key]
                        elif joker_keys and next_step_key is not None:
                            logging.debug(f"Successfully indexed a new sub-key under the WildCard('**'): '{next_step_key}'")
                            joker_keys.append(next_step_key)
                        elif next_step_key is None:
                            logging.debug(f"WildCard('**') without a sub-key — catchall mode enabled!")
                            joker_keys = []
                        break

                if key == "*":
                    logging.debug(f"WildCard('*') trap detected. Wildcard keys of the level will only match exactly to the sub-keys within")

                if key == "**":
                    logging.debug(f"WildCard('**') trap detected. Joker keys of the level will only match exactly to the sub-keys within")

                if key in exact_match_keys:
                    logging.debug(f"Key has already been processed and indexed. Checking sub-keys for the possibility of key collision")

                    if joker_keys and next_step_key in joker_keys: 
                        logging.debug(f"Sub-key has already been captured by the WildCard('**') and is thus discarded as a duplicate")
                        break
                    if wildcard_keys and next_step_key in wildcard_keys:
                        logging.debug(f"Sub-key has already been captured by the WildCard('*') and is thus discarded as a duplicate")
                        break

                    if next_step_key is None or next_step_key in exact_match_keys[key]:
                        if next_step_key in exact_match_keys[key]:
                            logging.debug(f"A duplicate sub-key detected in an already indexed key: '{key}': '{next_step_key}'")

                        # A Comment
                        logging.debug(f"Attempting to split the key further down to extract a possible deeper root: '{key}'")
                        key_parts = key.rsplit('.', 1)
                        if key_parts[0] != key:
                            logging.debug(f"Successfully extracted a deeper root from the key: '{key}': '{key_parts[0]}'")
                            key = key_parts[0]
                            continue

                        logging.debug(f"Key couldn't be split down any further, definitively proving it is a duplicate")
                        break

                    logging.debug(f"Successfully indexed a sub-key under an existing key: '{key}': '{next_step_key}'")
                    exact_match_keys[key].append(next_step_key)
                else:
                    exact_match_keys[key] = []
                    if next_step_key is not None:
                        if joker_keys and next_step_key in joker_keys:
                            logging.debug(f"Sub-key has already been captured by the WildCard('**') and is thus discarded as a duplicate")
                            break
                        if wildcard_keys and next_step_key in wildcard_keys:
                            logging.debug(f"Sub-key has already been captured by the WildCard('*') and is thus discarded as a duplicate")
                            break

                        logging.debug(f"Successfully indexed a new key together along with the new sub-key: '{key}': '{next_step_key}'")
                        exact_match_keys[key].append(next_step_key)
                        break
                    logging.debug(f"Successfully indexed a new key: '{key}'")
    
            break #the infinity (loop) and beyond!
        
    logging.debug(f"Returning processed keys as a valid JSON dictionary: \n{json.dumps(exact_match_keys, indent=4)}")
    return exact_match_keys, wildcard_keys, joker_keys

def deserialize_metadata(metadata: dict, extract_keys: List[str], exclude_keys: List[str], extract_strict: bool=False, exclude_strict: bool=False):
    """
    obj key in processed_keys? pass object[key] along with processed_keys[key] and so on...
    **.obj.otherObj meant at any depth, when obj is found, otherObj is processed (exclusion only?)
    """
    deserialized_metadata = {}
    if not metadata or not isinstance(metadata, dict):
        logging.debug(f"Metadata to deserialize must be provided as a non-empty JSON dictionary, got {type(metadata).__name__} instead")
        raise TypeError(f"Metadata to deserialize must be provided as a non-empty JSON dictionary, got {type(metadata).__name__} instead")
    
    if not isinstance(extract_keys, list) or not all(isinstance(key, str) for key in extract_keys):
        logging.debug(f"Keys to extract from the metadata must be provided as a list of strings, got {type(extract_keys).__name__} instead")
        raise TypeError(f"Keys to extract from the metadata must be provided as a list of strings, got {type(extract_keys).__name__} instead")

    if not isinstance(exclude_keys, list) or not all(isinstance(key, str) for key in exclude_keys):
        logging.debug(f"Keys to filter out from the metadata must be provided as a list of strings, got {type(exclude_keys).__name__} instead")
        raise TypeError(f"Keys to filter out from the metadata must be provided as a list of strings, got {type(exclude_keys).__name__} instead")
    
    if not isinstance(extract_strict, bool):
        logging.debug(f"Should the 'keys to extract' be enforced strictly must be provided as a bool, got {type(extract_strict).__name__} instead")
        raise TypeError(f"Should the 'keys to extract' be enforced strictly must be provided as a bool, got {type(extract_strict).__name__} instead")

    if not isinstance(exclude_strict, bool):
        logging.debug(f"Should the 'keys to filter out' be enforced strictly must be provided as a bool, got {type(exclude_strict).__name__} instead")
        raise TypeError(f"Should the 'keys to filter out' be enforced strictly must be provided as a bool, got {type(exclude_strict).__name__} instead")

    #at some point we might integrate process_keys back into this method
    if not extract_keys and not exclude_keys:
        logging.debug(f"No keys to extract or filter out were provided, returning the original metadata object")
        return metadata
    
    def extract_entries(obj: dict,  keys: List[str], strict: bool=False):
        exact_match_keys, wildcard_keys, joker_keys = process_keys(obj, keys, strict)

        joker_extractions = {}
        wildcard_extractions = {}
        exact_match_extractions = {}

        if joker_keys is not None and not joker_keys:
            return obj

        for key, value in obj.items():
            if isinstance(value, dict):
                if joker_keys is not None:
                    processed_joker_keys = [entry for entry in keys if entry.startswith("**")] + joker_keys
                    unconfirmed_joker_extraction = extract_entries(value, processed_joker_keys, False)
                    for u_j_e_key, u_j_e_value in unconfirmed_joker_extraction.items():
                        if u_j_e_key not in joker_keys:
                            if not u_j_e_value:
                                continue

                        if key not in joker_extractions:
                            joker_extractions[key] = {}
                        joker_extractions[key][u_j_e_key] = u_j_e_value

                if wildcard_keys is not None:
                    wildcard_extractions[key] = extract_entries(value, wildcard_keys, False)

                if key in exact_match_keys:
                    exact_match_extractions[key] = extract_entries(value, exact_match_keys[key], strict)
            elif isinstance(value, list):
                #_extracted_metadata[key] = [extract_metadata_entries(item) for item in value] list operations to be implemented
                pass
            else: 
                if key in exact_match_keys or wildcard_keys and key in wildcard_keys or joker_keys and key in joker_keys:
                    exact_match_extractions[key] = value

        def merge_objs(obj1={}, obj2={}, obj3={}):
            merged_obj = {}

            for obj in [obj1, obj2, obj3]:
                for key, value in obj.items():
                    if key not in merged_obj:
                        merged_obj[key] = value
                    elif isinstance(value, dict):
                        merged_obj[key] = merge_objs(merged_obj[key], value)  
            return merged_obj              

        return merge_objs(joker_extractions, wildcard_extractions, exact_match_extractions)

    def exclude_entries(obj: dict,  keys: List[str], strict: bool=False):
        exact_match_keys, wildcard_keys, joker_keys = process_keys(obj, keys, strict)

        if joker_keys is not None and not joker_keys:
            return {}

        if wildcard_keys is not None and not wildcard_keys:
            return {}

        filtered_metadata = {}
        for key, value in obj.items():
            if isinstance(value, dict):
                if key not in exact_match_keys:
                    filtered_metadata[key] = value
                elif exact_match_keys[key]:
                    filtered_metadata[key] = exclude_entries(value, exact_match_keys[key], strict)

                if wildcard_keys and key in filtered_metadata:
                    filtered_metadata[key] = exclude_entries(filtered_metadata[key], wildcard_keys, False)

                if joker_keys and key in filtered_metadata:
                    processed_joker_keys = [entry for entry in keys if entry.startswith("**")] + joker_keys
                    filtered_metadata[key] = exclude_entries(filtered_metadata[key], processed_joker_keys, False)
            elif isinstance(value, list):
                #_extracted_metadata[key] = [extract_metadata_entries(item) for item in value] list operations to be implemented
                pass
            else: 
                if wildcard_keys and key in wildcard_keys:
                    continue
                if joker_keys and key in joker_keys:
                    continue
                if key in exact_match_keys:
                    continue

                filtered_metadata[key] = value
        return filtered_metadata

    if extract_keys:
        deserialized_metadata = extract_entries(metadata, extract_keys, extract_strict)

    if exclude_keys:
        deserialized_metadata = exclude_entries(deserialized_metadata if deserialized_metadata else metadata, exclude_keys, exclude_strict)
    
    return deserialized_metadata

def read_metadata_property(metadata: dict, keys: List[str] | str) -> Any:
    """
    Safely retrieves a nested value from a metadata dictionary using a list of keys or a single key.

    This function traverses a nested dictionary (metadata) using the provided keys. If any key is missing 
    or the structure is not as expected (i.e., a non-dict encountered before reaching the final key), 
    the function logs a debug message and returns None.

    Parameters:
        metadata (dict): The dictionary to traverse.
        keys (List[str] | str): A list of keys (or a single key as a string) representing the path 
                                to the desired nested value.

    Returns:
        Any: The value at the specified nested key path,
                    or `None` if the path is invalid.
    """
    if not isinstance(metadata, dict):
        logging.debug(f"Provided object is not a valid metadata object")
        return None

    if not isinstance(keys, list):
        if not isinstance(keys, str):
            logging.debug(f"Provided keys object is invalid")
            return None
        logging.debug(f"Converting single key to list → [{keys}]")
        keys = [keys]

    logging.debug(f"Attempting to read metadata property: {' → '.join(keys)}")
    for index, key in enumerate(keys):
        if isinstance(metadata, dict):
            if key not in metadata:
                logging.debug(f"Provided metadata is missing required key: {key}")
                return None

            logging.debug(f"Crawling deeper into metadata key: {key} ({index + 1}/{len(keys)})")
            metadata = metadata[key]
        else:
            logging.debug(f"Provided metadata property is not a valid dictionary: {key}")
            return None

    logging.debug(f"Successfully extracted metadata property: {' → '.join(keys)}")
    return metadata

def read_metadata_from_file(metadata_file_path: Path) -> Any:
    """
    Reads and parses a JSON metadata file.

    Attempts to open the specified file and load its contents as a JSON object. 
    Logs warnings if the file is not found, unreadable, or contains invalid JSON.

    Parameters:
        metadata_file_path (Path): The path to the JSON metadata file.

    Returns:
        dict: The parsed JSON object if successful, otherwise `None`.
    """
    if not isinstance(metadata_file_path, Path):
        logging.debug(f"Provided metadata file path is not a valid Path object: {metadata_file_path}")
        return None

    try:
        with open(metadata_file_path, 'r', encoding="utf-8") as f:
            metadata = json.load(f)

        if not isinstance(metadata, dict):
            logging.debug(f"Metadata file {metadata_file_path} does not contain a valid dictionary object")
            return None
    except FileNotFoundError:
        logging.debug(f"Metadata file cannot be found: {metadata_file_path}")
        return None
    except json.JSONDecodeError as e:
        logging.debug(f"Failed to parse JSON in metadata file {metadata_file_path}: {e}")
        return None
    except Exception as e:
        logging.debug(f"Unexpected error while reading metadata file {metadata_file_path}: {e}")
        return None

    logging.debug(f"Successfully read contents of a metadata file: {metadata_file_path}")
    return metadata