import pytest
from utilities.metadata import deserialize_metadata


# ---------------------------------------------------------------------------
# Sample metadata fixture
# ---------------------------------------------------------------------------

sample_metadata = {
    "": {
        "": 1,
        "dot": 2,
    },
    ".": {
        "": True,
        ".": True,
    },
    "..": {
        "": True,
        "dot": True,
        "key": False,
    },
    "...": {
        "": True,
        "key": False,
        "logging": {
            "not": {
                "the": {
                    "best": "solution!",
                },
            },
        },
    },
    "user": {
        "name": "Alice",
        "email": "alice@example.com",
    },
    "system": {
        "**": {
            "best": 1,
        },
        "os": "Linux",
        "version": "22.04",
    },
    "extra": {
        "debug": True,
        "details": {
            "level": "high",
        },
        "logging": {
            "level": {
                "no joker can catch me": True,
            },
            "buggy": True,
        },
    },
    ".dotfiles": {
        ".zprofile.conf": True,
        ".bash_history": True,
        ".profile.X11": True,
    },
}


# ---------------------------------------------------------------------------
# Invalid input tests
# ---------------------------------------------------------------------------

def test_empty_metadata_and_keys():
    with pytest.raises(TypeError):
        deserialize_metadata({}, [], [])

@pytest.mark.parametrize("bad_input", [{}, "not a dict", 42, None, ["user"]])
def test_non_dict_metadata_raises(bad_input):
    with pytest.raises(TypeError):
        deserialize_metadata(bad_input, [], [])


@pytest.mark.parametrize("bad_extract_keys", ["user", {"key": "value"}, None])
def test_invalid_extract_keys_type(bad_extract_keys):
    with pytest.raises(TypeError):
        deserialize_metadata(sample_metadata, bad_extract_keys, [])


@pytest.mark.parametrize("bad_exclude_keys", ["extra", {"key": "value"}, None])
def test_invalid_exclude_keys_type(bad_exclude_keys):
    with pytest.raises(TypeError):
        deserialize_metadata(sample_metadata, [], bad_exclude_keys)


@pytest.mark.parametrize("bad_flag", ["yes", 1, None, {"key": "value"}])
def test_invalid_strict_flags(bad_flag):
    with pytest.raises(TypeError):
        deserialize_metadata(sample_metadata, [], [], extract_strict=bad_flag)
    with pytest.raises(TypeError):
        deserialize_metadata(sample_metadata, [], [], exclude_strict=bad_flag)

@pytest.mark.parametrize("bad_keys", [[1, 2], [None], [{}], [42, "valid"]])
def test_invalid_elements_in_extract_keys(bad_keys):
    with pytest.raises(TypeError):
        deserialize_metadata(sample_metadata, bad_keys, [])

@pytest.mark.parametrize("bad_keys", [[1, 2], [None], [{}], [42, "valid"]])
def test_invalid_elements_in_exclude_keys(bad_keys):
    with pytest.raises(TypeError):
        deserialize_metadata(sample_metadata, [], bad_keys)

def test_invalid_extract_and_exclude_keys():
    with pytest.raises(TypeError):
        deserialize_metadata(sample_metadata, ["user"], [None])

def test_extract_strict_with_nonexistent_key():
    with pytest.raises(KeyError):
        deserialize_metadata(sample_metadata, ["nonexistent"], [], extract_strict=True)

def test_exclude_strict_with_nonexistent_key():
    with pytest.raises(KeyError):
        deserialize_metadata(sample_metadata, [], ["nonexistent"], exclude_strict=True)


# ---------------------------------------------------------------------------
# Extraction tests
# ---------------------------------------------------------------------------

def test_extract_empty_keys():
    result = deserialize_metadata(
        sample_metadata,
        extract_keys=[],
        exclude_keys=[],
        extract_strict=True,
        exclude_strict=True,
    )

    assert result == sample_metadata


def test_extract_simple_keys():
    result = deserialize_metadata(
        sample_metadata,
        extract_keys=["user", "user.name", "user.email", "system.version", "extra", ".dotfiles"],
        exclude_keys=[],
        extract_strict=True,
        exclude_strict=True,
    )

    assert result == {
        "user": {"name": "Alice", "email": "alice@example.com"},
        "system": {"version": "22.04"},
        ".dotfiles": {},
        "extra": {},
    }


