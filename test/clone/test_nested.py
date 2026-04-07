import pytest

from test.clone.base import CloneTestBase
from test.clone.cases import CloneNestedCase


pytestmark = pytest.mark.slow


class TestCloneNested(CloneNestedCase, CloneTestBase):
    """Broad-run shard for the recursive nested-subproject clone path."""
