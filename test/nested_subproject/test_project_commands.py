import pytest

from test.nested_subproject.base import NestedSubprojectTestBase
from test.nested_subproject.cases import NestedSubprojectProjectCommandsCase


pytestmark = pytest.mark.slow


class TestNestedSubprojectProjectCommands(NestedSubprojectProjectCommandsCase, NestedSubprojectTestBase):
    """Broad-run shard for project-wide nested command coverage."""
