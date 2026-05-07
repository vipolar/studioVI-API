import pytest
from typing import List, Dict
from utilities.metadata import process_keys

sample_metadata = {
    "": {
        "": 1,
        "inner": 2
    },
    ".": {
        "": 1,
        "inner": 2
    },
    ".": {
        "": True,
        ".": True
    },
    "..": {
        "dot": True,
        "key": False
    },
    "...": {
        "": True,
        "key": False
    },
    "user": {
        "name": "Alice",
        "email": "alice@example.com"
    },
    "system": {
        "os": "Linux",
        "version": "22.04"
    },
    "extra": {
        "debug": True,
        "details": {
            "level": "high"
        }
    },
    ".dotfiles": {
        ".zprofile.conf": True,
        ".bash_history": True,
        ".profile.X11": True
    }
}

def test_empty_keys():
    result = process_keys(sample_metadata, [], strict=False)
    assert result == {}

def test_simple_keys():
    result = process_keys(sample_metadata, ['user.name', 'system.version'], strict=False)
    assert result == {
        'user': ['name'],
        'system': ['version']
    }

def test_missing_key_non_strict():
    result = process_keys(sample_metadata, ['nonexistent.key'], strict=False)
    assert result == {}

def test_missing_key_strict_raises():
    with pytest.raises(KeyError):
        process_keys(sample_metadata, ['nonexistent.key'], strict=True)

def test_wildcard_priority_sorting():
    result = process_keys(sample_metadata, ['*.user', '**.name', 'user.name'], strict=True)
    # We only test sorting precedence indirectly (no KeyError)
    assert 'user' in result or '*' in result or '**' in result
    assert 'name' not in result["user"]
    assert 'name' not in result["*"]
    assert 'name' in result["**"]    

def test_duplicate_subkeys_ignored():
    result = process_keys(sample_metadata, ['user.name', 'user.name'], strict=False)
    assert result == {'user': ['name']}

def test_double_dot_keys():
    result = process_keys(sample_metadata, ['user..name'], strict=False)
    # Should interpret as "user" → ".name"
    assert result == {'user': ['.name']}

def test_empty_string_keys():
    result = process_keys(sample_metadata, ['.inner'], strict=False)
    assert "" in result and "inner" in result[""]

def test_top_level_empty_key_only():
    result = process_keys(sample_metadata, [''], strict=False)
    assert "" in result
    assert result[""] == []

def test_deep_wildcard_behavior():
    result = process_keys(sample_metadata, ['**.details.level'], strict=False)
    assert "**" in result and "details.level" in result["**"]

def test_multiple_nested_keys():
    result = process_keys(sample_metadata, ['user.name', 'user.email', 'extra.details.level'], strict=False)
    assert "user" in result and "name" in result["user"] and "email" in result["user"]
    assert "extra" in result and "details.level" in result["extra"]

def test_multiple_nested_dot_keys():
    result = process_keys(sample_metadata, ['.dotfiles', '.dotfiles..zprofile.conf', '.dotfiles..bash_history'], strict=False)
    assert ".dotfiles" in result and ".zprofile.conf" in result[".dotfiles"] and ".bash_history" in result[".dotfiles"]

def test_dots_to_empty_string_keys():
    result = process_keys(sample_metadata, ['....', '...', '...', '..', '..', '..', '.', '.', ''], strict=False)
    assert "" in result and "" in result[""]
    assert "." in result and "" in result["."]
    assert ".." in result and "" in result[".."]
    assert "..." in result and "" in result["..."]