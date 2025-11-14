'''
Author: Uyanide pywang0608@foxmail.com
Date: 2025-11-03 13:03:19
LastEditTime: 2025-11-14 13:06:11
Description: Summary manager and Summary writer implementations
'''

from abc import ABC, abstractmethod
from pathlib import Path
import time
from dataclasses import dataclass

from .log import Logger


@dataclass(frozen=True, slots=True)
class SummaryEntry:
    stored_path: str
    course_name: str
    category_name: str
    entry_name: str
    file_name: str
    status: str
    detail: str


class SummaryWriter(ABC):
    @abstractmethod
    def __init__(self, dir: Path, prefix: str) -> None:
        pass

    @abstractmethod
    def get_extname(self) -> str:
        pass

    @abstractmethod
    def get_filepath(self) -> Path:
        pass

    @abstractmethod
    def open(self) -> None:
        pass

    @abstractmethod
    def close(self) -> None:
        pass

    @abstractmethod
    def add_entry(self, entry: SummaryEntry) -> None:
        pass

    @abstractmethod
    def format_summary(self) -> str:
        pass


class _SummaryWriterCSV(SummaryWriter):
    _file_path: Path
    _file: object
    _entries: list[SummaryEntry]

    def _format_filename(self, prefix: str) -> str:
        return f"{prefix}{time.strftime('%Y%m%d_%H%M%S', time.localtime())}{self.get_extname()}"

    def __init__(self, dir: Path, prefix: str) -> None:
        self._file_path = dir / self._format_filename(prefix)
        self._entries = []
        self._file = None

    def get_extname(self) -> str:
        return ".csv"

    def get_filepath(self) -> Path:
        return self._file_path

    def open(self) -> None:
        self._file_path.parent.mkdir(parents=True, exist_ok=True)
        self._file = open(self._file_path, "w", encoding="utf-8")
        self._write_header()

    def _write(self, content: str) -> None:
        self._file.write(content)  # type: ignore

    def close(self) -> None:
        self._file.close()  # type: ignore

    def _write_header(self) -> None:
        header = '"stored_path","course_name","category_name","entry_name","file_name","status","detail"\n'
        self._write(header)

    def add_entry(self, entry: SummaryEntry) -> None:
        line = f'"{entry.stored_path}","{entry.course_name}","{entry.category_name}","{entry.entry_name}","{entry.file_name}","{entry.status}","{entry.detail}"\n'
        self._write(line)
        self._entries.append(entry)

    def format_summary(self) -> str:
        total = len(self._entries)
        counts = {}
        for entry in self._entries:
            counts[entry.status] = counts.get(entry.status, 0) + 1
        ret = f"Total updated files: {total}."
        if total == 0:
            ret += " No files were updated.\n"
        else:
            ret += " Details: " + ", ".join(f"{status}: {count}" for status, count in counts.items())
            ret += "\nUpdated files:\n"
            for entry in self._entries:
                ret += f"- [{entry.status}] {entry.stored_path}\n"
        ret += f"Summary file has been saved to: {self._file_path}"
        return ret


class SummaryManager:
    _expire_days: int
    _summary_dir: Path
    _summary_prefix: str
    _writer: SummaryWriter | None

    def __init__(self, expire_days: int, summary_dir: Path, summary_prefix: str = "autumoodle_summary_") -> None:
        self._expire_days = expire_days
        self._summary_dir = summary_dir
        self._summary_prefix = summary_prefix
        self._writer = None
        self.clear_old_summaries()

    def clear_old_summaries(self) -> None:
        curr_time = time.time()
        for file in self._summary_dir.glob(f"{self._summary_prefix}*"):
            try:
                days_old = (curr_time - file.stat().st_mtime) / 86400
                if days_old > self._expire_days:
                    Logger.d("SummaryManager", f"Deleting old summary file: {file} (age: {days_old:.2f} days)")
                    file.unlink()
            except Exception:
                Logger.w("SummaryManager", f"Failed to delete old summary file: {file}")

    def __enter__(self) -> SummaryWriter:
        if self._writer:
            raise RuntimeError("SummaryManager is already in use")
        self._writer = _SummaryWriterCSV(self._summary_dir, self._summary_prefix)
        Logger.i("SummaryManager", f"Creating new summary file at: {self._writer.get_filepath()}")
        self._writer.open()
        return self._writer

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        Logger.d("SummaryManager", "Exiting SummaryManager context")
        if self._writer:
            print(self._writer.format_summary())
            self._writer.close()
        self._writer = None
