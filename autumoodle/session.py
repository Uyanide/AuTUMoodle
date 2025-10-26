import asyncio
from playwright.async_api import async_playwright, Playwright, Browser, Page, BrowserContext, Locator, Download
from os import environ
from dataclasses import dataclass
from pathlib import Path

from .log import Logger
from . import utils

# There are 3 kinds of login pages:
# - The actual login page with input fields for username & password
TUM_LOGIN_URL = "https://login.tum.de"  # with subpath like /idp/profile/SAML2/Redirect/SSO and a param like execution=e1s1
# - Main page (before login) with 3 buttons (actually <a/> tags) (With TUM ID, With LMU ID, Guest (without ID))
#   Clicking on "With TUM ID" redirects to ${TUM_LOGIN_URL}/...
MOODLE_URL = "https://www.moodle.tum.de"
# - "Log in to TUM-Moodle" page with 3 links (TUM LOGIN, LMU LOGIN, DFN-AAI LOGIN)
#   Clicking on "TUM LOGIN" redirects to ${TUM_LOGIN_URL}/...
MOODLE_LOGIN_URL = f"{MOODLE_URL}/login/index.php"

# the param "courseid" should be appended along with the actual course id from COURSES_PAGE_URL
DOWNLOAD_CENTER_URL = f"{MOODLE_URL}/local/downloadcenter/index.php"

# coc-manage=1 enables "Ausgeblendete Kurse verwalten" that shows all courses
COURSES_PAGE_URL = f"{MOODLE_URL}/my/?coc-manage="

TIMEOUT = 30  # in seconds


# Describes a downloadable resource in the download center
@dataclass
class ResourceInfo:
    id: str  # numeric
    filename: str  # filename without "Dateien mit ursprünglichem Dateinamen herunterladen"

    # for internal use
    _input: Locator  # checkbox
    _div: Locator  # the "form-check" div


# Describes a category of downloadable resources
@dataclass
class ResourceCategory:
    title: str  # e.g. "Übungen"
    resources: list[ResourceInfo]


# Describes a class/course in Moodle
@dataclass
class CourseInfo:
    id: str  # numeric
    # One entry on www.moodle.tum.de/my should be like:
    #   $title
    #   ($semester | $school)
    title: str  # e.g. Analysis für Informatik [MA0902]
    # school: str  # e.g. Computation, Information and Technology
    metainfo: str  # Containing semester and school info
    is_ws: bool = False  # is winter semester
    start_year: int = 0  # start year of the semester


