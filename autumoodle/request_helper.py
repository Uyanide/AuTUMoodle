'''
Author: Uyanide pywang0608@foxmail.com
Date: 2025-10-29 09:57:27
LastEditTime: 2025-11-06 23:30:58
Description: Helpers for "requests" session implementation
'''

from bs4 import BeautifulSoup
from urllib.parse import urlencode, urlparse, urljoin

GENERAL_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7"
}

FORM_HEADERS = {
    "Content-Type": "application/x-www-form-urlencoded",
}


def join_relative_url(url: str, relative: str) -> str:
    # Case already absolute URL
    if relative.startswith("http://") or relative.startswith("https://"):
        return relative
    # Join with base URL
    parsed_url = urlparse(url)
    base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
    return urljoin(base_url, relative)


class FormParser:
    html_content: str
    action_url: str
    inputs: list[tuple[str, str]]  # keys can be duplicated

    def __init__(self, html_content: str):
        self.html_content = html_content
        soup = BeautifulSoup(self.html_content, 'html.parser')
        form = soup.find('form')
        if not form:
            raise ValueError("No form found in the HTML content")

        action_url = form.get('action')
        if not action_url:
            raise ValueError("No action URL found in the form")
        self.action_url = str(action_url)

        self.inputs = []
        for input_tag in form.find_all('input'):
            name = input_tag.get('name')
            value = input_tag.get('value', '')
            if name is None:
                continue
            if value is None:
                value = ''
            self.inputs.append((str(name), str(value)))

    def update_inputs(self, updates: dict[str, str]):
        for i, (name, value) in enumerate(self.inputs):
            if name in updates:
                self.inputs[i] = (name, updates[name])
        for name, value in updates.items():
            self.inputs.append((name, value))

    def remove_inputs(self, keys: set[str]):
        self.inputs = [(name, value) for name, value in self.inputs if name not in keys]

    def do_have_input(self, name: str) -> bool:
        return any(n == name for n, v in self.inputs)

    def ensure_have_inputs(self, names: set[str]) -> None:
        missing = names - {n for n, v in self.inputs}
        if missing:
            raise ValueError(f"Missing inputs: {', '.join(missing)}")

    def encode_inputs(self) -> str:
        return urlencode(self.inputs)
