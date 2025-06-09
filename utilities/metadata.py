from flask import current_app as app
from typing import Any, Dict, List
from pathlib import Path
import logging
import json

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

def extract_metadata_properties(metadata: dict,  keys: List[str], mode: str="include", strict: bool=False):
    """
    Extracts or excludes specific keys from a metadata dictionary based on the selected mode.

    Modes:
        - "include": Returns a dictionary with only the specified keys.
                     If `strict` is True, raises a KeyError if any key is missing.
        - "exclude": Returns a dictionary without the specified keys.
    
    Parameters:
        metadata (dict): The metadata dictionary to filter.
        keys (List[str]): List of keys to include or exclude considering the mode.
        mode (str): "include" to return only specified keys, "exclude" to remove them.
        strict (bool): If True (and mode is "include"), raises KeyError for any missing keys.

    Returns:
        dict: Filtered dictionary based on mode and keys,
                    or `None` in case of a failure.
    """
    if not isinstance(metadata, dict):
        logging.debug(f"Provided object is not a valid metadata object")
        return None

    if mode not in {"include", "exclude"}:
        logging.debug(f"Invalid extraction mode provided: {mode}")
        return None

    if mode == "include":
        if strict:
            logging.debug(f"Strict mode enabled, checking for required key(s): {keys}")
            missing_keys = [key for key in keys if key not in metadata]
            if missing_keys:
                logging.debug(f"Missing required key(s): {', '.join(missing_keys)}")
                return None

        included = {key: metadata[key] for key in keys if key in metadata}
        logging.debug(f"Included key(s): {list(included.keys())}")
        return included
    

    excluded = {key: value for key, value in metadata.items() if key not in keys}
    logging.debug(f"Excluded key(s): {list(excluded.keys())}")
    return excluded

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