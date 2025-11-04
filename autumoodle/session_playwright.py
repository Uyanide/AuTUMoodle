'''
Author: Uyanide pywang0608@foxmail.com
Date: 2025-10-26 21:59:22
LastEditTime: 2025-11-04 23:34:40
Description: Playwright-based Moodle session implementation
'''

from typing import Callable
from playwright.async_api import async_playwright, Playwright, Browser, Page, BrowserContext, Locator, Download
from dataclasses import dataclass
from pathlib import Path

from .log import Logger
from . import utils
from . import session_intf as intf

# autopep8: off
# There are 3 kinds of login pages:
# - The actual login page with input fields for username & password
def TUM_LOGIN_URL(): return "https://login.tum.de"  # with subpath like /idp/profile/SAML2/Redirect/SSO and a param like execution=e1s1
# - Main page (before login) with 3 buttons (actually <a/> tags) (With TUM ID, With LMU ID, Guest (without ID))
#   Clicking on "With TUM ID" redirects to ${TUM_LOGIN_URL}/...
# MOODLE_URL = "https://www.moodle.tum.de"
def MOODLE_URL(): return "https://www.moodle.tum.de"
# - "Log in to TUM-Moodle" page with 3 links (TUM LOGIN, LMU LOGIN, DFN-AAI LOGIN)
#   Clicking on "TUM LOGIN" redirects to ${TUM_LOGIN_URL}/...
def MOODLE_LOGIN_URL(): return f"{MOODLE_URL()}/login/index.php"

# the param "courseid" should be appended along with the actual course id from COURSES_PAGE_URL
def DOWNLOAD_CENTER_URL(course_id): return f"{MOODLE_URL()}/local/downloadcenter/index.php?courseid={course_id}"

# coc-manage=1 enables "Ausgeblendete Kurse verwalten" that shows all courses
def COURSES_PAGE_URL(show_hidden): return f"{MOODLE_URL()}/my/?coc-manage={'1' if show_hidden else '0'}"
# autopep8: on


TIMEOUT = 30  # in seconds


@dataclass(frozen=True, slots=True)
class EntryInfo(intf.EntryInfo):
    id: str
    title: str
    # for internal use
    _input: Locator  # checkbox
    _div: Locator  # the "form-check" div


@dataclass(slots=True)
class CategoryInfo(intf.CategoryInfo):
    title: str
    entries: list[intf.EntryInfo]


@dataclass(frozen=True, slots=True)
class CourseInfo(intf.CourseInfo):
    id: str
    title: str
    metainfo: str
    is_ws: bool = False
    start_year: int = 0


