import re
import tempfile
from pathlib import Path
from contextlib import contextmanager
from enum import Enum
from functools import partial
from typing import Callable
import unicodedata


def check_prefix(prefix: str) -> re.Pattern:
    return re.compile(rf"^{re.escape(prefix)}")


def passthrough(whatever):
    return whatever


def sanitize_filename(filename: str | Path, allow_separators: bool = False) -> str:
    """Sanitize a filename"""
    if not filename:
        return "unnamed"

    if not isinstance(filename, str):
        filename = str(filename)

    # Control characters
    filename = unicodedata.normalize("NFKC", filename)
    filename = re.sub(r"[\x00-\x1F\x7F]", "", filename)
    filename = filename.strip()

    # Path separators
    if not allow_separators:
        filename = filename.replace("/", "").replace("\\", "")

    # Other risky chars
    filename = re.sub(r'[<>:"|*]', "", filename)
    filename = re.sub(r'[?]', "_", filename)

    return filename


def parse_semester(semester: str) -> tuple[bool, int]:
    '''Parse a semester string like "WS23/24" or "SS2024" or "WiSe 2023/2024" into a tuple (is_ws, start_year).'''
    semester = semester.lower()
    is_ws = "ws" in semester or "winter" in semester or "wis" in semester
    number_groups = [int(s) for s in re.findall(r'\d{2,4}', semester)]
    if not number_groups:
        raise ValueError(f"Could not parse year from semester string: {semester}")
    if number_groups[0] >= 2000:
        start_year = number_groups[0]
    else:
        start_year = 2000 + number_groups[0]
    return is_ws, start_year


# @contextmanager
# def create_temp_dir(prefix: str = "autumoodle_"):
#     with tempfile.TemporaryDirectory(prefix=prefix) as d:
#         yield Path(d)
def create_temp_dir(prefix: str = "autumoodle_") -> Path:
    d = tempfile.mkdtemp(prefix=prefix)
    return Path(d)


# @contextmanager
# def create_temp_file(suffix: str = "", prefix: str = "autumoodle_"):
#     with tempfile.NamedTemporaryFile(suffix=suffix, prefix=prefix) as f:
#         yield Path(f.name)
def create_temp_file(suffix: str = "", prefix: str = "autumoodle_") -> Path:
    f = tempfile.NamedTemporaryFile(suffix=suffix, prefix=prefix, delete=False)
    f.close()
    return Path(f.name)


class PatternMatcher:
    class MatchType(Enum):
        LITERAL = "literal"
        REGEX = "regex"

    match: Callable[[str], bool]

    def __init__(self, pattern: str, match_type: MatchType | str):
        if isinstance(match_type, str):
            try:
                match_type = self.MatchType(match_type.lower())
            except ValueError:
                raise ValueError(f"Invalid match_type: '{match_type}'. Must be one of {[e.value for e in self.MatchType]}")

        if match_type == self.MatchType.LITERAL:
            self.match = partial(self._match_literal, pattern)
        elif match_type == self.MatchType.REGEX:
            self.match = partial(self._match_regex, re.compile(pattern))
        else:
            raise ValueError(f"Unsupported match_type: {match_type}")

    @staticmethod
    def _match_literal(src: str, text: str) -> bool:
        return src == text

    @staticmethod
    def _match_regex(pattern: re.Pattern, text: str) -> bool:
        return bool(pattern.search(text))
