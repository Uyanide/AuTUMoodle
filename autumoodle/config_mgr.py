'''
Author: Uyanide pywang0608@foxmail.com
Date: 2025-10-26 21:59:22
LastEditTime: 2025-10-31 13:34:33
Description: Data classes representing configurations from json config files
'''

from dataclasses import dataclass, field
from pathlib import Path
from enum import Enum

from .utils import PatternMatcher, parse_semester


# Action to take when file exists & needs to be updated
class UpdateType(Enum):
    RENAME = "rename"        # like $filename.ext -> $filename_1.ext
    OVERWRITE = "overwrite"  # overwrite existing files (replace)
    SKIP = "skip"            # skip if file exists


class CourseConfigType(Enum):
    CATEGORY_AUTO = "category_auto"      # automatically create subdirs according to category titles
    CATEGORY_MANUAL = "category_manual"  # use manually defined category & entry configs, only the included categories will be considered
    ENTRY_AUTO = "entry_auto"            # put all entries in the course base dir
    ENTRY_MANUAL = "entry_manual"        # use manually defined entry configs, only the included entries will be considered


# Using a function to return defaults for clarity and consistency
def get_default_config():
    return {
        "show_hidden_courses": False,
        "cache_dir": Path.home() / ".cache" / "autumoodle",
        "session_type": "requests",
        "session_save": False,
        "session_save_path": Path.home() / ".cache" / "autumoodle" / "session.dat",
        "destination_base": Path.home() / "Documents" / "AuTUMoodle",
        "log_level": "INFO",
        "update_type": UpdateType.RENAME,
        "course_config_type": CourseConfigType.CATEGORY_AUTO,
        "playwright_browser": "firefox",
        "playwright_headless": True,
        "summary_enabled": False,
        "summary_dir": Path.home() / ".cache" / "autumoodle" / "summaries",
        "summary_expire_days": 7,
    }


@dataclass(slots=True)
class EntryConfig:
    title_matcher: PatternMatcher = field(init=False)
    directory: Path | None = field(default=None)
    update_type: UpdateType | None = field(default=None)
    ignore: bool = field(default=False)

    @classmethod
    def from_dict(cls, config_data: dict):
        cm = cls()

        if "pattern" not in config_data or "match_type" not in config_data:
            raise ValueError("entry config requires 'pattern' and 'match_type' fields")
        cm.title_matcher = PatternMatcher(
            config_data["pattern"], config_data["match_type"]
        )

        if "ignore" in config_data:
            cm.ignore = config_data["ignore"]

        if "directory" in config_data:
            cm.directory = Path(config_data["directory"]).expanduser()

        if "update" in config_data:
            cm.update_type = UpdateType(config_data["update"].lower())

        return cm


@dataclass(slots=True)
class FileConfig:
    name_matcher: PatternMatcher = field(init=False)
    directory: Path | None = field(default=None)
    update_type: UpdateType | None = field(default=None)
    ignore: bool = field(default=False)

    @classmethod
    def from_dict(cls, config_data: dict):
        cm = cls()

        if "pattern" not in config_data or "match_type" not in config_data:
            raise ValueError("file config requires 'pattern' and 'match_type' fields")
        cm.name_matcher = PatternMatcher(
            config_data["pattern"], config_data["match_type"]
        )

        if "directory" in config_data:
            cm.directory = Path(config_data["directory"]).expanduser()

        if "ignore" in config_data:
            cm.ignore = config_data["ignore"]

        if "update" in config_data:
            cm.update_type = UpdateType(config_data["update"].lower())

        return cm


@dataclass(slots=True)
class CategoryConfig:
    title_matcher: PatternMatcher = field(init=False)
    destination: Path | None = field(default=None)
    update_type: UpdateType | None = field(default=None)

    @classmethod
    def from_dict(cls, config_data: dict):
        cm = cls()

        if "pattern" not in config_data or "match_type" not in config_data:
            raise ValueError("category config requires 'pattern' and 'match_type' fields")
        cm.title_matcher = PatternMatcher(
            config_data["pattern"], config_data["match_type"]
        )

        if "destination" in config_data:
            cm.destination = Path(config_data["destination"]).expanduser()

        if "update" in config_data:
            cm.update_type = UpdateType(config_data["update"].lower())

        return cm


