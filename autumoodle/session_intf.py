'''
Author: Uyanide pywang0608@foxmail.com
Date: 2025-10-29 17:26:36
LastEditTime: 2025-10-31 13:55:35
Description: Interfaces for Moodle session implementations and data classes
'''

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from .utils import passthrough


# describes a downloadable resource in the download center
@dataclass(frozen=True)
class EntryInfo(ABC):
    """Interface for a downloadable resource in the download center"""
    id: str
    title: str


# describes a category of downloadable resources
# can be edited by filter functions, so not frozen
@dataclass
class CategoryInfo(ABC):
    """Interface for a category of downloadable resources"""
    title: str
    entries: list[EntryInfo]


# describes a class/course in Moodle
@dataclass(frozen=True)
class CourseInfo(ABC):
    """Interface for a class/course in Moodle"""
    id: str
    title: str
    metainfo: str
    is_ws: bool
    start_year: int


class TUMMoodleSession(ABC):
    """Interface for a Moodle session"""

    @abstractmethod
    async def get_courses(self, show_hidden: bool) -> list[CourseInfo]:
        """Get the list of courses"""
        pass

    @abstractmethod
    async def download_archive(self, course_id: str, save_path: Path, filter=passthrough) -> None:
        """Download the archive of a course"""
        pass
