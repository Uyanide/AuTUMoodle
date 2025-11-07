'''
Author: Uyanide pywang0608@foxmail.com
Date: 2025-10-29 22:08:19
LastEditTime: 2025-11-06 20:44:01
Description: Main logic for downloading courses based on configuration
'''

from pathlib import Path
import asyncio


from .session_mgr import TUMMoodleSessionBuilder
from .session_intf import TUMMoodleSession, CourseInfo, CategoryInfo
from .config_mgr import Config, CourseConfig, CourseConfigType
from .utils import create_temp_file, PatternMatcher, sanitize_filename
from .log import Logger
from .zip_extract import EntryDownloadConfig, extract_files
from .summary import SummaryManager, SummaryWriter


class _CourseProcess():
    _destination_base: Path
    _session: TUMMoodleSession
    _course_config: CourseConfig
    _course: CourseInfo
    _entry_download_configs: list[EntryDownloadConfig]
    _ignored_files_list: list[PatternMatcher]
    _summary_writer: SummaryWriter | None

    def __init__(self,
                 session: TUMMoodleSession,
                 course_config: CourseConfig,
                 course: CourseInfo,
                 global_destination_base: Path,
                 ignored_files_list: list[PatternMatcher],
                 summary_writer: SummaryWriter | None = None):
        self._session = session
        self._course_config = course_config
        self._course = course
        self._entry_download_configs = []
        self._ignored_files_list = ignored_files_list.copy()
        self._summary_writer = summary_writer

        if course_config.destination_base:
            if course_config.destination_base.is_absolute():
                self._destination_base = course_config.destination_base
            else:
                self._destination_base = global_destination_base / course_config.destination_base
        else:
            self._destination_base = global_destination_base / sanitize_filename(self._course.title)

    ########
    # Functions to get the filter function for each config type and build the download config map

    def _get_filter_func_auto(self, course_config: CourseConfig, respect_categories: bool = True):

        def filter_func(resource: list[CategoryInfo]) -> list[CategoryInfo]:
            for category in resource:
                if respect_categories:
                    directory = self._destination_base / sanitize_filename(category.title)
                else:
                    directory = self._destination_base
                self._entry_download_configs.append(EntryDownloadConfig(
                    category_matcher=PatternMatcher(
                        category.title,
                        "literal"
                    ),
                    entry_matcher=None,  # Match whatever file in the category
                    ignore=False,
                    directory=directory,
                    update_type=course_config.update_type
                ))
            return resource

        return filter_func

    def _get_filter_func_category_auto(self, course_config: CourseConfig):
        return self._get_filter_func_auto(course_config, respect_categories=True)

    def _get_filter_func_entry_auto(self, course_config: CourseConfig):
        return self._get_filter_func_auto(course_config, respect_categories=False)

    def _get_filter_func_category_manual(self, course_config: CourseConfig):
        cat_configs = course_config.categories
        entry_configs = course_config.entries

        def filter_func(resource: list[CategoryInfo]) -> list[CategoryInfo]:
            new_cats = []
            for cat in resource:
                # Check if any category config matches
                matched_cat_config = None
                for cat_config in cat_configs:
                    if cat_config.title_matcher.match(cat.title):
                        matched_cat_config = cat_config
                        break
                # Ignore entire category if no match
                if not matched_cat_config:
                    continue
                # Default to category title if no destination is sepecified
                cat_dest = matched_cat_config.destination if matched_cat_config.destination else Path(
                    sanitize_filename(cat.title))
                if not cat_dest.is_absolute():
                    cat_dest = self._destination_base / cat_dest
                cat_update_type = matched_cat_config.update_type if matched_cat_config.update_type else course_config.update_type
                new_entries = []
                for entry in cat.entries:
                    # Check if any entry config matches
                    matched_entry_config = None
                    for entry_config in entry_configs:
                        if entry_config.title_matcher.match(entry.title):
                            matched_entry_config = entry_config
                            break
                    # Use fallback config if no match
                    if not matched_entry_config:
                        new_entries.append(entry)
                        continue
                    # Check if to ignore
                    if matched_entry_config.ignore:
                        self._entry_download_configs.append(EntryDownloadConfig(
                            category_matcher=matched_cat_config.title_matcher,
                            entry_matcher=matched_entry_config.title_matcher,
                            ignore=True,
                            directory=self._destination_base / cat_dest,
                            update_type=course_config.update_type
                        ))
                        continue
                    new_entries.append(entry)
                    # Determine destination
                    entry_dest = matched_entry_config.directory if matched_entry_config.directory else cat_dest
                    if not entry_dest.is_absolute():
                        directory = self._destination_base / sanitize_filename(entry_dest, allow_separators=True)
                    else:
                        directory = entry_dest
                    # Add download config
                    self._entry_download_configs.append(EntryDownloadConfig(
                        category_matcher=matched_cat_config.title_matcher,
                        entry_matcher=matched_entry_config.title_matcher,
                        ignore=False,
                        directory=directory,
                        update_type=matched_entry_config.update_type if matched_entry_config.update_type else cat_update_type
                    ))
                # Append fallback config for the entire category
                self._entry_download_configs.append(EntryDownloadConfig(
                    category_matcher=matched_cat_config.title_matcher,
                    entry_matcher=None,
                    ignore=False,
                    directory=self._destination_base / cat_dest,
                    update_type=course_config.update_type
                ))
                cat.entries = new_entries
                new_cats.append(cat)
            return new_cats
        return filter_func

    def _get_filter_func_entry_manual(self, course_config: CourseConfig):
        file_configs = course_config.entries

        def filter_func(resource: list[CategoryInfo]) -> list[CategoryInfo]:
            new_cats = []
            for category in resource:
                new_entries = []
                for file in category.entries:
                    # Check if any file config matches
                    matched_file_config = None
                    for file_config in file_configs:
                        if file_config.title_matcher.match(file.title):
                            matched_file_config = file_config
                            break
                    # Skip if no match
                    if not matched_file_config:
                        continue
                    # Check if to ignore
                    if matched_file_config.ignore:
                        continue
                    new_entries.append(file)
                if new_entries:
                    category.entries = new_entries
                    new_cats.append(category)
            return new_cats

        for file_config in file_configs:
            if file_config.ignore:
                self._entry_download_configs.append(EntryDownloadConfig(
                    category_matcher=None,
                    entry_matcher=file_config.title_matcher,
                    ignore=True,
                    directory=self._destination_base,
                    update_type=course_config.update_type
                ))
            # Determine destination
            file_dest = file_config.directory if file_config.directory else Path(".")
            if not file_dest.is_absolute():
                destination = self._destination_base / sanitize_filename(file_dest, allow_separators=True)
            else:
                destination = file_dest
            # Add download config
            self._entry_download_configs.append(EntryDownloadConfig(
                category_matcher=None,
                entry_matcher=file_config.title_matcher,
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
        elif self._course_config.config_type == CourseConfigType.ENTRY_AUTO:
            get_filter_func_func = self._get_filter_func_entry_auto
        elif self._course_config.config_type == CourseConfigType.CATEGORY_MANUAL:
            get_filter_func_func = self._get_filter_func_category_manual
        elif self._course_config.config_type == CourseConfigType.ENTRY_MANUAL:
            get_filter_func_func = self._get_filter_func_entry_manual

        if not get_filter_func_func:
            raise ValueError(f"Unsupported course config type: {self._course_config.config_type}")

        filter_func = get_filter_func_func(self._course_config)
        temp_zip_path = create_temp_file(".zip")
        try:
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
            extract_files(
                temp_zip_path,
                self._course.title,
                self._destination_base,
                self._entry_download_configs,
                self._ignored_files_list,
                self._course_config.files,
                self._summary_writer
            )
        finally:
            if temp_zip_path.exists():
                temp_zip_path.unlink()


class TUMMoodleDownloader():
    _session: TUMMoodleSession
    _config: Config
    _summary_writer: SummaryWriter | None
    _additional_matchers: list[PatternMatcher]

    def __init__(self, config: Config, additional_matchers: list[PatternMatcher] | None = None):
        self._config = config
        self._summary_writer = None
        self._additional_matchers = additional_matchers if additional_matchers else []

    def _check_additional_matchers(self, course_title: str) -> bool:
        # if not provided, always match
        if not self._additional_matchers:
            return True
        for matcher in self._additional_matchers:
            if matcher.match(course_title):
                return True
        return False

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

            if not self._check_additional_matchers(course.title):
                Logger.d("Downloader", f"Skipping course '{course.title}': does not match any of the additional matchers")
                return

            Logger.i("Downloader", f"Started processing course '{course.title}'")
            await _CourseProcess(
                self._session,
                course_config,
                course,
                self._config.destination_base,
                self._config.ignored_files,
                self._summary_writer,
            ).proc()
            Logger.i("Downloader", f"Finished processing course '{course.title}'")
        except Exception as e:
            Logger.e("Downloader", f"Error downloading from course '{course.title}': {e}")

    # Do magic ╰( ͡° ͜ʖ ͡° )つ──☆*:・ﾟ
    async def do_magic(self):
        async with TUMMoodleSessionBuilder(self._config) as self._session:  # type: ignore
            if self._config.summary_enabled:
                with SummaryManager(
                    self._config.summary_expire_days,
                    self._config.summary_dir
                ) as summary_writer:
                    self._summary_writer = summary_writer
                    courses = await self._session.get_courses(False)
                    Logger.i("Downloader", f"Found {len(courses)} courses in total")
                    await asyncio.gather(*[self._proc_course(course) for course in courses])
            else:
                self._summary_writer = None
                courses = await self._session.get_courses(False)
                Logger.i("Downloader", f"Found {len(courses)} courses in total")
                await asyncio.gather(*[self._proc_course(course) for course in courses])
