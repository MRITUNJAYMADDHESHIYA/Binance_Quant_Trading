import time
import logging
import coloredlogs


def add_logger_filehandler(logger: logging.Logger, log_file: str, level: int = logging.DEBUG, fmt: str = '%(asctime)s - %(name)s - %(levelname)s - %(message)s', datefmt: str = '%Y-%m-%d %H:%M:%S') -> bool:
    """
    Add a file handler to the logger (writes logs to a file).

    Args:
        logger: The logger instance.
        log_file: Path to the log file.
        level: Log level for the file handler.
        fmt: Log format string.
        datefmt: Date format string.

    Returns:
        bool: True if successful, False otherwise.
    """
    try:
        fh = logging.FileHandler(log_file)
        fh.setLevel(level)
        fh.setFormatter(logging.Formatter(fmt=fmt, datefmt=datefmt))
        logger.addHandler(fh)
    except Exception as e:
        logger.error(f"Failed to add file handler: {e}")
        return False
    return True


def get_logger(log_name: str, log_level: int = logging.INFO, log_file: str = None, file_level: int = logging.DEBUG, fmt: str = '%(asctime)s [%(levelname)s] %(name)s:%(lineno)d - %(message)s', datefmt: str = '%Y-%m-%d %H:%M:%S') -> logging.Logger:
    """
    Create and configure a logger with console + optional file output.
    Args:
        log_name: Name of the logger.
        log_level: Logging level for console.
        log_file: Optional log file path.
        file_level: Logging level for file handler.
        fmt: Log format string.
        datefmt: Date format string.

    Returns:
        logging.Logger: Configured logger instance.
    """
    logger = logging.getLogger(log_name)
    logger.setLevel(log_level)

    if log_file is not None:
        if not add_logger_filehandler(logger, log_file, level=file_level, fmt=fmt, datefmt=datefmt):
            logger.warning(f"Could not attach file handler: {log_file}")

    # Colored logs for console
    coloredlogs.install(level=log_level, logger=logger, fmt=fmt, datefmt=datefmt)

    return logger


#current local time zone
def get_local_timezone() -> str:
    return time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time()))
