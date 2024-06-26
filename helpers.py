import logging
from logging.handlers import TimedRotatingFileHandler
import os
import shutil
from pydantic import BaseModel
from typing import Optional
from pathlib import Path


"""
This module contains helper classes for logging, database operations, Discord-related operations, and miscellaneous utility functions.
"""


class LogHelper:
    """
    A helper class for logging operations.

    This class provides methods to check if a logger exists, create a logger with a file handler and a stream handler,
    and create file and stream handlers with specified log levels.

    Attributes:
        None

    Methods:
        logger_exists(logger_name): Checks if a logger with the given name exists.
        create_logger(logger_name, log_file, file_log_level, stream_log_level): Creates a logger with the given name and log file.
    """

    class HandlerBase(BaseModel):
        logger_name: str
        log_file: str

    class FileAndStreamHandler(HandlerBase):
        file_log_level: Optional[int] = logging.INFO
        stream_log_level: Optional[int] = logging.ERROR

    class TimedRotatingFileAndStreamHandler(FileAndStreamHandler):
        interval: Optional[str] = "midnight"
        backup_count: Optional[int] = 7

    def logger_exists(self, logger_name: str) -> bool:
        """
        Checks if a logger with the given name exists.

        Args:
            logger_name (str): The name of the logger to check.

        Returns:
            bool: True if a logger with the given name exists, False otherwise.
        """
        return logger_name in logging.Logger.manager.loggerDict

    def create_logger(
        self, log: FileAndStreamHandler | TimedRotatingFileAndStreamHandler
    ) -> logging.Logger:
        """
        Creates a logger with the given name and log file.

        Helper function to create, configure, and return a logger with the given name and log file.
        The logger will have a file handler and a stream handler attached to it.
        If the logger already exists, it will be returned without any changes.

        Args:
            log (FileAndStreamHandler | TimedRotatingFileAndStreamHandler): The log object containing the logger name and log file.

        Returns:
            logging.Logger: The created logger.
        """
        if not Path(log.log_file).parent.exists():
            self.create_log_dir(str(Path(log.log_file).parent))

        if self.logger_exists(log.logger_name):
            return logging.getLogger(log.logger_name)

        logger = logging.getLogger(log.logger_name)
        logger.setLevel(logging.DEBUG)

        stream_handler = self._create_stream_handler(log.stream_log_level)
        logger.addHandler(stream_handler)

        if isinstance(log, self.FileAndStreamHandler):
            file_handler = self._create_file_handler(log.log_file, log.file_log_level)
            logger.addHandler(file_handler)
        elif isinstance(log, self.TimedRotatingFileAndStreamHandler):
            timed_rotating_file_handler = self._create_timed_rotating_file_handler(
                log.log_file,
                log.file_log_level,
                log.interval,
                log.backup_count,
            )
            logger.addHandler(timed_rotating_file_handler)

        return logger

    def _create_file_handler(self, log_file: str, level: int) -> logging.FileHandler:
        """
        Creates a logging FileHandler with the specified log file and level.

        Args:
            log_file (str): The path and name of the log file to create.

        Returns:
            logging.FileHandler: The file handler object.

        """
        handler = logging.FileHandler(
            filename=log_file,
            encoding="utf-8",
            mode="a",
        )
        date_format = "%Y-%m-%d %H:%M:%S"
        formatter = logging.Formatter(
            "[{asctime}] [{levelname:<8}] {name}: {message}",
            datefmt=date_format,
            style="{",
        )
        handler.setFormatter(formatter)
        handler.setLevel(level)
        return handler

    def _create_stream_handler(self, level: int) -> logging.StreamHandler:
        """
        Creates a logging StreamHandler with the specified log level.

        Returns:
            logging.StreamHandler: The created StreamHandler object.

        """
        handler = logging.StreamHandler()
        date_format = "%Y-%m-%d %H:%M:%S"
        formatter = logging.Formatter(
            "[{asctime}] [{levelname:<8}] {name}: {message}",
            datefmt=date_format,
            style="{",
        )
        handler.setFormatter(formatter)
        handler.setLevel(level)
        return handler

    def _create_timed_rotating_file_handler(
        self, log_file: str, level: int, interval: str, backup_count: int
    ) -> TimedRotatingFileHandler:
        """
        Creates a logging TimedRotatingFileHandler with the specified log file, level, interval, and backup count.

        Args:
            log_file (str): The path and name of the log file to create.
            level (int): The log level for the file handler.
            interval (str): The interval at which log files should be rotated (e.g., 'midnight', 'daily', 'weekly', 'monthly').
            backup_count (int): The number of backup log files to keep.

        Returns:
            logging.handlers.TimedRotatingFileHandler: The created TimedRotatingFileHandler object.
        """
        handler = TimedRotatingFileHandler(
            filename=log_file,
            when=interval,
            backupCount=backup_count,
            encoding="utf-8",
        )
        date_format = "%Y-%m-%d %H:%M:%S"
        formatter = logging.Formatter(
            "[{asctime}] [{levelname:<8}] {name}: {message}",
            datefmt=date_format,
            style="{",
        )
        handler.setFormatter(formatter)
        handler.setLevel(level)
        return handler

    def create_log_dir(self, log_dir: str):
        """
        Creates a log directory if it does not exist.

        Args:
            log_dir (str): The path to the log directory.

        """
        os.makedirs(log_dir, exist_ok=True)


class MiscHelper:
    """
    A helper class that provides miscellaneous utility functions.

    attributes:
        None

    methods:
        is_installed(executable): Checks if the specified executable is installed on the system.
        remaining_time(seconds): Converts the given number of seconds into a formatted string representing the remaining time.
    """

    def is_installed(self, executable: str) -> bool:
        """
        Checks if the specified executable is installed on the system.

        Args:
            executable (str): The name of the executable to check.

        Returns:
            bool: True if the executable is installed, False otherwise.
        """
        return shutil.which(executable) is not None

    def remaining_time(self, seconds: int) -> str:
        """
        Converts the given number of seconds into a formatted string representing the remaining time.

        Args:
            seconds (int): The number of seconds.

        Returns:
            str: A formatted string representing the remaining time in the format "MM:SS".
        """
        minutes, seconds = divmod(seconds, 60)
        return f"{int(minutes):02d}:{int(seconds):02d}"

    def get_git_commit_count(self) -> int:
        """
        Gets the number of commits in the git repository.

        Returns:
            int: The number of commits in the git repository.
        """
        return int(os.popen("git rev-list --count HEAD").read().strip())
