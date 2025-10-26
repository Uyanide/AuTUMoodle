from dataclasses import dataclass
from pathlib import Path
import asyncio

from .session import TUMMoodleSession, CourseInfo, ResourceCategory
from .config_mgr import ConfigManager, CourseConfig, CourseConfigType, UpdateType
from .utils import passthrough, create_temp_file, PatternMatcher
from .log import Logger
from .zip_extract import FileDownloadConfig, ZipExtractor


class _CourseProcess():
    _session: TUMMoodleSession
    _course_config: CourseConfig
    _course: CourseInfo
    _file_download_configs: list[FileDownloadConfig]

    def __init__(self, session: TUMMoodleSession, course_config: CourseConfig, course: CourseInfo):
        self._session = session
        self._course_config = course_config
        self._course = course
        self._file_download_configs = []

    ########
    # Functions to get the filter function for each config type and build the download config map

    def _get_filter_func_auto(self, course_config: CourseConfig, respect_categories: bool = True):
        dest_base = course_config.destination_base

        def filter_func(resource: list[ResourceCategory]) -> list[ResourceCategory]:
            for category in resource:
                if respect_categories:
                    directory = dest_base / category.title
                else:
                    directory = dest_base
                self._file_download_configs.append(FileDownloadConfig(
                    category_matcher=PatternMatcher(
                        category.title,
                        "literal"
                    ),
                    name_matcher=None,  # Match whatever file in the category
                    ignore=False,
                    directory=directory,
                    update_type=course_config.update_type
                ))
            return resource

        return filter_func

    def _get_filter_func_category_auto(self, course_config: CourseConfig):
        return self._get_filter_func_auto(course_config, respect_categories=True)

    def _get_filter_func_file_auto(self, course_config: CourseConfig):
        return self._get_filter_func_auto(course_config, respect_categories=False)

    def _get_filter_func_category_manual(self, course_config: CourseConfig):
        dest_base = course_config.destination_base
        cat_configs = course_config.categories
        file_configs = course_config.files

        def filter_func(resource: list[ResourceCategory]) -> list[ResourceCategory]:
            for cat in resource:
                # Check if any category config matches
                matched_cat_config = None
                for cat_config in cat_configs:
                    if cat_config.title_matcher.match(cat.title):
                        matched_cat_config = cat_config
                        break
                # Ignore entire category if no match
                if not matched_cat_config:
                    resource.remove(cat)
                    continue
                # Default to category title if no destination is sepecified
                cat_dest = matched_cat_config.destination if matched_cat_config.destination else Path(
                    cat.title)
                if not cat_dest.is_absolute():
                    cat_dest = dest_base / cat_dest
                cat_update_type = matched_cat_config.update_type if matched_cat_config.update_type else course_config.update_type
                new_resources = []
                for file in cat.resources:
                    # Check if any file config matches
                    matched_file_config = None
                    for file_config in file_configs:
                        if file_config.name_matcher.match(file.filename):
                            matched_file_config = file_config
                            break
                    # Use fallback config if no match
                    if not matched_file_config:
                        new_resources.append(file)
                        continue
                    # Check if to ignore
                    if matched_file_config.ignore:
                        self._file_download_configs.append(FileDownloadConfig(
                            category_matcher=matched_cat_config.title_matcher,
                            name_matcher=matched_file_config.name_matcher,
                            ignore=True,
                            directory=dest_base / cat_dest,
                            update_type=course_config.update_type
                        ))
                        continue
                    new_resources.append(file)
                    # Determine destination
                    file_dest = matched_file_config.directory if matched_file_config.directory else cat_dest
                    if not file_dest.is_absolute():
                        directory = dest_base / file_dest
                    else:
                        directory = file_dest
                    # Add download config
                    self._file_download_configs.append(FileDownloadConfig(
                        category_matcher=matched_cat_config.title_matcher,
                        name_matcher=matched_file_config.name_matcher,
                        ignore=False,
                        directory=directory,
                        update_type=matched_file_config.update_type if matched_file_config.update_type else cat_update_type
                    ))
                cat.resources = new_resources
                # Append fallback config for the entire category
                self._file_download_configs.append(FileDownloadConfig(
                    category_matcher=matched_cat_config.title_matcher,
                    name_matcher=None,
                    ignore=False,
                    directory=dest_base / cat_dest,
                    update_type=course_config.update_type
                ))
            return resource
        return filter_func

    def _get_filter_func_file_manual(self, course_config: CourseConfig):
        dest_base = course_config.destination_base
        file_configs = course_config.files

        def filter_func(resource: list[ResourceCategory]) -> list[ResourceCategory]:
            for category in resource:
                new_resources = []
                for file in category.resources:
                    # Check if any file config matches
                    matched_file_config = None
                    for file_config in file_configs:
                        if file_config.name_matcher.match(file.filename):
                            matched_file_config = file_config
                            break
                    # Skip if no match
                    if not matched_file_config:
                        continue
                    # Check if to ignore
                    if matched_file_config.ignore:
                        continue
                    new_resources.append(file)
                category.resources = new_resources
            return resource

        for file_config in file_configs:
            if file_config.ignore:
                self._file_download_configs.append(FileDownloadConfig(
                    category_matcher=None,
                    name_matcher=file_config.name_matcher,
                    ignore=True,
                    directory=dest_base,
                    update_type=course_config.update_type
                ))
            # Determine destination
            file_dest = file_config.directory if file_config.directory else Path(".")
            if not file_dest.is_absolute():
                destination = dest_base / file_dest
            else:
                destination = file_dest
            # Add download config
            self._file_download_configs.append(FileDownloadConfig(
                category_matcher=None,
                name_matcher=file_config.name_matcher,
                ignore=False,
                directory=destination,
                update_type=file_config.update_type if file_config.update_type else course_config.update_type
            ))

        return filter_func

    ########
    # Main download logic

    async def proc(self):
        get_filter_func_func = None
        if self._course_config.config_type == CourseConfigType.CATEGORY_AUTO:
            get_filter_func_func = self._get_filter_func_category_auto
        elif self._course_config.config_type == CourseConfigType.FILE_AUTO:
            get_filter_func_func = self._get_filter_func_file_auto
        elif self._course_config.config_type == CourseConfigType.CATEGORY_MANUAL:
            get_filter_func_func = self._get_filter_func_category_manual
        elif self._course_config.config_type == CourseConfigType.FILE_MANUAL:
            get_filter_func_func = self._get_filter_func_file_manual

        if not get_filter_func_func:
            raise ValueError(f"Unsupported course config type: {self._course_config.config_type}")

        filter_func = get_filter_func_func(self._course_config)
        with create_temp_file(".zip") as temp_zip_path:
            Logger.d("Downloader", f"Downloading course '{self._course.title}' to temporary file '{temp_zip_path}'...")
            await self._session.download_archive(
                self._course.id,
                temp_zip_path,
                filter_func
            )
            if not temp_zip_path.exists():
                raise RuntimeError("Downloaded archive file does not exist")
            if temp_zip_path.stat().st_size == 0:
                raise RuntimeError("Downloaded archive is empty")

            Logger.d("Downloader", f"Extracting course '{self._course.title}' from '{temp_zip_path}'...")
            ZipExtractor(temp_zip_path).extract_files(self._file_download_configs)
            Logger.i("Downloader", f"Finished processing course '{self._course.title}'")