class TUMMoodleSession:
    _username: str
    _password: str
    _headless: bool
    _storage_state_path: Path | None

    # Playwright objects
    _async_playwright: Playwright
    _browser: Browser
    _context: BrowserContext

    def __init__(self, username, password, headless=True, storage_state_path: Path | None = None):
        '''Initialize TUMMoodleSession with credentials without starting the browser.'''
        self._username = username
        self._password = password
        self._headless = headless
        self._storage_state_path = storage_state_path

    async def __aenter__(self, browser="firefox"):
        '''Start the Playwright browser and create a new page.'''
        Logger.d("TUMMoodleSession", "Launching the browser...")
        self._async_playwright = await async_playwright().start()
        self._browser = await self._async_playwright[browser].launch(headless=self._headless)

        if self._storage_state_path and self._storage_state_path.exists():
            Logger.d("TUMMoodleSession", f"Using saved session from {self._storage_state_path}")
            self._context = await self._browser.new_context(storage_state=str(self._storage_state_path))
        else:
            self._context = await self._browser.new_context()

        Logger.d("TUMMoodleSession", "Browser has been launched.")
        try:
            Logger.d("TUMMoodleSession", "Attempting the first login...")
            page = await self._create_page(COURSES_PAGE_URL)
            await page.close()
            Logger.d("TUMMoodleSession", "Initial login attempt finished.")
        except Exception as e:
            Logger.e("TUMMoodleSession", f"Failed to open Moodle main page: {e}")
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        Logger.d("TUMMoodleSession", "Saving session state...")
        await self._save_storage_state()
        Logger.d("TUMMoodleSession", "Closing the browser...")
        await self._context.close()
        await self._browser.close()
        await self._async_playwright.stop()
        Logger.d("TUMMoodleSession", "Browser has been closed.")

    async def _save_storage_state(self):
        '''Save current browser context storage (cookies/localStorage) to file.'''
        if not self._storage_state_path:
            return
        try:
            self._storage_state_path.parent.mkdir(parents=True, exist_ok=True)
            await self._context.storage_state(path=str(self._storage_state_path))
            Logger.d("TUMMoodleSession", f"Session state saved to {self._storage_state_path}")
        except Exception as e:
            Logger.w("TUMMoodleSession", f"Failed to save session state: {e}")

    async def _create_page(self, url: str) -> Page:
        '''Create a new page and navigate to the specified URL.'''
        page = await self._context.new_page()
        await self._goto(page, url)
        return page

    async def _goto(self, page: Page, url: str):
        '''Navigate to the specified URL and ensure login status.'''
        if page.url != url:
            await page.goto(url, timeout=TIMEOUT * 1000)
            await self._check_login(page)
            if not page.url.startswith(url):
                Logger.w("TUMMoodleSession", f"Redirected to unexpected URL: {page.url}")

    async def _check_login(self, page: Page) -> bool:
        '''Check if current page is one of the known login pages, and perform login if needed.'''
        Logger.d("TUMMoodleSession", f"Checking login status on page: {page.url}")
        if page.url.startswith(TUM_LOGIN_URL):
            Logger.d("TUMMoodleSession", "TUM login page detected, attempting login...")
            return await self._login(page)
        elif page.url.startswith(MOODLE_LOGIN_URL):
            try:
                Logger.d("TUMMoodleSession", "Moodle login page detected, attempting login...")
                await page.locator('a[title="TUM LOGIN"]').click()
                await page.wait_for_url(utils.check_prefix(TUM_LOGIN_URL), timeout=TIMEOUT * 1000)
                return await self._login(page)
            except Exception as e:
                Logger.e("TUMMoodleSession", f"Failed to login via Moodle: {e}")
                return False
        elif page.url.removesuffix("/") == MOODLE_URL:
            try:
                Logger.d("TUMMoodleSession", "Moodle main login page detected, attempting login...")
                await page.locator('a:has-text("With TUM ID")').click()
                await page.wait_for_url(utils.check_prefix(TUM_LOGIN_URL), timeout=TIMEOUT * 1000)
                return await self._login(page)
            except Exception as e:
                Logger.e("TUMMoodleSession", f"Failed to login via Moodle main page: {e}")
                return False
        Logger.d("TUMMoodleSession", "Not a recognized login page, assuming already logged in.")
        return True

    async def _login(self, page: Page) -> bool:
        '''Perform login on the TUM login page and wait until redirected back to Moodle.'''
        Logger.d("TUMMoodleSession", f"Attempting login on page: {page.url}")
        if not page.url.startswith(TUM_LOGIN_URL):
            Logger.w("TUMMoodleSession", "Not on TUM login page, login aborted.")
            return False
        try:
            Logger.d("TUMMoodleSession", "Filling in login credentials...")

            await page.locator('input[name="j_username"]').fill(self._username)
            await page.locator('input[name="j_password"]').fill(self._password)
            await page.locator('button[type="submit"]').click()
            Logger.d("TUMMoodleSession", "Submitted login form, waiting for redirect...")
            await page.wait_for_url(utils.check_prefix(MOODLE_URL), timeout=TIMEOUT * 1000)
            Logger.d("TUMMoodleSession", "Successfully logged in.")
            Logger.d("TUMMoodleSession", "Saving session state after login...")
            await self._save_storage_state()
            return True
        except Exception as e:
            Logger.e("TUMMoodleSession", f"Login failed: {e}")
            return False

    async def get_courses(self, show_hidden: bool) -> list[CourseInfo]:
        '''Retrieve the list of courses from the Moodle "Meine Startseite" page.'''
        home_page = None
        try:
            Logger.d("TUMMoodleSession", "Retrieving courses from Meine Startseite...")
            home_page = await self._create_page(f"{COURSES_PAGE_URL}{'1' if show_hidden else '0'}")
            links = home_page.locator('div.coursebox h3 a')
            courses = []
            count = await links.count()
            for i in range(count):
                link = links.nth(i)
                title = await link.get_attribute("title")
                if not title:
                    Logger.d("TUMMoodleSession", f"Skipping course with missing title.")
                    continue
                href = await link.get_attribute("href")
                if not href or href.find("id=") == -1:
                    Logger.d("TUMMoodleSession", f"Skipping invalid course link: {href}")
                    continue
                id = href.split("id=")[-1].split("&")[0]  # get the numeric id
                metainfo = link.locator('span.coc-metainfo')
                metainfo_text = (await metainfo.inner_text()).strip() if metainfo else ""
                is_ws, start_year = utils.parse_semester(metainfo_text.split(
                    " | ")[0].removeprefix("(")) if metainfo_text else (False, 0)
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
        finally:
            if home_page:
                await home_page.close()

    async def _parse_download_form_entry(self, entry) -> ResourceInfo | None:
        '''Parse a single download form entry (div.form-check) and return ResourceInfo.'''
        entry_input = entry.locator('input')
        if not entry_input:
            return None
        entry_id = await entry_input.get_attribute("name")
        if not entry_id:
            return None
        entry_id = entry_id.split("_")[-1]  # only keep the numeric ID part
        entry_filename = (await entry.locator('span.itemtitle').locator('span').inner_text()).strip()
        if not entry_filename:
            return None
        if await entry_input.is_checked():
            await entry_input.uncheck()
        return ResourceInfo(
            id=entry_id,
            filename=entry_filename,
            _input=entry_input,
            _div=entry
        )

    async def _parse_categorie(self, card) -> list[ResourceInfo]:
        '''Parse a download category card and return list of ResourceInfo.'''
        # Get the section title
        title = (await card.locator('span.sectiontitle').inner_text()).strip()
        Logger.d("TUMMoodleSession", f"Processing card '{title}'...")

        resource_items = []
        items = card.locator('div.form-check')
        count = await items.count()
        # The first div should be the section title
        if count <= 1:
            Logger.d("TUMMoodleSession", f"No resources found in card '{title}'.")
            return resource_items
        for j in range(1, count):
            item = items.nth(j)
            item_idx = j
            parsed_item = await self._parse_download_form_entry(item)
            if parsed_item:
                Logger.d("TUMMoodleSession", f"Found resource: {parsed_item.filename} (ID: {parsed_item.id})")
                resource_items.append(parsed_item)
            else:
                Logger.d("TUMMoodleSession", f"Failed to parse resource item at index {item_idx} in card '{title}'.")
        return resource_items

    async def _perform_download(self, categories: list[ResourceCategory], page: Page) -> Download | None:
        '''Perform the download of selected resources and save to the specified path.'''
        to_check = [item._input for category in categories for item in category.resources]
        if len(to_check) == 0:
            Logger.w("TUMMoodleSession", f"No resources selected for download after filtering.")
            return None
        Logger.d("TUMMoodleSession", f"Selecting {len(to_check)} resources for download...")
        for input_elem in to_check:
            await input_elem.check()
        await page.locator('input[id="id_filesrealnames"]').uncheck()
        await page.locator('input[id="id_addnumbering"]').uncheck()
        async with page.expect_download(timeout=TIMEOUT * 1000) as download_info:
            await page.locator('input[id="id_submitbutton"]').click()
            Logger.d("TUMMoodleSession", f"Download initiated, waiting for completion...")
            return await download_info.value

    async def download_archive(self, course_id: str, save_path: Path, filter=utils.passthrough):
        '''Download the archive for the specified course ID, applying the filter function to resources.'''
        page = None
        try:
            Logger.d("TUMMoodleSession", f"Downloading archives for course {course_id}...")
            download_url = f"{DOWNLOAD_CENTER_URL}?courseid={course_id}"
            page = await self._create_page(download_url)
            await self._check_login(page)

            # Click on "keine" first
            await page.locator('a[id="downloadcenter-none-included"]').click()
            # Find all download cards
            download_cards = page.locator('div.card', has=page.locator('span.sectiontitle'))
            count = await download_cards.count()
            Logger.d("TUMMoodleSession", f"Found {count} cards.")
            categories: list[ResourceCategory] = []
            for i in range(count):
                card = download_cards.nth(i)
                card_title = (await (card.locator('span.sectiontitle').inner_text())).strip()
                resource_items = await self._parse_categorie(card)
                if resource_items:
                    Logger.d("TUMMoodleSession", f"Adding {len(resource_items)} resources under '{card_title}'.")
                    categories.append(ResourceCategory(
                        title=card_title,
                        resources=resource_items
                    ))
                else:
                    Logger.d("TUMMoodleSession", f"Failed to parse resources in card '{card_title}'.")

            Logger.d("TUMMoodleSession", f"Total categories parsed: {len(categories)}.")
            filtered_resources = filter(categories)
            Logger.d("TUMMoodleSession",
                     f"Total resources after filtering: {sum(len(cat.resources) for cat in filtered_resources)}.")
            download = await self._perform_download(filtered_resources, page)
            if download:
                Logger.d("TUMMoodleSession", f"Downloaded archive will be saved to: {save_path}")
                return await download.save_as(str(save_path))
            else:
                Logger.w("TUMMoodleSession", f"No archive was downloaded for course {course_id}.")

        except Exception as e:
            Logger.e("TUMMoodleSession", f"Failed to download archive for course {course_id}: {e}")
            raise
        finally:
            if page:
                await page.close()


def _create_session(headless: bool = True) -> TUMMoodleSession:
    username = environ.get("TUM_USERNAME")
    password = environ.get("TUM_PASSWORD")
    return TUMMoodleSession(username, password, headless=headless, storage_state_path=Path("~/.cache/autumoodle/session_storage.json").expanduser())


async def _main():
    Logger.set_level("DEBUG")
    session = _create_session(True)
    async with session as sess:
        courses = await sess.get_courses(False)
        for course in courses:
            print(f"Course: {course.title} (ID: {course.id})")
            print(f"  Metainfo: {course.metainfo}")

            if "MA0902" in course.title:
                with utils.create_temp_file(suffix=".zip") as tmpfile:
                    archive_path = await sess.download_archive(course.id, tmpfile, filter=utils.passthrough)
                    print(f"  Archive downloaded to: {archive_path}")
        await asyncio.sleep(30)


if __name__ == "__main__":
    asyncio.run(_main())
