import atexit
import logging
import logging.handlers
import pickle
import select
import socket
import SocketServer
import struct
import threading
from six import add_metaclass
from vine.singleton import Singleton


@add_metaclass(Singleton)
class LoggingServerManager(object):

    LOCALHOST = 'localhost'

    def __init__(self):
        self.log_thread = None
        self.socket_server = None
        atexit.register(self.close_server)

    def is_server_active(self):
        return self.is_socket_open_for_connection() and \
            self.is_logging_thread_active()

    @classmethod
    def is_socket_open_for_connection(cls):
        """Tests connection to server."""
        try:
            s = socket.create_connection(
                (cls.LOCALHOST, logging.handlers.DEFAULT_TCP_LOGGING_PORT)
                )
            s.close()
            return True
        except Exception:
            logging.debug("Logging socket server is not running.")
            return False

    def is_logging_thread_active(self):
        return self.log_thread and self.log_thread.is_alive()

    def start_logging_to_file(self, log_file):
        self._start_server()

        file_formatter = logging.Formatter(
            '%(processName)-10s %(name)s %(levelname)-8s %(module)s.%(funcName)s %(message)s')

        file_handler = logging.handlers.RotatingFileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(file_formatter)

        socket_to_file_logger = logging.getLogger(
            LogRecordStreamHandler.LOGNAME)
        socket_to_file_logger.setLevel(logging.DEBUG)
        socket_to_file_logger.propagate = False

        for handler in socket_to_file_logger.handlers:
            socket_to_file_logger.removeHandler(handler)

        socket_to_file_logger.addHandler(file_handler)
        logging.debug("Setting file handler for: " + log_file)

    def _start_server(self):
        self.close_server()
        self.socket_server = LogRecordSocketReceiver()

        self.log_thread = threading.Thread(
            target=self.socket_server.serve_until_stopped)
        self.log_thread.setDaemon(True)
        self.log_thread.start()
        logging.debug("Started logging socket server in new thread...")

    def close_server(self):
        """Cleans up server side and socket handler (client) side.
        
        Registered with 'atexit' module, cleaned up automaticlly after test.
        """
        logging.debug("Closing socket server connection...")
        is_log_thread_alive = self.is_logging_thread_active()
        if is_log_thread_alive:
            logging.debug("Joining log thread after socket server has closed.")

        if self.is_socket_open_for_connection():
            self.socket_server.stop_server()

        if is_log_thread_alive:
            self.log_thread.join()
        self.log_thread = None


"""
Code below is heavily based on the Python's documentation:
https://docs.python.org/3/howto/logging-cookbook.html#logging-to-a-single-file-from-multiple-processes
"""
class LogRecordStreamHandler(SocketServer.StreamRequestHandler):
    """Handles logging messages sent from various processes to a socket."""

    LOGNAME = 'socket_to_file_logger'

    def handle(self):
        """
        Handle multiple requests - each expected to be a 4-byte length,
        followed by the LogRecord in pickle format. Logs the record
        according to whatever policy is configured locally.
        """
        receivable_len = 4
        while True:
            chunk = self.connection.recv(receivable_len)
            if len(chunk) < receivable_len:
                break
            slen = struct.unpack('>L', chunk)[0]
            chunk = self.connection.recv(slen)
            while len(chunk) < slen:
                chunk = chunk + self.connection.recv(slen - len(chunk))
            obj = self.unPickle(chunk)
            record = logging.makeLogRecord(obj)
            self.handleLogRecord(record)

    def unPickle(self, data):
        return pickle.loads(data)

    def handleLogRecord(self, record):
        if self.server.logname is not None:
            name = self.server.logname
        else:
            name = record.name
        logger = logging.getLogger(name)
        # Filtering should be done at the client end, not here.
        logger.handle(record)


class LogRecordSocketReceiver(SocketServer.ThreadingTCPServer):
    """Simple TCP socket-based logging receiver."""

    allow_reuse_address = True
    logname = LogRecordStreamHandler.LOGNAME

    def __init__(self, host='localhost', port=None,
                 handler=LogRecordStreamHandler):
        if port is None:
            port = logging.handlers.DEFAULT_TCP_LOGGING_PORT
        SocketServer.ThreadingTCPServer.__init__(self, (host, port), handler)
        self.timeout = 1
        self._stop_server = threading.Event()

    def serve_until_stopped(self):
        """Receives logging messages sent from logging.SocketHandler(s)."""
        try:
            while not self._stop_server.is_set():
                rd, _, _ = select.select([self.socket.fileno()],
                                           [], [],
                                           self.timeout)
                if rd:
                    self.handle_request()
        finally:
            self.server_close()

    def stop_server(self):
        """Stops server by setting threading.Event sentinel flag.
        
        Calling LoggingServerManager.is_socket_open_for_connection() eliminates
        the race condition where the current test must free up the socket
        server before a new test tries to bind..
        """
        while LoggingServerManager.is_socket_open_for_connection():
            self._stop_server.set()
