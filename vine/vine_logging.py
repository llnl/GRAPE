from functools import wraps
import logging
import logging.handlers
import StringIO
import os
import sys
from six import add_metaclass
from vine.vine_log_server import LoggingServerManager
from vine.singleton import Singleton


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


@add_metaclass(Singleton)
class GrapeLogger(object):
    """
    Logging utility that logs messages to stdout, stderr, or a logging server.

    GrapeLogger provides a controlled layer between messaging and the OS.
    This separation can simplify testing output and managing verbosity levels.
    Messages sent to the logging server are saved to a log file. The server
    is accesible to all forked/spawned processes and should be used in favor
    of directly using a logging.FileHandler (to avoid deadlock).
    """

    REAL_STDOUT = sys.stdout
    STUB_STDOUT = StringIO.StringIO()


    def __init__(self):
        self.log_file = None
        self.socket_server = LoggingServerManager()

        self.manager = logging.Manager(logging.root)
        self.manager.root.setLevel(logging.DEBUG)
        self._silence_root_logger()

    def _silence_root_logger(self):
        """
        Redirects root logger output to /dev/null or the Windows equivalent.

        Starting point before registering shared logging handlers to the root
        logger and other specialized loggers. These shared handlers propagate
        messages for controlled printing and file logging.
        """
        # This while loop is more reliable than an equivalent for loop due to
        # an unexplored delay that occurs between modifying "self.manager.root"
        # and the "logging.RootLogger" object. These 2 objects are identical.
        while self.manager.root.handlers:
            self.manager.root.removeHandler(self.manager.root.handlers[0])

        # Accepts everything, propagates messages through handlers, emits nothing.
        devnull_handler = logging.FileHandler(os.devnull)
        self.manager.root.addHandler(devnull_handler)

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

    def is_logging_to_socket(self):
        if not any(isinstance(handler, logging.handlers.SocketHandler)
                   for handler in self.manager.root.handlers):
            return False

        return self.socket_server.is_server_active()

    def is_logging_to_stdout(self):
        return self._is_logging_to_stream(sys.stdout, logging.INFO)

    def is_logging_to_stdout_debug(self):
        return self._is_logging_to_stream(sys.stdout, logging.DEBUG)

    def is_logging_to_stderr(self):
        return self._is_logging_to_stream(sys.stderr)

    def _is_logging_to_stream(self, stream, logging_level=None):
        for handler in self.manager.root.handlers:
            if isinstance(handler, logging.StreamHandler) \
                and handler.stream == stream:
                    if logging_level:
                        return handler.level == logging_level
                    return True
        return False

    def _log_to_socket(self):
        """Log to socket server that then logs messages to a file.

        Adding the SocketHandler only works if LogRecordSocketReceiver is
        running. This is a safe assumption since GrapeLogger instantiates
        LoggingServerManager, and LoggingServerManager starts running
        LogRecordSocketReceiver.
        """
        if self.is_logging_to_socket():
            logging.warning("Skipping setup for logging to socket. " +
                            "Already configured.")
            return

        socket_handler = self.get_socket_handler()
        self.manager.root.addHandler(socket_handler)

    def get_socket_handler(self):
        """Returns a logging handler that logs to a running socket server.

        Socket server assumed to be up and running before adding SocketHandler
        to any logger. This approach circumvents race conditions when multiple
        processes try to write to a single file. Using a multiprocessing.Queue
        was carefully considered but disregarded for the following reasons:

        Grape executes multiple tasks in parallel using its own modified
        version of Python's multiprocessing.Pool. Grape's custom pool workers
        are non-daemonic, allowing the workers to create subprocesses that can
        execute non-Pythonic tasks such as Git commands. Each pool worker
        executes its task within a new process and starts with no reference to
        the main process' logging configurations. Sharing a reference to a
        multiprocessing.Queue would bridge this interprocess communication gap
        if Grape had direct access to the constructor of each spawned process
        (it does not).

        Instead, each process can be use this SocketHandler to propagate
        logging messages to the localhost's default TCP logging port. Messages
        propagated through each process' SocketHandler all route to a single,
        unique socket server. This socket server (LogRecordSocketReceiver)
        contains a handler that routes the messages into a file.

        NOTE: always close each SocketHandler when finished.
        """
        socket_formatter = logging.Formatter(
            '%(processName)-10s %(name)s %(levelname)-8s %(module)s.%(funcName)s %(message)s')

        socket_handler = logging.handlers.SocketHandler(
            LoggingServerManager.LOCALHOST,
            logging.handlers.DEFAULT_TCP_LOGGING_PORT)
        socket_handler.setFormatter(socket_formatter)

        return socket_handler

    def log_to_file(self, log_file):
        self.log_file = log_file
        self.socket_server.start_logging_to_file(log_file)
        self._log_to_socket()

    def get_log_file_contents(self):
        if self.log_file and os.path.isfile(self.log_file):
            with open(self.log_file) as log_file:
                log_file_contents = log_file.read()
            return log_file_contents
        return ''

    def log_to_stderr(self):
        """Prints logging.warning() (or more severe) calls to sys.stderr."""
        if self.is_logging_to_stderr():
            logging.debug("Logging to stderr already set up.")
            return
        self._set_up_log_to_stream(StreamHandlerFactory.STDERR)

    def log_to_stdout(self):
        """Prints logging.info() calls to sys.stdout."""
        if self.is_logging_to_stdout():
            logging.debug("Logging to stdout already set up.")
            return
        self._set_up_log_to_stream(StreamHandlerFactory.STDOUT)

    def log_to_stdout_debug(self):
        """Prints logging.debug() calls to sys.stdout."""
        if self.is_logging_to_stdout_debug():
            logging.debug("Debugging logging to stdout already set up.")
            return
        self._set_up_log_to_stream(StreamHandlerFactory.DEBUG)

    def _set_up_log_to_stream(self, stream_type):
        stream_handler_factory = StreamHandlerFactory()
        stream_handler = stream_handler_factory(stream_type)
        self.manager.root.addHandler(stream_handler)

    def clean_up_server(self):
        self.socket_server.close_server()
        for handler in self.manager.root.handlers:
            if isinstance(handler, logging.handlers.SocketHandler):
                self.manager.root.removeHandler(handler)


