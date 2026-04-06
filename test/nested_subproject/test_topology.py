import pytest

from test.nested_subproject.base import NestedSubprojectTestBase
from test.nested_subproject.cases import NestedSubprojectTopologyCase


pytestmark = pytest.mark.slow


class TestNestedSubprojectTopology(NestedSubprojectTopologyCase, NestedSubprojectTestBase):
    """Broad-run shard for nested topology and checkout coverage."""
