from .session import TUMMoodleSession, CourseInfo, ResourceCategory
from .config_mgr import ConfigManager
from .utils import parse_semester


class TUMMoodleDownloader():
    _session: TUMMoodleSession
    _config: ConfigManager

    def __init__(self, config: ConfigManager):
        self._session = TUMMoodleSession(
            config.username,
            config.password,
            headless=True,
            storage_state_path=None if not config.session_save or not config.session_save_path else config.session_save_path
        )
        self._config = config

    async def _proc_course(self, course: CourseInfo):
        # Check if the course matches any configured course
        found = False
        for course_config in self._config.courses_config:
            # No matcher (should not happen)
            if not course_config.title_matcher:
                continue
            # Title didn't match
            if not course_config.title_matcher.match(course.title):
                continue
            # Compare semester
            if course.is_ws != course_config.is_ws or course.start_year != course_config.start_year:
                continue
            found = True
            break
        if not found:
            return

        def filter_func(categories: list[ResourceCategory]):

    async def do_magic(self):
        async with self._session as sess:
            courses = await sess.get_courses(self._config.show_hidden_courses)
            for course in courses:
                await self._proc_course(course)
