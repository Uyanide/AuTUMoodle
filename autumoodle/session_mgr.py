from contextlib import asynccontextmanager

from .session_requests import TUMMoodleSession as SessionRequests
from .session_playwright import TUMMoodleSession as SessionPlaywright

from .config_mgr import Config


@asynccontextmanager
async def TUMMoodleSessionBuilder(config: Config):
    if config.session_type == "requests":
        async with SessionRequests(
            config.username,
            config.password,
            config.session_save_path if config.session_save else None
        ) as session:
            yield session
    elif config.session_type == "playwright":
        async with SessionPlaywright(
            config.username,
            config.password,
            config.playwright_headless,
            config.playwright_browser,
            config.session_save_path if config.session_save else None
        ) as session:
            yield session
    else:
        raise ValueError(f"Unknown session type: {config.session_type}")