def test_extract_nested_keys():
    result = deserialize_metadata(
        sample_metadata,
        extract_keys=["user.name", "user.email", "extra.details.level"],
        exclude_keys=[],
        extract_strict=True,
        exclude_strict=True,
    )

    assert result == {
        "user": {"name": "Alice", "email": "alice@example.com"},
        "extra": {"details": {"level": "high"}},
    }


def test_extract_empty_string_keys():
    result = deserialize_metadata(
        sample_metadata,
        extract_keys=[""],
        exclude_keys=[],
        extract_strict=True,
        exclude_strict=True,
    )

    assert "" in result and result[""] == {}


def test_extract_nested_dot_keys():
    result = deserialize_metadata(
        sample_metadata,
        extract_keys=[".dotfiles", ".dotfiles..zprofile.conf", ".dotfiles..bash_history"],
        exclude_keys=[],
        extract_strict=True,
        exclude_strict=True,
    )

    assert result == {
        ".dotfiles": {
            ".zprofile.conf": True,
            ".bash_history": True,
        }
    }


def test_extract_nested_empty_string_and_dot_keys():
    result = deserialize_metadata(
        sample_metadata,
        extract_keys=["....", "...", "...", "...", "...", "..", "..", "..", ".", ".", ""],
        exclude_keys=[],
        extract_strict=True,
        exclude_strict=True,
    )

    assert result == {
        "": {"": 1},
        ".": {"": True, ".": True},
        "..": {"": True},
        "...": {"": True},
    }


def test_extract_top_level_wildcard():
    result = deserialize_metadata(
        sample_metadata,
        extract_keys=["*"],
        exclude_keys=[],
        extract_strict=True,
        exclude_strict=True,
    )

    assert result == {
        "": {},
        ".": {},
        "..": {},
        "...": {},
        "user": {},
        "extra": {},
        "system": {},
        ".dotfiles": {},
    }


def test_extract_simple_wildcard_keys():
    result = deserialize_metadata(
        sample_metadata,
        extract_keys=["*.details"],
        exclude_keys=[],
        extract_strict=True,
        exclude_strict=True,
    )

    assert "extra" in result and "details" in result["extra"]


def test_extract_nested_wildcard_keys():
    result = deserialize_metadata(
        sample_metadata,
        extract_keys=["*.*.level"],
        exclude_keys=[],
        extract_strict=True,
        exclude_strict=True,
    )

    assert "extra" in result and "details" in result["extra"] and "level" in result["extra"]["details"]


def test_extract_mixed_simple_wildcard_and_nested_keys():
    result = deserialize_metadata(
        sample_metadata,
        extract_keys=["*.details", "user.name", "user.email", "extra.details.level"],
        exclude_keys=[],
        extract_strict=True,
        exclude_strict=True,
    )

    assert "user" in result and "name" in result["user"] and "email" in result["user"]
    assert "extra" in result and "details" in result["extra"] and "level" in result["extra"]["details"]


def test_extract_catch_all_joker():
    result = deserialize_metadata(
        sample_metadata,
        extract_keys=["**"],
        exclude_keys=[],
        extract_strict=True,
        exclude_strict=True,
    )

    assert result == sample_metadata


def test_extract_simple_joker_keys():
    result = deserialize_metadata(
        sample_metadata,
        extract_keys=["**.level"],
        exclude_keys=[],
        extract_strict=True,
        exclude_strict=True,
    )

    assert "extra" in result and "details" in result["extra"] and "logging" in result["extra"]
    assert "level" in result["extra"]["details"] and "level" in result["extra"]["logging"]


def test_extract_peculiar_joker_keys():
    result = deserialize_metadata(
        sample_metadata,
        extract_keys=["**.logging.level"],
        exclude_keys=[],
        extract_strict=True,
        exclude_strict=True,
    )

    assert result == {
        "extra": {
            "logging": {
                "level": {},
            }
        }
    }


def test_extract_nested_peculiar_joker_keys():
    result = deserialize_metadata(
        sample_metadata,
        extract_keys=["**.logging.**.best"],
        exclude_keys=[],
        extract_strict=True,
        exclude_strict=True,
    )

    assert result == {
        "...": {
            "logging": {
                "not": {"the": {"best": "solution!"}},
            }
        }
    }


