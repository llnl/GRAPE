import pytest

from test.nested_subproject.base import NestedSubprojectTestBase
from test.nested_subproject.cases import NestedSubprojectProjectCommandsCase
from test.nested_subproject.cases import NestedSubprojectTopologyCase
from test.nested_subproject.cases import NestedSubprojectWorkspaceSyncCase


pytestmark = pytest.mark.slow


class TestNestedSubproject(
    NestedSubprojectTopologyCase,
    NestedSubprojectWorkspaceSyncCase,
    NestedSubprojectProjectCommandsCase,
    NestedSubprojectTestBase,
):
    """Legacy aggregate nested-subproject suite preserved for direct selectors."""
