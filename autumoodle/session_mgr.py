'''
Author: Uyanide pywang0608@foxmail.com
Date: 2025-10-30 12:40:53
LastEditTime: 2025-10-31 13:55:41
Description: Factory for Moodle session implementations
'''

from contextlib import asynccontextmanager

from .config_mgr import Config


@asynccontextmanager
async def TUMMoodleSessionBuilder(config: Config):
    if config.session_type == "requests":
        from .session_requests import TUMMoodleSession as SessionRequests
        async with SessionRequests(
            config.username,
            config.password,
            config.session_save_path if config.session_save else None
        ) as session:
            yield session
    elif config.session_type == "playwright":
        from .session_playwright import TUMMoodleSession as SessionPlaywright
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
