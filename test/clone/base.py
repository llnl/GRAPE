from contextlib import contextmanager
from io import StringIO
import os
import shutil
import sys
import tempfile

from test import testGrape


class CloneTestBase(testGrape.TestGrape):
    """Shared helpers for the split clone suites.

    These tests still use the older unittest-style harness because the rest of
    the GRAPE suite already builds repository fixtures through `TestGrape`.
    The pytest-facing shard files simply subclass this base so each file can be
    scheduled independently by the broad runner.
    """

    @contextmanager
    def preserved_cwd(self):
        """Restore the working directory after clone mutates process state."""
        cwd = os.getcwd()
        try:
            yield
        finally:
            os.chdir(cwd)

    @contextmanager
    def captured_stdout(self):
        """Temporarily capture `sys.stdout` for docopt help-message checks."""
        doc_output = StringIO()
        tmp_stdout = sys.stdout
        sys.stdout = doc_output
        try:
            yield doc_output
        finally:
            sys.stdout = tmp_stdout
            doc_output.close()

    @contextmanager
    def temp_clone_dir(self):
        """Create and later remove a temp directory used as a clone target."""
        temp_dir = os.path.realpath(tempfile.mkdtemp())
        try:
            yield temp_dir
        finally:
            self._temp_dir_cleanup(temp_dir)

    def _temp_dir_cleanup(self, temp_dir):
        """Skips Windows permissions errors when testing as non-admin user."""

        def skip_rm(*args):
            pass

        shutil.rmtree(temp_dir, onerror=skip_rm)