def test_extract_multiple_peculiar_joker_keys():
    result = deserialize_metadata(
        sample_metadata,
        extract_keys=["**.logging.**.best", "**.logging.level"],
        exclude_keys=[],
        extract_strict=True,
        exclude_strict=True,
    )

    assert result == {
        "...": {
            "logging": {
                "not": {"the": {"best": "solution!"}},
            }
        },
        "extra": {
            "logging": {
                "level": {},
            }
        },
    }


def test_extract_multiple_overlapping_peculiar_joker_keys():
    result = deserialize_metadata(
        sample_metadata,
        extract_keys=["**.logging.**", "**.logging.**.best"],
        exclude_keys=[],
        extract_strict=True,
        exclude_strict=True,
    )

    assert result == {
        "...": {
            "logging": {
                "not": {"the": {"best": "solution!"}},
            }
        },
        "extra": {
            "logging": {
                "level": {"no joker can catch me": True},
                "buggy": True,
            }
        },
    }


# ---------------------------------------------------------------------------
# Exclusion tests
# ---------------------------------------------------------------------------

def test_exclude_empty_keys():
    result = deserialize_metadata(
        sample_metadata,
        extract_keys=[],
        exclude_keys=[],
        extract_strict=True,
        exclude_strict=True,
    )

    assert result == sample_metadata


def test_exclude_simple_keys():
    result = deserialize_metadata(
        sample_metadata,
        extract_keys=[],
        exclude_keys=["user", "system.version", "extra", ".dotfiles"],
        extract_strict=True,
        exclude_strict=True,
    )

    assert result == {
        "": {"": 1, "dot": 2},
        ".": {"": True, ".": True},
        "..": {"": True, "dot": True, "key": False},
        "...": {
            "": True,
            "key": False,
            "logging": {"not": {"the": {"best": "solution!"}}},
        },
        "system": {"**": {"best": 1,}, "os": "Linux"},
    }


def test_exclude_nested_keys():
    result = deserialize_metadata(
        sample_metadata,
        extract_keys=[],
        exclude_keys=["user.name", "extra.details.level"],
        extract_strict=True,
        exclude_strict=True,
    )

    assert result == {
        "": {"": 1, "dot": 2},
        ".": {"": True, ".": True},
        "..": {"": True, "dot": True, "key": False},
        "...": {
            "": True,
            "key": False,
            "logging": {"not": {"the": {"best": "solution!"}}},
        },
        "user": {"email": "alice@example.com"},
        "system": {"**": {"best": 1,}, "os": "Linux", "version": "22.04"},
        "extra": {
            "debug": True,
            "details": {},
            "logging": {"buggy": True, "level": {"no joker can catch me": True}},
        },
        ".dotfiles": {".zprofile.conf": True, ".profile.X11": True, ".bash_history": True},
    }


def test_exclude_empty_string_keys():
    result = deserialize_metadata(
        sample_metadata,
        extract_keys=[],
        exclude_keys=[""],
        extract_strict=True,
        exclude_strict=True,
    )

    assert result == {
        ".": {"": True, ".": True},
        "..": {"": True, "dot": True, "key": False},
        "...": {
            "": True,
            "key": False,
            "logging": {"not": {"the": {"best": "solution!"}}},
        },
        "user": {"name": "Alice", "email": "alice@example.com"},
        "system": {"**": {"best": 1,}, "os": "Linux", "version": "22.04"},
        "extra": {
            "debug": True,
            "details": {"level": "high"},
            "logging": {"buggy": True, "level": {"no joker can catch me": True}},
        },
        ".dotfiles": {".zprofile.conf": True, ".profile.X11": True, ".bash_history": True},
    }


def test_exclude_nested_dot_keys():
    result = deserialize_metadata(
        sample_metadata,
        extract_keys=[],
        exclude_keys=[".dotfiles..zprofile.conf", ".dotfiles..bash_history"],
        extract_strict=True,
        exclude_strict=True,
    )

    assert result == {
        "": {"": 1, "dot": 2},
        ".": {"": True, ".": True},
        "..": {"": True, "dot": True, "key": False},
        "...": {
            "": True,
            "key": False,
            "logging": {"not": {"the": {"best": "solution!"}}},
        },
        "user": {"name": "Alice", "email": "alice@example.com"},
        "system": {"**": {"best": 1,}, "os": "Linux", "version": "22.04"},
        "extra": {
            "debug": True,
            "details": {"level": "high"},
            "logging": {"buggy": True, "level": {"no joker can catch me": True}},
        },
        ".dotfiles": {".profile.X11": True},
    }