@dataclass(slots=True)
class CourseConfig:
    title_matcher: PatternMatcher = field(init=False)
    is_ws: bool = field(init=False)
    start_year: int = field(init=False)
    destination_base: Path | None = field(default=None)
    categories: list[CategoryConfig] = field(default_factory=list)
    entries: list[EntryConfig] = field(default_factory=list)
    files: list[FileConfig] = field(default_factory=list)
    config_type: CourseConfigType = field(default_factory=lambda: get_default_config()["course_config_type"])
    update_type: UpdateType = field(default_factory=lambda: get_default_config()["update_type"])

    @classmethod
    def from_dict(cls, config_data: dict):
        cm = cls()
        # title matcher
        if "pattern" not in config_data or "match_type" not in config_data:
            raise ValueError("CourseConfig requires 'pattern' and 'match_type' fields")
        cm.title_matcher = PatternMatcher(
            config_data["pattern"], config_data["match_type"]
        )

        # semester
        if "semester" not in config_data:
            raise ValueError("CourseConfig requires 'semester' field")
        semester = config_data["semester"].lower()
        cm.is_ws, cm.start_year = parse_semester(semester)

        # destination base
        if "destination_base" in config_data:
            cm.destination_base = Path(config_data["destination_base"]).expanduser()

        # update type
        if "update" in config_data:
            cm.update_type = UpdateType(config_data["update"].lower())

        # config type
        if "config_type" in config_data:
            cm.config_type = CourseConfigType(config_data["config_type"].lower())

        if cm.config_type == CourseConfigType.CATEGORY_AUTO or cm.config_type == CourseConfigType.ENTRY_AUTO:
            if "categories" in config_data or "entries" in config_data:
                raise ValueError(f"Auto config type '{cm.config_type.value}' should not have 'categories' or 'entries' defined")
            # cm.categories and cm.entries are already initialized to []
            return cm
        elif cm.config_type == CourseConfigType.ENTRY_MANUAL:
            if "categories" in config_data:
                raise ValueError(f"entry_manual config type should not have 'categories' defined")

        config = config_data.get("config", {})
        rules = config.get("rules", {})
        for cat_cfg in rules.get("categories", []):
            cm.categories.append(CategoryConfig.from_dict(cat_cfg))

        for entry_cfg in rules.get("entries", []):
            cm.entries.append(EntryConfig.from_dict(entry_cfg))

        for file_cfg in rules.get("files", []):
            cm.files.append(FileConfig.from_dict(file_cfg))

        return cm


@dataclass(slots=True)
class Config:
    courses_config: list[CourseConfig] = field(default_factory=list)
    ignored_files: list[PatternMatcher] = field(default_factory=list)
    username: str = field(default="")
    password: str = field(default="")
    show_hidden_courses: bool = field(default_factory=lambda: get_default_config()["show_hidden_courses"])
    cache_dir: Path = field(default_factory=lambda: get_default_config()["cache_dir"])
    session_type: str = field(default_factory=lambda: get_default_config()["session_type"])
    session_save: bool = field(default_factory=lambda: get_default_config()["session_save"])
    session_save_path: Path = field(default_factory=lambda: get_default_config()["session_save_path"])
    destination_base: Path = field(default_factory=lambda: get_default_config()["destination_base"])
    log_level: str = field(default_factory=lambda: get_default_config()["log_level"])
    summary_enabled: bool = field(default_factory=lambda: get_default_config()["summary_enabled"])
    summary_dir: Path = field(default_factory=lambda: get_default_config()["summary_dir"])
    summary_expire_days: int = field(default_factory=lambda: get_default_config()["summary_expire_days"])
    playwright_browser: str = field(default_factory=lambda: get_default_config()["playwright_browser"])
    playwright_headless: bool = field(default_factory=lambda: get_default_config()["playwright_headless"])

    @classmethod
    def from_dict(cls, config_data: dict):
        cm = cls()
        try:
            cm.show_hidden_courses = config_data.get("show_hidden_courses", cm.show_hidden_courses)
            cm.cache_dir = Path(config_data.get("cache_dir", str(cm.cache_dir))).expanduser()

            if "session" in config_data:
                session_cfg = config_data["session"]
                cm.session_save = session_cfg.get("save", cm.session_save)
                cm.session_save_path = Path(session_cfg.get(
                    "save_path", str(cm.cache_dir / "session.dat"))).expanduser()

            if "log_level" in config_data:
                cm.log_level = config_data["log_level"]
                if cm.log_level not in ["DEBUG", "INFO", "WARNING", "ERROR"]:
                    raise ValueError(f"Invalid log_level: {cm.log_level}, must be one of DEBUG, INFO, WARNING, ERROR")

            # if "destination_base" in config_data:
            #     cm.destination_base: Path = Path(config_data["destination_base"]).expanduser()
            cm.destination_base = Path(config_data.get(
                "destination_base", str(cm.destination_base))).expanduser()

            if "summary" in config_data:
                summary_cfg = config_data["summary"]
                cm.summary_enabled = summary_cfg.get("enabled", cm.summary_enabled)
                cm.summary_dir = Path(summary_cfg.get("path", str(cm.summary_dir))).expanduser()
                cm.summary_expire_days = summary_cfg.get("expire_days", cm.summary_expire_days)

            cm.session_type = config_data.get("session_type", cm.session_type).lower()

            if "playwright" in config_data:
                pw_cfg = config_data["playwright"]
                cm.playwright_browser = pw_cfg.get("browser", cm.playwright_browser)
                cm.playwright_headless = pw_cfg.get("headless", cm.playwright_headless)

            if "courses" in config_data:
                for course_cfg in config_data["courses"]:
                    cm.courses_config.append(CourseConfig.from_dict(course_cfg))

            if "ignored_files" in config_data:
                for pattern_cfg in config_data["ignored_files"]:
                    if "pattern" not in pattern_cfg or "match_type" not in pattern_cfg:
                        raise ValueError("ignored_files entry requires 'pattern' and 'match_type' fields")
                    pm = PatternMatcher(
                        pattern_cfg["pattern"], pattern_cfg["match_type"]
                    )
                    cm.ignored_files.append(pm)

            return cm

        except Exception as e:
            raise ValueError(f"Error parsing configuration: {e}") from e

    def set_credentials(self, username: str, password: str):
        self.username = username
        self.password = password