class StreamHandlerFactory(object):

    DEBUG = 'debug'
    STDERR = 'stderr'
    STDOUT = 'stdout'

    def __call__(self, stream):
        if stream == self.STDOUT:
            return self.get_stdout_logger()
        elif stream == self.STDERR:
            return self.get_stderr_logger()
        elif stream == self.DEBUG:
            return self.get_stdout_logger(logging.DEBUG)
        else:
            logging.warning("StreamHandlerFactory: Invalid stream type given.")

    def get_stdout_logger(self, logging_level=logging.INFO):
        """Returns a logger that exclusively logs to sys.stdout.

        Logger only propagates 'logging.info()' messages to sys.stdout unless
        logging level specified.
        """
        stdout_filter = SingleLevelFilter(logging_level)

        stdout_formatter = self._get_formatter()

        stdout_handler = logging.StreamHandler(sys.stdout)
        stdout_handler.setLevel(logging_level)
        stdout_handler.addFilter(stdout_filter)
        stdout_handler.setFormatter(stdout_formatter)
        return stdout_handler

    def get_stderr_logger(self):
        """Returns a logger that exclusively logs to sys.stderr.

        Logger propagates messages to sys.stderr given the following severity
        levels: 'logging.WARNING', 'logging.ERROR', and 'logging.CRITICAL'.
        """
        stderr_formatter = self._get_formatter(self.STDERR)

        stderr_handler = logging.StreamHandler(sys.stderr)
        stderr_handler.setLevel(logging.WARNING)
        stderr_handler.setFormatter(stderr_formatter)
        return stderr_handler

    def _get_formatter(self, stream=sys.stdout):
        if stream == sys.stdout:
            return logging.Formatter('GRAPE: %(message)s')
        elif stream == sys.stderr:
            return logging.Formatter('%(levelname)s: %(message)s')


class SingleLevelFilter(logging.Filter):
    """Logging Filter that only accepts LogRecords of a specific level."""

    def __init__(self, level, name=''):
        super(SingleLevelFilter, self).__init__(name)
        self.__level = level

    def filter(self, logRecord):
        return logRecord.levelno == self.__level