def test_exclude_nested_empty_string_and_dot_keys():
    result = deserialize_metadata(
        sample_metadata,
        extract_keys=[],
        exclude_keys=["....", "...", "..", ".", ""],
        extract_strict=True,
        exclude_strict=True,
    )

    assert result == {
        "...": {
            "key": False,
            "logging": {"not": {"the": {"best": "solution!"}}},
        },
        "user": {"name": "Alice", "email": "alice@example.com"},
        "system": {"**": {"best": 1,}, "os": "Linux", "version": "22.04"},
        "extra": {
            "debug": True,
            "details": {"level": "high"},
            "logging": {"buggy": True, "level": {"no joker can catch me": True}},
        },
        ".dotfiles": {".zprofile.conf": True, ".profile.X11": True, ".bash_history": True},
    }


def test_exclude_top_level_wildcard():
    result = deserialize_metadata(
        sample_metadata,
        extract_keys=[],
        exclude_keys=["*"],
        extract_strict=True,
        exclude_strict=True,
    )

    assert result == {}


def test_exclude_simple_wildcard_keys():
    result = deserialize_metadata(
        sample_metadata,
        extract_keys=[],
        exclude_keys=["*.details", "*.dot"],
        extract_strict=True,
        exclude_strict=True,
    )

    assert result == {
        "": {"": 1},
        ".": {"": True, ".": True},
        "..": {"": True, "key": False},
        "...": {
            "": True,
            "key": False,
            "logging": {"not": {"the": {"best": "solution!"}}},
        },
        "user": {"name": "Alice", "email": "alice@example.com"},
        "system": {"**": {"best": 1,}, "os": "Linux", "version": "22.04"},
        "extra": {
            "debug": True,
            "logging": {"buggy": True, "level": {"no joker can catch me": True}},
        },
        ".dotfiles": {".zprofile.conf": True, ".profile.X11": True, ".bash_history": True},
    }


def test_exclude_nested_wildcard_keys():
    result = deserialize_metadata(
        sample_metadata,
        extract_keys=[],
        exclude_keys=["*.*.level"],
        extract_strict=True,
        exclude_strict=True,
    )

    assert result == {
        "": {"": 1, "dot": 2},
        ".": {"": True, ".": True},
        "..": {"": True, "dot": True, "key": False},
        "...": {
            "": True,
            "key": False,
            "logging": {"not": {"the": {"best": "solution!"}}},
        },
        "user": {"name": "Alice", "email": "alice@example.com"},
        "system": {"**": {"best": 1,}, "os": "Linux", "version": "22.04"},
        "extra": {
            "debug": True,
            "details": {},
            "logging": {"buggy": True},
        },
        ".dotfiles": {".zprofile.conf": True, ".profile.X11": True, ".bash_history": True},
    }


def test_exclude_mixed_simple_wildcard_and_nested_keys():
    result = deserialize_metadata(
        sample_metadata,
        extract_keys=[],
        exclude_keys=["*.details", "user.name", "extra.details.level"],
        extract_strict=True,
        exclude_strict=True,
    )

    assert result == {
        "": {"": 1, "dot": 2},
        ".": {"": True, ".": True},
        "..": {"": True, "dot": True, "key": False},
        "...": {
            "": True,
            "key": False,
            "logging": {"not": {"the": {"best": "solution!"}}},
        },
        "user": {"email": "alice@example.com"},
        "system": {"**": {"best": 1,}, "os": "Linux", "version": "22.04"},
        "extra": {
            "debug": True,
            "logging": {"buggy": True, "level": {"no joker can catch me": True}},
        },
        ".dotfiles": {".zprofile.conf": True, ".profile.X11": True, ".bash_history": True},
    }


def test_exclude_catch_all_joker():
    result = deserialize_metadata(
        sample_metadata,
        extract_keys=[],
        exclude_keys=["**"],
        extract_strict=True,
        exclude_strict=True,
    )

    assert result == {}


