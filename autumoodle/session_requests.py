from dataclasses import dataclass
from pathlib import Path
import httpx
import pickle
from bs4 import BeautifulSoup, Tag

from .log import Logger
from . import utils
from . import request_helper
from .auth import auth
from . import session_intf as smgr

# autopep8: off
def MOODLE_URL(): return "https://www.moodle.tum.de"
# the param "courseid" should be appended along with the actual course id from COURSES_PAGE_URL
def DOWNLOAD_CENTER_URL(course_id): return f"{MOODLE_URL()}/local/downloadcenter/index.php?courseid={course_id}"
# coc-manage=1 enables "Ausgeblendete Kurse verwalten" that shows all courses
def COURSES_PAGE_URL(show_hidden): return f"{MOODLE_URL()}/my/{'?coc-manage=1' if show_hidden else ''}"
# autopep8: on


@dataclass(frozen=True, slots=True)
class ResourceInfo(smgr.ResourceInfo):
    id: str
    filename: str
    _input_name: str


@dataclass(slots=True)
class ResourceCategory(smgr.ResourceCategory):
    title: str
    resources: list[smgr.ResourceInfo]
    _input_name: str


@dataclass(frozen=True, slots=True)
class CourseInfo(smgr.CourseInfo):
    id: str
    title: str
    metainfo: str
    is_ws: bool
    start_year: int


