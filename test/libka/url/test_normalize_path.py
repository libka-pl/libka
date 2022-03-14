import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / 'script.module.libka' / 'lib'))
from libka.url import URL  # noqa: E402

PATHS = [
    # No dots
    ("", ""),
    ("/", "/"),
    ("//", "//"),
    ("///", "///"),
    # Single-dot
    ("path/to", "path/to"),
    ("././path/to", "path/to"),
    ("path/./to", "path/to"),
    ("path/././to", "path/to"),
    ("path/to/.", "path/to/"),
    ("path/to/./.", "path/to/"),
    # Double-dots
    ("../path/to", "path/to"),
    ("path/../to", "to"),
    ("path/../../to", "to"),
    # Non-ASCII characters
    ("μονοπάτι/../../να/ᴜɴɪ/ᴄᴏᴅᴇ", "να/ᴜɴɪ/ᴄᴏᴅᴇ"),
    ("μονοπάτι/../../να/𝕦𝕟𝕚/𝕔𝕠𝕕𝕖/.", "να/𝕦𝕟𝕚/𝕔𝕠𝕕𝕖/"),
]


@pytest.mark.parametrize("original,expected", PATHS)
def test__normalize_path(original, expected):
    assert URL._normalize_path(original) == expected
