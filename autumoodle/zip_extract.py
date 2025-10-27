from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import shutil
from zipfile import ZipFile

from .config_mgr import UpdateType
from .utils import create_temp_dir, PatternMatcher


@dataclass
class FileDownloadConfig:
    category_matcher: PatternMatcher | None
    name_matcher: PatternMatcher | None
    ignore: bool
    directory: Path
    update_type: UpdateType


class ZipExtractor:
    _file_path: Path

    def __init__(self, file_path: Path):
        if not file_path.exists() or not file_path.is_file():
            raise FileNotFoundError(f"Zip file not found: {file_path}")
        self._file_path = file_path

    def _find_matching_config(self, category: str, name: str, _file_download_configs: list[FileDownloadConfig]) -> FileDownloadConfig | None:
        for config in _file_download_configs:
            if config.category_matcher and not config.category_matcher.match(category):
                continue
            if config.name_matcher and not config.name_matcher.match(name):
                continue
            return config
        return None

    def _copy_with_stat(self, src: Path, dest: Path):
        shutil.copy2(src, dest)
        try:
            shutil.copystat(src, dest)
        except OSError:
            pass

    def extract_files(self, file_download_configs: list[FileDownloadConfig]):
        with create_temp_dir(prefix="autumoodle_zip_extract_") as temp_dir:
            with ZipFile(self._file_path, 'r') as zip_ref:
                for zip_info in zip_ref.infolist():
                    normalized_name = zip_info.filename.replace("\\", "/").lstrip("/")
                    splitted = normalized_name.split("/")
                    if len(splitted) < 2:
                        continue
                    category_name = splitted[0]
                    entry_name = splitted[1]
                    file_config = self._find_matching_config(category_name, entry_name, file_download_configs)
                    if file_config is None:
                        # Try without extension name
                        # But directories should not have extensions
                        if len(splitted) > 2:
                            continue
                        entry_name = Path(entry_name).stem
                        file_config = self._find_matching_config(category_name, entry_name, file_download_configs)

                    if file_config is None:
                        continue

                    temp_path = Path(zip_ref.extract(zip_info, temp_dir))

                    destination_path = file_config.directory / entry_name  # correct extension
                    # Handle subdirectories
                    if len(splitted) > 2:
                        destination_path = destination_path / "/".join(splitted[2:])
                    destination_path.parent.mkdir(parents=True, exist_ok=True)

                    update_type = file_config.update_type
                    if destination_path.exists():
                        local_date = destination_path.stat().st_mtime
                    else:
                        local_date = 0
                    zip_mtime = datetime(*zip_info.date_time).timestamp()
                    # Skip extraction if local file is up-to-date
                    if local_date >= zip_mtime:
                        continue

                    if update_type == UpdateType.OVERWRITE:
                        self._copy_with_stat(temp_path, destination_path)
                    elif update_type == UpdateType.RENAME:
                        final_path = Path(destination_path)
                        counter = 1
                        while final_path.exists():
                            final_path = destination_path.with_name(
                                f"{destination_path.stem}_{counter}{destination_path.suffix}")
                            counter += 1
                        self._copy_with_stat(temp_path, final_path)
                    elif update_type == UpdateType.SKIP:
                        if destination_path.exists():
                            continue
                        self._copy_with_stat(temp_path, destination_path)
                    else:
                        raise ValueError(f"Unknown update type: {update_type}")