class TUMMoodleSession(intf.TUMMoodleSession):
    _username: str
    _password: str
    _headless: bool
    _browser_name: str
    _storage_state_path: Path | None
    _show_hidden_courses: bool

    # Playwright objects
    _async_playwright: Playwright
    _browser: Browser
    _context: BrowserContext

    def __init__(self, username, password, headless=True, browser="firefox", storage_state_path: Path | None = None):
        '''Initialize TUMMoodleSession with credentials without starting the browser.'''
        self._username = username
        self._password = password
        self._headless = headless
        self._browser_name = browser
        self._storage_state_path = storage_state_path

    async def __aenter__(self):
        '''Start the Playwright browser and create a new page.'''
        Logger.d("TUMMoodleSession", "Launching the browser...")
        self._async_playwright = await async_playwright().start()
        self._browser = await self._async_playwright[self._browser_name].launch(headless=self._headless)

        if self._storage_state_path and self._storage_state_path.exists():
            Logger.d("TUMMoodleSession", f"Using saved session from {self._storage_state_path}")
            try:
                self._context = await self._browser.new_context(storage_state=str(self._storage_state_path))
            except Exception as e:
                Logger.w("TUMMoodleSession", f"Failed to load storage state: {e}, starting with a fresh context.")
                self._context = await self._browser.new_context()
        else:
            self._context = await self._browser.new_context()

        Logger.d("TUMMoodleSession", "Browser has been launched.")
        try:
            Logger.d("TUMMoodleSession", "Attempting the first login...")
            page = await self._create_page(COURSES_PAGE_URL(False))
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
        if page.url.startswith(TUM_LOGIN_URL()):
            Logger.d("TUMMoodleSession", "TUM login page detected, attempting login...")
            return await self._login(page)
        elif page.url.startswith(MOODLE_LOGIN_URL()):
            try:
                Logger.d("TUMMoodleSession", "Moodle login page detected, attempting login...")
                await page.locator('a[title="TUM LOGIN"]').click()
                await page.wait_for_url(utils.check_prefix(TUM_LOGIN_URL()), timeout=TIMEOUT * 1000)
                return await self._login(page)
            except Exception as e:
                Logger.e("TUMMoodleSession", f"Failed to login via Moodle: {e}")
                return False
        elif page.url.removesuffix("/") == MOODLE_URL:
            try:
                Logger.d("TUMMoodleSession", "Moodle main login page detected, attempting login...")
                await page.locator('a:has-text("With TUM ID")').click()
                await page.wait_for_url(utils.check_prefix(TUM_LOGIN_URL()), timeout=TIMEOUT * 1000)
                return await self._login(page)
            except Exception as e:
                Logger.e("TUMMoodleSession", f"Failed to login via Moodle main page: {e}")
                return False
        Logger.d("TUMMoodleSession", "Not a recognized login page, assuming already logged in.")
        return True

    async def _login(self, page: Page) -> bool:
        '''Perform login on the TUM login page and wait until redirected back to Moodle.'''
        Logger.d("TUMMoodleSession", f"Attempting login on page: {page.url}")
        if not page.url.startswith(TUM_LOGIN_URL()):
            Logger.d("TUMMoodleSession", "Not on TUM login page, login aborted.")
            return False
        try:
            Logger.d("TUMMoodleSession", "Filling in login credentials...")

            await page.locator('input[name="j_username"]').fill(self._username)
            await page.locator('input[name="j_password"]').fill(self._password)
            await page.locator('button[type="submit"]').click()
            Logger.d("TUMMoodleSession", "Submitted login form, waiting for redirect...")
            await page.wait_for_url(utils.check_prefix(MOODLE_URL()), timeout=TIMEOUT * 1000)
            Logger.d("TUMMoodleSession", "Successfully logged in.")
            Logger.d("TUMMoodleSession", "Saving session state after login...")
            await self._save_storage_state()
            return True
        except Exception as e:
            Logger.e("TUMMoodleSession", f"Login failed: {e}")
            return False

    async def get_courses(self, show_hidden: bool) -> list[intf.CourseInfo]:
        '''Retrieve the list of courses from the Moodle "Meine Startseite" page.'''
        home_page = None
        try:
            Logger.d("TUMMoodleSession", "Retrieving courses from Meine Startseite...")
            home_page = await self._create_page(COURSES_PAGE_URL(show_hidden))
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

    async def _parse_download_form_entry(self, entry) -> EntryInfo | None:
        '''Parse a single download form entry (div.form-check) and return ResourceInfo.'''
        entry_input = entry.locator('input')
        if not entry_input:
            return None
        entry_id = await entry_input.get_attribute("name")
        if not entry_id:
            return None
        entry_id = entry_id.split("_")[-1]  # only keep the numeric ID part
        entry_title = (await entry.locator('span.itemtitle').locator('span').inner_text()).strip()
        if not entry_title:
            return None
        if await entry_input.is_checked():
            await entry_input.uncheck()
        return EntryInfo(
            id=entry_id,
            title=entry_title,
            _input=entry_input,
            _div=entry
        )

    async def _parse_categorie(self, card) -> list[EntryInfo]:
        '''Parse a download category card and return list of ResourceInfo.'''
        # Get the section title
        title = (await card.locator('span.sectiontitle').inner_text()).strip()
        Logger.d("TUMMoodleSession", f"Processing card '{title}'...")

        entries = []
        items = card.locator('div.form-check')
        count = await items.count()
        # The first div should be the section title
        if count <= 1:
            Logger.d("TUMMoodleSession", f"No resources found in card '{title}'.")
            return entries
        for j in range(1, count):
            item = items.nth(j)
            item_idx = j
            entry = await self._parse_download_form_entry(item)
            if entry:
                Logger.d("TUMMoodleSession", f"Found resource: {entry.title} (ID: {entry.id})")
                entries.append(entry)
            else:
                Logger.d("TUMMoodleSession", f"Failed to parse resource item at index {item_idx} in card '{title}'.")
        return entries

    async def _perform_download(self, categories: list[CategoryInfo], page: Page) -> Download | None:
        '''Perform the download of selected resources and save to the specified path.'''
        to_check = [item._input for category in categories for item in category.entries]  # pyright: ignore[reportAttributeAccessIssue]
        if len(to_check) == 0:
            Logger.d("TUMMoodleSession", f"No resources selected for download after filtering.")
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

    async def download_archive(self, course_id: str, save_path: Path, filter: Callable[[list], list] = utils.passthrough) -> None:
        '''Download the archive for the specified course ID, applying the filter function to resources.'''
        page = None
        try:
            Logger.d("TUMMoodleSession", f"Downloading archives for course {course_id}...")
            download_url = DOWNLOAD_CENTER_URL(course_id)
            page = await self._create_page(download_url)
            await self._check_login(page)

            # Click on "keine" first
            await page.locator('a[id="downloadcenter-none-included"]').click()
            # Find all download cards
            download_cards = page.locator('div.card', has=page.locator('span.sectiontitle'))
            count = await download_cards.count()
            Logger.d("TUMMoodleSession", f"Found {count} cards.")
            categories: list[CategoryInfo] = []
            for i in range(count):
                card = download_cards.nth(i)
                card_title = (await (card.locator('span.sectiontitle').inner_text())).strip()
                entries = await self._parse_categorie(card)
                if entries:
                    Logger.d("TUMMoodleSession", f"Adding {len(entries)} resources under '{card_title}'.")
                    categories.append(CategoryInfo(
                        title=card_title,
                        entries=entries  # pyright: ignore[reportArgumentType]
                    ))
                else:
                    Logger.d("TUMMoodleSession", f"Failed to parse resources in card '{card_title}'.")

            Logger.d("TUMMoodleSession", f"Total categories parsed: {len(categories)}.")
            filtered_categories = filter(categories)
            Logger.d("TUMMoodleSession",
                     f"Total entries after filtering: {sum(len(cat.entries) for cat in filtered_categories)}.")
            download = await self._perform_download(filtered_categories, page)
            if download:
                Logger.d("TUMMoodleSession", f"Downloaded archive will be saved to: {save_path}")
                await download.save_as(str(save_path))
            else:
                Logger.w("TUMMoodleSession", f"No archive was downloaded for course {course_id}.")

        except Exception as e:
            Logger.e("TUMMoodleSession", f"Failed to download archive for course {course_id}: {e}")
            raise
        finally:
            if page:
                await page.close()
