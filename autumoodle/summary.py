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


class SummaryWriter:
    _file_path: Path
    _file: object
    _entries: list[SummaryEntry]

    @staticmethod
    def get_extname() -> str:
        return ".csv"

    @staticmethod
    def format_filename(prefix: str) -> str:
        return f"{prefix}{time.strftime("%Y%m%d_%H%M%S", time.localtime())}{SummaryWriter.get_extname()}"

    def __init__(self, file_path: Path) -> None:
        self._file_path = file_path
        self._file_path.parent.mkdir(parents=True, exist_ok=True)
        self._entries = []
        self._file = None

    def open(self) -> None:
        self._file = open(self._file_path, "w", encoding="utf-8")
        self._write_header()

    def write(self, content: str) -> None:
        self._file.write(content)  # type: ignore

    def close(self) -> None:
        self._file.close()  # type: ignore

    def _write_header(self) -> None:
        header = '"stored_path","course_name","category_name","entry_name","file_name","status","detail"\n'
        self.write(header)

    def add_entry(self, entry: SummaryEntry) -> None:
        line = f'"{entry.stored_path}","{entry.course_name}","{entry.category_name}","{entry.entry_name}","{entry.file_name}","{entry.status}","{entry.detail}"\n'
        self.write(line)
        self._entries.append(entry)

    def print_summary(self) -> str:
        total = len(self._entries)
        counts = {}
        for entry in self._entries:
            counts[entry.status] = counts.get(entry.status, 0) + 1
        return f"Total updated files: {total}. Details: " + ", ".join(f"{status}: {count}" for status, count in counts.items())


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
        for file in self._summary_dir.glob(f"{self._summary_prefix}*{SummaryWriter.get_extname()}"):
            try:
                days_old = (Path.cwd().stat().st_mtime - file.stat().st_mtime) / 86400
                if days_old > self._expire_days:
                    Logger.d("SummaryManager", f"Deleting old summary file: {file} (age: {days_old:.2f} days)")
                    file.unlink()
            except Exception:
                Logger.w("SummaryManager", f"Failed to delete old summary file: {file}")

    def __enter__(self) -> SummaryWriter:
        summary_file = self._summary_dir / SummaryWriter.format_filename(self._summary_prefix)
        Logger.d("SummaryManager", f"Creating summary file: {summary_file}")
        if self._writer:
            raise RuntimeError("SummaryManager is already in use")
        self._writer = SummaryWriter(summary_file)
        self._writer.open()
        return self._writer

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        Logger.d("SummaryManager", "Exiting SummaryManager context")
        if self._writer:
            Logger.i("SummaryWriter", self._writer.print_summary())
            self._writer.close()
            Logger.i("SummaryManager", f"Summary file saved: {self._writer._file_path}")
        self._writer = None
