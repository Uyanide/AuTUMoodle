'''
Author: Uyanide pywang0608@foxmail.com
Date: 2025-10-29 22:08:19
LastEditTime: 2025-10-31 13:56:48
Description: Functions to extract files from zip archives based on configuration
'''

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import shutil
import os
from zipfile import ZipFile

from .config_mgr import UpdateType, FileConfig
from .utils import create_temp_dir, PatternMatcher


@dataclass(frozen=True, slots=True)
class EntryDownloadConfig:
    category_matcher: PatternMatcher | None
    entry_matcher: PatternMatcher | None
    ignore: bool
    directory: Path
    update_type: UpdateType


def _find_matching_config(category: str, entry: str, _file_download_configs: list[EntryDownloadConfig]) -> EntryDownloadConfig | None:
    for config in _file_download_configs:
        if config.category_matcher and not config.category_matcher.match(category):
            continue
        if config.entry_matcher and not config.entry_matcher.match(entry):
            continue
        return config
    return None


def _find_matching_file_config(file_path: Path, file_configs: list[FileConfig]) -> FileConfig | None:
    for config in file_configs:
        if config.name_matcher and config.name_matcher.match(file_path.name):
            return config
    return None


def _check_ignored(fullpath: Path, ignored_files: list[PatternMatcher]) -> bool:
    name = fullpath.name
    for matcher in ignored_files:
        if matcher.match(name):
            return True
    return False


def _copy_with_timestamp(src: Path, dest: Path, timestamp: float | None = None):
    shutil.copy2(src, dest)
    if timestamp is not None:
        os.utime(dest, (timestamp, timestamp))


def _find_latest_modification_time(target: Path):
    newest_time = 0
    if target.exists():
        newest_time = target.stat().st_mtime

    for file in target.parent.glob(f"{target.stem}_[0-9]*{target.suffix}"):
        file_time = file.stat().st_mtime
        if file_time > newest_time:
            newest_time = file_time
    return newest_time


def extract_files(zip_path: Path,
                  destination_base: Path,
                  file_download_configs: list[EntryDownloadConfig],
                  ignored_files: list[PatternMatcher],
                  file_configs: list[FileConfig]):
    temp_dir = create_temp_dir(prefix="autumoodle_zip_extract_")
    try:
        with ZipFile(zip_path, 'r') as zip_ref:
            for zip_info in zip_ref.infolist():
                normalized_name = zip_info.filename.replace("\\", "/").lstrip("/")
                # Get category and entry names
                splitted = normalized_name.split("/")
                if len(splitted) < 2:
                    continue
                category_name = splitted[0]
                entry_name = splitted[1]
                # Find matching config
                entry_config = _find_matching_config(category_name, entry_name, file_download_configs)
                if entry_config is None:
                    # Try without extension name
                    # But directories should not have extensions
                    if len(splitted) > 2:
                        continue
                    entry_name = Path(entry_name).stem
                    entry_config = _find_matching_config(category_name, entry_name, file_download_configs)

                if entry_config is None:
                    continue

                # Get configuration values
                destination_path = entry_config.directory / normalized_name.split("/", 1)[1]
                update_type = entry_config.update_type

                # Check the file is to be ignored
                if ignored_files and _check_ignored(destination_path, ignored_files):
                    continue

                # Check if any FileConfig matches
                file_config = _find_matching_file_config(destination_path, file_configs)
                if file_config:
                    if file_config.ignore:
                        continue
                    # Override destination path if specified
                    if file_config.directory is not None:
                        if file_config.directory.is_absolute():
                            destination_path = file_config.directory / destination_path.name
                        else:
                            destination_path = destination_base / file_config.directory / destination_path.name
                    # Override update type if specified
                    if file_config.update_type is not None:
                        update_type = file_config.update_type

                destination_path.parent.mkdir(parents=True, exist_ok=True)

                # Extract to temp location
                temp_path = Path(zip_ref.extract(zip_info, temp_dir))

                # Check modification time
                if destination_path.exists():
                    local_date = _find_latest_modification_time(destination_path)
                else:
                    local_date = 0
                zip_mtime = datetime(*zip_info.date_time).timestamp()
                # Skip extraction if local file is up-to-date
                if local_date >= zip_mtime:
                    continue

                if update_type == UpdateType.OVERWRITE:
                    _copy_with_timestamp(temp_path, destination_path, zip_mtime)
                elif update_type == UpdateType.RENAME:
                    final_path = Path(destination_path)
                    counter = 1
                    while final_path.exists():
                        final_path = destination_path.with_name(
                            f"{destination_path.stem}_{counter}{destination_path.suffix}")
                        counter += 1
                    _copy_with_timestamp(temp_path, final_path, zip_mtime)
                elif update_type == UpdateType.SKIP:
                    if destination_path.exists():
                        continue
                    _copy_with_timestamp(temp_path, destination_path, zip_mtime)
                else:
                    raise ValueError(f"Unknown update type: {update_type}")
    finally:
        shutil.rmtree(temp_dir)
