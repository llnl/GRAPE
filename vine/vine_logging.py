from functools import wraps
import inspect
import logging
import logging.handlers
import StringIO
import os
import sys


def log_wrapper(func, *args, **kwargs):
    """
    Annotate a function to log entering, exiting, and returned values.

    NOTE: Logs to root logger only if effective level is 'logging.DEBUG'.
    Indepedent of GrapeLogger if root logger has no custom logging handlers
    registered. If GrapeLogger has registered logging handlers to the root
    logger, then messages will propagate accordingly.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        func_info = func.__module__ + "." + func.__name__ + " IN " + \
                    func.__code__.co_filename + " LINE: " + \
                    str(func.__code__.co_firstlineno)
        logging.debug("STARTING " + func_info)
        result = func(*args, **kwargs)
        logging.debug(func_info + " RETURNED: '" + repr(result) + "'")
        logging.debug("FINISHED " + func_info + "\n")
        return result
    return wrapper


class GrapeLogger(object):
    """
    Logging utility that logs messages to file, stdout, stderr, devnull, etc.

    GrapeLogger provides a controlled layer between messaging and the OS.
    This separation can simplify testing output and managing verbosity levels.
    """

    REAL_STDOUT = sys.stdout
    STUB_STDOUT = StringIO.StringIO()


    def __init__(self):
        self.manager = logging.Manager(logging.root)
        self._silence_root_logger()

    def _silence_root_logger(self):
        """
        Redirects root logger output to /dev/null or the Windows equivalent.
        
        Starting point before registering shared logging handlers to the root
        logger and other specialized loggers. These shared handlers propagate
        messages for controlled printing and file logging.
        """
        root = self.manager.root
        for handler in root.handlers:
            root.removeHandler(handler)
        # Accepts everything, propagates messages through handlers, emits nothing.
        logging.basicConfig(filename=os.devnull, level=logging.DEBUG)

    @classmethod
    def redirect_sys_stdout(cls):
        """
        TESTING PURPOSES ONLY. Redirects all output to a file like object.

        Output from external programs like Git may create unwanted noise during
        testing. Routing normal GRAPE output through its own logger allows for
        complete control of GRAPE's output during normal operations. This is
        not intended for use in normal operations, use logging handlers.
        """
        sys.stdout = cls.STUB_STDOUT

    @classmethod
    def restore_sys_stdout(cls):
        """TESTING PURPOSES ONLY. Restores output routing to sys.stdout."""
        sys.stdout = cls.REAL_STDOUT

    @property
    def all_logger_names(self):
        return list(self.manager.loggerDict.keys())

    def add_logger(self, logger_name, level=logging.DEBUG):
        new_logger = self.manager.getLogger(logger_name)
        new_logger.setLevel(level)

    def add_file_handler_to_root(self, file_name, level=logging.DEBUG):
        """
        Adds a logging handler that writes messages to a file.
        
        Adding a file handler to the root logger is likely sufficient for
        general cases.
        """
        file_handler = self._get_file_handler(file_name,
                                              mode='w',
                                              maxBytes=2**16,
                                              backupCount=3)
        formatter = self.get_file_formatter()
        file_handler.setFormatter(formatter)
        self.__add_handler_to_root(file_handler)

    def add_stdout_handler(self, logger_name=None):
        """
        Adds StreamHandler to root logger, then one or more secondary loggers.

        Output intended for the user should be called with 'logging.info()'.
        NOTE: only accepts messages with the 'info' logging level.
        """
        level = logging.INFO
        stdout_handler = self._get_stream_handler(sys.stdout, level)
        stdout_formatter = self.get_stdout_formatter()
        stdout_handler.setFormatter(stdout_formatter)

        log_filter = SingleLevelFilter(level)
        stdout_handler.addFilter(log_filter)

        self.__add_handler_to_root(stdout_handler)
        self.__add_handler(logger_name, stdout_handler)

    def add_stderr_handler(self, logger_name=None, level=logging.WARNING):
        """
        Adds StreamHandler to root logger, then one or more secondary loggers.

        Output intended for the user should be called with:
        'logging.warning()' if 'level' has been set to 'logging.WARNING',
        or an equivalent call corresponding to a more severe logging level.
        """
        stderr_handler = self._get_stream_handler(sys.stderr, level)
        stderr_formatter = self.get_stderr_formatter(level)
        stderr_handler.setFormatter(stderr_formatter)
        self.__add_handler_to_root(stderr_handler)
        self.__add_handler(logger_name, stderr_handler)

    def __add_handler_to_root(self, handler):
        self.manager.root.addHandler(handler)

    def __add_handler(self, logger_name, handler):
        logger_names = [logger_name] if logger_name else self.all_logger_names
        for logger_name in logger_names:
            logger = self.manager.getLogger(logger_name)
            logger.addHandler(handler)

    def get_file_formatter(self):
        return logging.Formatter(
            '%(processName)-10s %(name)s %(levelname)-8s %(module)s.%(funcName)s %(message)s')

    def get_stdout_formatter(self):
        return logging.Formatter('%(message)s')

    def get_stderr_formatter(self, level=logging.ERROR):
        return logging.Formatter('%(levelname)s: %(message)s')

    def _get_file_handler(self, file_name, level=logging.DEBUG, mode='a',
                          maxBytes=0, backupCount=0, encoding=None, delay=0):
        """Wrapper around Python's implementation."""
        file_handler = logging.handlers.RotatingFileHandler(
            file_name, mode='a', maxBytes=0, backupCount=0,
            encoding=None, delay=0)
        file_handler.setLevel(level)
        return file_handler

    def _get_stream_handler(self, stream, level):
        """Returns a logging handler to send messages to stdout or stderr."""
        stream_handler = logging.StreamHandler(stream)
        stream_handler.setLevel(level)
        return stream_handler


class SingleLevelFilter(logging.Filter):
    """Logging Filter that only accepts LogRecords of a specific level."""

    def __init__(self, level, name=''):
        super(SingleLevelFilter, self).__init__(name)
        self.__level = level

    def filter(self, logRecord):
        return logRecord.levelno == self.__level