class TUMMoodleDownloader():
    _session_builder: TUMMoodleSession
    _session: TUMMoodleSession
    _config: ConfigManager

    def __init__(self, config: ConfigManager):
        if not config.username or not config.password:
            raise ValueError("Username and password must be provided in the config")
        self._session_builder = TUMMoodleSession(
            config.username,
            config.password,
            headless=True,
            storage_state_path=None if not config.session_save or not config.session_save_path else config.session_save_path
        )
        self._config = config

    async def _proc_course(self, course: CourseInfo):
        try:
            # Check if the course matches any configured course
            course_config = None
            for config in self._config.courses_config:
                # No matcher (should not happen)
                if not config.title_matcher:
                    continue
                # Title didn't match
                if not config.title_matcher.match(course.title):
                    continue
                # Compare semester
                if course.is_ws != config.is_ws or course.start_year != config.start_year:
                    continue
                course_config = config
                break
            if not course_config:
                Logger.d("Downloader", f"Skipping course '{course.title}': no matching config found")
                return

            await _CourseProcess(self._session, course_config, course=course).proc()
        except Exception as e:
            Logger.e("Downloader", f"Error downloading from course '{course.title}': {e}")

    # Do magic ╰( ͡° ͜ʖ ͡° )つ──☆*:・ﾟ
    async def do_magic(self):
        async with self._session_builder as self._session:
            courses = await self._session.get_courses(self._config.show_hidden_courses)
            await asyncio.gather(*[self._proc_course(course) for course in courses])