def test_exclude_simple_joker_keys():
    result = deserialize_metadata(
        sample_metadata,
        extract_keys=[],
        exclude_keys=["**.level"],
        extract_strict=True,
        exclude_strict=True,
    )

    assert result == {
        "": {"": 1, "dot": 2},
        ".": {"": True, ".": True},
        "..": {"": True, "dot": True, "key": False},
        "...": {
            "": True,
            "key": False,
            "logging": {"not": {"the": {"best": "solution!"}}},
        },
        "user": {"name": "Alice", "email": "alice@example.com"},
        "system": {"**": {"best": 1,}, "os": "Linux", "version": "22.04"},
        "extra": {
            "debug": True,
            "details": {},
            "logging": {"buggy": True},
        },
        ".dotfiles": {".zprofile.conf": True, ".profile.X11": True, ".bash_history": True},
    }


def test_exclude_peculiar_joker_keys():
    result = deserialize_metadata(
        sample_metadata,
        extract_keys=[],
        exclude_keys=["**.logging.level"],
        extract_strict=True,
        exclude_strict=True,
    )

    assert result == {
        "": {"": 1, "dot": 2},
        ".": {"": True, ".": True},
        "..": {"": True, "dot": True, "key": False},
        "...": {
            "": True,
            "key": False,
            "logging": {"not": {"the": {"best": "solution!"}}},
        },
        "user": {"name": "Alice", "email": "alice@example.com"},
        "system": {"**": {"best": 1,}, "os": "Linux", "version": "22.04"},
        "extra": {
            "debug": True,
            "details": {"level": "high"},
            "logging": {"buggy": True},
        },
        ".dotfiles": {".zprofile.conf": True, ".profile.X11": True, ".bash_history": True},
    }


def test_exclude_nested_peculiar_joker_keys():
    result = deserialize_metadata(
        sample_metadata,
        extract_keys=[],
        exclude_keys=["**.logging.**.best"],
        extract_strict=True,
        exclude_strict=True,
    )

    assert result == {
        "": {"": 1, "dot": 2},
        ".": {"": True, ".": True},
        "..": {"": True, "dot": True, "key": False},
        "...": {
            "": True,
            "key": False,
            "logging": {"not": {"the": {}}},
        },
        "user": {"name": "Alice", "email": "alice@example.com"},
        "system": {"**": {"best": 1,}, "os": "Linux", "version": "22.04"},
        "extra": {
            "debug": True,
            "details": {"level": "high"},
            "logging": {"buggy": True, "level": {"no joker can catch me": True}},
        },
        ".dotfiles": {".zprofile.conf": True, ".profile.X11": True, ".bash_history": True},
    }


def test_exclude_multiple_peculiar_joker_keys():
    result = deserialize_metadata(
        sample_metadata,
        extract_keys=[],
        exclude_keys=["**.logging.**.best", "**.logging.level"],
        extract_strict=True,
        exclude_strict=True,
    )

    assert result == {
        "": {"": 1, "dot": 2},
        ".": {"": True, ".": True},
        "..": {"": True, "dot": True, "key": False},
        "...": {
            "": True,
            "key": False,
            "logging": {"not": {"the": {}}},
        },
        "user": {"name": "Alice", "email": "alice@example.com"},
        "system": {"**": {"best": 1,}, "os": "Linux", "version": "22.04"},
        "extra": {
            "debug": True,
            "details": {"level": "high"},
            "logging": {"buggy": True},
        },
        ".dotfiles": {".zprofile.conf": True, ".profile.X11": True, ".bash_history": True},
    }


def test_exclude_multiple_overlapping_peculiar_joker_keys():
    result = deserialize_metadata(
        sample_metadata,
        extract_keys=[],
        exclude_keys=["**.logging.**", "**.logging.**.best"],
        extract_strict=True,
        exclude_strict=True,
    )

    assert result == {
        "": {"": 1, "dot": 2},
        ".": {"": True, ".": True},
        "..": {"": True, "dot": True, "key": False},
        "...": {
            "": True,
            "key": False,
            "logging": {},
        },
        "user": {"name": "Alice", "email": "alice@example.com"},
        "system": {"**": {"best": 1,}, "os": "Linux", "version": "22.04"},
        "extra": {
            "debug": True,
            "details": {"level": "high"},
            "logging": {},
        },
        ".dotfiles": {".zprofile.conf": True, ".profile.X11": True, ".bash_history": True},
    }
