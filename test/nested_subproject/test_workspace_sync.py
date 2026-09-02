import pytest

from test.nested_subproject.base import NestedSubprojectTestBase
from test.nested_subproject.cases import NestedSubprojectWorkspaceSyncCase


pytestmark = pytest.mark.slow


class TestNestedSubprojectWorkspaceSync(NestedSubprojectWorkspaceSyncCase, NestedSubprojectTestBase):
    """Broad-run shard for nested workspace sync and lifecycle coverage."""
