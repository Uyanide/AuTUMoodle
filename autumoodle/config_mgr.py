from dataclasses import dataclass
from pathlib import Path
from enum import Enum
import re

from .utils import PatternMatcher


# Action to take when file exists & needs to be updated
class UpdateType(Enum):
    RENAME = "rename"        # like $filename.ext -> $filename_1.ext
    OVERWRITE = "overwrite"  # overwrite existing files (replace)
    SKIP = "skip"            # skip if file exists


class CourseConfigType(Enum):
    CATEGORY_AUTO = "category_auto"      # automatically create subdirs according to category titles
    CATEGORY_MANUAL = "category_manual"  # use manually defined category & file configs, only the included categories will be considered
    FILE_AUTO = "file_auto"              # put all files in the course base dir
    FILE_MANUAL = "file_manual"          # use manually defined file configs, only the included files will be considered


@dataclass
class _DefaultConfig:
    show_hidden_courses: bool = False
    cache_dir: Path = Path.home() / ".cache" / "autumoodle"
    summary_dir: Path = cache_dir / "summaries"
    session_save: bool = True
    session_save_path: Path = cache_dir / "session.json"
    log_level: str = "INFO"
    update_type: UpdateType = UpdateType.RENAME
    course_config_type: CourseConfigType = CourseConfigType.CATEGORY_AUTO


@dataclass
class _FileConfig:
    name_matcher: PatternMatcher
    destination: Path | None = None
    update_type: UpdateType = UpdateType.RENAME

    def __init__(self, config_data: dict):
        if "pattern" not in config_data or "match_type" not in config_data:
            raise ValueError("file config requires 'pattern' and 'match_type' fields")
        self.name_matcher = PatternMatcher(
            config_data["pattern"], config_data["match_type"]
        )

        if "destination" in config_data:
            self.destination = Path(config_data["destination"]).expanduser()

        self.update_type = UpdateType(config_data["update"].lower())


@dataclass
class _CategoryConfig:
    title_matcher: PatternMatcher
    destination: Path | None = None
    update_type: UpdateType = UpdateType.RENAME

    def __init__(self, config_data: dict):
        if "pattern" not in config_data or "match_type" not in config_data:
            raise ValueError("category config requires 'pattern' and 'match_type' fields")
        self.title_matcher = PatternMatcher(
            config_data["pattern"], config_data["match_type"]
        )

        if "destination" in config_data:
            self.destination = Path(config_data["destination"]).expanduser()

        self.update_type = UpdateType(config_data["update"].lower())


@dataclass
class _CourseConfig:
    title_matcher: PatternMatcher
    is_ws: bool
    start_year: int
    destination_base: Path
    categories: list[_CategoryConfig]
    files: list[_FileConfig]
    config_type: CourseConfigType = CourseConfigType.CATEGORY_AUTO
    update_type: UpdateType = UpdateType.RENAME

    def __init__(self, config_data: dict):
        # title matcher
        if "pattern" not in config_data or "match_type" not in config_data:
            raise ValueError("CourseConfig requires 'pattern' and 'match_type' fields")
        self.title_matcher = PatternMatcher(
            config_data["pattern"], config_data["match_type"]
        )

        # semester
        if "semester" not in config_data:
            raise ValueError("CourseConfig requires 'semester' field")
        semester = config_data["semester"].lower()
        self.is_ws = "ws" in semester or "winter" in semester or "wis" in semester
        number_groups = [int(s) for s in re.findall(r'\d{2,4}', semester)]
        if not number_groups:
            raise ValueError("CourseConfig 'semester' field must contain a year")
        if number_groups[0] >= 2000:
            self.start_year = number_groups[0]
        else:
            self.start_year = 2000 + number_groups[0]

        # destination base
        if "destination_base" not in config_data:
            raise ValueError("CourseConfig requires 'destination_base' field")
        self.destination_base = Path(config_data["destination_base"]).expanduser()

        # update type
        if "update" in config_data:
            self.update_type = UpdateType(config_data["update"].lower())

        # config type
        if "config_type" in config_data:
            self.config_type = CourseConfigType(config_data["config_type"].lower())

        if self.config_type == CourseConfigType.CATEGORY_AUTO or self.config_type == CourseConfigType.FILE_AUTO:
            if "categories" in config_data or "files" in config_data:
                raise ValueError(f"Auto config type '{self.config_type.value}' should not have 'categories' or 'files' defined")
            self.categories = []
            self.files = []
            return
        elif self.config_type == CourseConfigType.FILE_MANUAL:
            if "categories" in config_data:
                raise ValueError(f"file_manual config type should not have 'categories' defined")

        for cat_cfg in config_data.get("categories", []):
            self.categories.append(_CategoryConfig(cat_cfg))

        for file_cfg in config_data.get("files", []):
            self.files.append(_FileConfig(file_cfg))


class ConfigManager:
    defaults = _DefaultConfig()

    show_hidden_courses: bool = defaults.show_hidden_courses
    cache_dir: Path = defaults.cache_dir
    summary_dir: Path = defaults.summary_dir
    session_save: bool = defaults.session_save
    session_save_path: Path = defaults.session_save_path
    log_level: str = defaults.log_level
    courses_config: list[_CourseConfig] = []

    username: str = ""
    password: str = ""

    def __init__(self, config_data: dict):
        try:
            if "show_hidden_courses" in config_data:
                self.show_hidden_courses = config_data["show_hidden_courses"]
            if "cache_dir" in config_data:
                self.cache_dir = Path(config_data["cache_dir"]).expanduser()
            if "summary_dir" in config_data:
                self.summary_dir = Path(config_data["summary_dir"]).expanduser()
            else:
                self.summary_dir = self.cache_dir / "summaries"
            if "session" in config_data:
                session_cfg = config_data["session"]
                if "save" in session_cfg:
                    self.session_save = session_cfg["save"]
                if "save_path" in session_cfg:
                    self.session_save_path = Path(session_cfg["save_path"]).expanduser()
            if "log_level" in config_data:
                self.log_level = config_data["log_level"]
                if self.log_level not in ["DEBUG", "INFO", "WARNING", "ERROR"]:
                    raise ValueError(f"Invalid log_level: {self.log_level}, must be one of DEBUG, INFO, WARNING, ERROR")
            if "courses" in config_data:
                for course_cfg in config_data["courses"]:
                    self.courses_config.append(_CourseConfig(course_cfg))

        except Exception as e:
            raise ValueError(f"Error parsing configuration: {e}") from e

    def set_credentials(self, username: str, password: str):
        self.username = username
        self.password = password