class TUMMoodleSession(smgr.TUMMoodleSession):
    _username: str
    _password: str
    _storage_state_path: Path | None

    _client: httpx.AsyncClient

    def __init__(self, username: str, password: str, storage_state_path: Path | None = None, retries: int = 2, timeout: int = 30):
        self._username = username
        self._password = password
        self._client = httpx.AsyncClient(
            follow_redirects=True,
            transport=httpx.AsyncHTTPTransport(retries=retries),
            headers=request_helper.GENERAL_HEADERS,
            timeout=timeout,
        )
        self._storage_state_path = storage_state_path

    async def __aenter__(self):
        Logger.d("TUMMoodleSession", "Loading session from storage...")
        self._load_session()
        await self._check_login()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        Logger.d("TUMMoodleSession", "Saving session to storage...")
        try:
            self._save_session()
        except Exception as e:
            Logger.e("TUMMoodleSession", f"Failed to save session: {e}")
        Logger.d("TUMMoodleSession", "Closing session...")
        await self._client.aclose()
        Logger.d("TUMMoodleSession", "Session closed.")

    def _save_session(self):
        if self._storage_state_path:
            self._storage_state_path.parent.mkdir(parents=True, exist_ok=True)
            # The cookie jar contains a lock, which is not pickleable.
            # We extract the cookies into a list, which is.
            cookies_list = list(self._client.cookies.jar)
            with open(self._storage_state_path, 'wb') as f:
                pickle.dump(cookies_list, f)
            Logger.d("TUMMoodleSession", f"Session saved to {self._storage_state_path}")

    def _load_session(self) -> bool:
        if not self._storage_state_path:
            Logger.w("TUMMoodleSession", "No storage_state_path provided, cannot load session.")
            return False
        if not self._storage_state_path.exists():
            Logger.w("TUMMoodleSession", f"Session file not found: {self._storage_state_path}")
            return False

        try:
            with open(self._storage_state_path, 'rb') as f:
                cookies_list = pickle.load(f)
            # Re-populate the new cookie jar with the loaded cookies.
            for cookie in cookies_list:
                self._client.cookies.jar.set_cookie(cookie)
            Logger.d("TUMMoodleSession", f"Session loaded from {self._storage_state_path}")
            return True
        except Exception as e:
            Logger.e("TUMMoodleSession", f"Failed to load session: {e}")
            return False

    async def _check_login(self):
        Logger.d("TUMMoodleSession", "Checking login status...")
        response = await self._client.get(COURSES_PAGE_URL(False), follow_redirects=False)
        if response.status_code == 200:
            Logger.d("TUMMoodleSession", "Already logged in.")
            return
        Logger.d("TUMMoodleSession", "Not logged in, performing login...")
        await self._login()

    async def _login(self):
        await auth(self._client, self._username, self._password)
        try:
            self._save_session()
        except Exception as e:
            Logger.e("TUMMoodleSession", f"Failed to save session after login: {e}")

    async def get_courses(self, show_hidden: bool) -> list[smgr.CourseInfo]:
        try:
            Logger.d("TUMMoodleSession", "Retrieving courses from Mein Startseite...")
            response = await self._client.get(COURSES_PAGE_URL(show_hidden))
            if response.status_code != 200:
                raise RuntimeError(f"Failed to retrieve courses page, status code: {response.status_code}")
            soup = BeautifulSoup(response.text, 'html.parser')
            links = soup.select('div.coursebox h3 a')
            courses = []
            for link in links:
                title = link.get('title')
                if not isinstance(title, str):
                    Logger.d("TUMMoodleSession", f"Skipping course with missing title.")
                    continue
                href = link.get('href')
                if not isinstance(href, str) or href.find("id=") == -1:
                    Logger.d("TUMMoodleSession", f"Skipping invalid course link: {href}")
                    continue
                id = href.split("id=")[-1].split("&")[0]  # get the numeric id
                metainfo_tag = link.find('span', class_='coc-metainfo')
                metainfo_text = metainfo_tag.get_text(strip=True) if metainfo_tag else ""
                # Parse semester info more efficiently by avoiding redundant string operations
                if metainfo_text:
                    semester_part = metainfo_text.split(" | ", 1)[0]
                    if semester_part.startswith("("):
                        semester_part = semester_part[1:]
                    is_ws, start_year = utils.parse_semester(semester_part)
                else:
                    is_ws, start_year = False, 0
                course = CourseInfo(
                    id=id,
                    title=title.strip(),
                    metainfo=metainfo_text,
                    is_ws=is_ws,
                    start_year=start_year
                )
                Logger.d("TUMMoodleSession", f"Found course: {course}")
                courses.append(course)
            Logger.d("TUMMoodleSession", f"Total courses retrieved: {len(courses)}.")
            return courses
        except Exception as e:
            Logger.e("TUMMoodleSession", f"Failed to retrieve courses: {e}")
            return []

    def _parse_entry(self, entry: Tag) -> ResourceInfo | None:
        entry_input = entry.select_one('input')
        if not entry_input:
            return None
        entry_input_name = entry_input.get('name')
        if not isinstance(entry_input_name, str):
            return None
        entry_id = entry_input_name.split("_")[-1]
        entry_label = entry.select_one('span.itemtitle')
        if not entry_label:
            return None
        entry_label_span = entry_label.select_one('span')
        if not entry_label_span:
            return None
        entry_name = entry_label_span.get_text(strip=True)
        if not entry_name:
            return None
        return ResourceInfo(
            id=entry_id,
            filename=entry_name,
            _input_name=entry_input_name
        )

    def _parse_category(self, card: Tag) -> ResourceCategory | None:
        title_tags = card.select('span.sectiontitle')
        if not title_tags:
            Logger.w("TUMMoodleSession", "No title tag found in resource card.")
            return None
        title = title_tags[0].get_text(strip=True)
        Logger.d("TUMMoodleSession", f"Processing card '{title}'...")

        entries = []
        items = card.select('div.form-check')
        if len(items) <= 1:
            Logger.w("TUMMoodleSession", f"No resources found in card '{title}'.")
            return None
        category_input = items[0].select_one('input')
        if not category_input:
            Logger.w("TUMMoodleSession", f"No category input found in card '{title}'.")
            return None
        category_input_name = category_input.get('name')
        if not isinstance(category_input_name, str):
            Logger.w("TUMMoodleSession", f"Invalid category input name in card '{title}'.")
            return None
        for item in items[1:]:  # skip the first one (select all)
            entry = self._parse_entry(item)
            if entry:
                Logger.d("TUMMoodleSession", f"Found resource: {entry.filename} (ID: {entry.id})")
                entries.append(entry)

        if not entries:
            Logger.w("TUMMoodleSession", f"No valid resources parsed in card '{title}'.")
            return None

        return ResourceCategory(
            title=title,
            resources=entries,
            _input_name=category_input_name
        )

    async def _perform_download(self, categories: list[ResourceCategory], page: BeautifulSoup, save_path: Path) -> Path | None:
        form = page.find('form')
        if not form:  # should not happen
            raise RuntimeError("No form found on download center page")

        action = form.get('action')
        if not action:  # should not happen
            raise RuntimeError("No action found on download form")
        action = str(action)

        inputs = form.select('input')
        payload = {
            "courseid": "",
            "sesskey": ""
        }
        for input_tag in inputs:
            name = input_tag.get('name')
            if not isinstance(name, str):
                continue
            if name in payload:
                value = input_tag.get('value', '')
                if not isinstance(value, str):
                    value = ''
                payload[name] = value
        payload.update({
            "_qf__local_downloadcenter_download_form": "1",
            "mform_isexpanded_id_downloadoptions": "1",
            "submitbutton": "ZIP-Archiv erstellen"
        })

        have_entries = False
        for category in categories:
            if not category.resources:
                continue
            have_entries = True
            # select the category
            payload[category._input_name] = '1'
            for entry in category.resources:
                # select the entry
                payload[entry._input_name] = '1'  # type: ignore

        if not have_entries:
            Logger.w("TUMMoodleSession", "No entries selected for download.")
            return None

        response = self._client.stream('POST', action, data=payload, headers={
            **request_helper.GENERAL_HEADERS,
            **request_helper.ADDITIONAL_HEADERS
        })
        async with response as download_response:
            if download_response.status_code != 200:
                raise RuntimeError(f"Failed to download resources, status code: {download_response.status_code}")
            if not download_response.headers.get('Content-Type', '') == 'application/x-zip':
                raise RuntimeError(
                    f"Downloaded content is not a zip archive: {download_response.headers.get('Content-Type', '')}")
            with open(save_path, 'wb') as f:
                async for chunk in download_response.aiter_bytes():
                    f.write(chunk)
            return save_path

    async def download_archive(self, course_id: str, save_path: Path, filter=utils.passthrough):
        try:
            Logger.d("TUMMoodleSession", f"Downloading archives for course {course_id}...")
            download_url = DOWNLOAD_CENTER_URL(course_id)
            response = await self._client.get(download_url)
            if response.status_code != 200:
                raise RuntimeError(f"Failed to retrieve download center page, status code: {response.status_code}")
            soup = BeautifulSoup(response.text, 'html.parser')

            download_cards = soup.select('div.card:has(span.sectiontitle)')
            Logger.d("TUMMoodleSession", f"Found {len(download_cards)} cards.")
            categories: list[ResourceCategory] = []
            for card in download_cards:
                category = self._parse_category(card)
                if category:
                    categories.append(category)
            Logger.d("TUMMoodleSession", f"Total categories parsed: {len(categories)}.")
            filtered_resources = filter(categories)
            Logger.d("TUMMoodleSession",
                     f"Total resources after filtering: {sum(len(cat.resources) for cat in filtered_resources)}.")
            downloaded_path = await self._perform_download(filtered_resources, soup, save_path)
            if downloaded_path:
                Logger.d("TUMMoodleSession", f"Downloaded archive will be saved to: {downloaded_path}")
                return
            else:
                Logger.w("TUMMoodleSession", f"No archive was downloaded for course {course_id}.")
        except Exception as e:
            Logger.e("TUMMoodleSession", f"Failed to download archive for course {course_id}: {e}")
            raise


if __name__ == "__main__":
    import asyncio

    async def main():
        async with TUMMoodleSession("abcdedg", "NeverGonnaGiveYouUp", storage_state_path=Path("session.pkl")) as session:
            courses = await session.get_courses(show_hidden=True)
            for course in courses:
                print(course)

            course_id = "112336"
            await session.download_archive(course_id, Path(f"temp.zip"))

    asyncio.run(main())
