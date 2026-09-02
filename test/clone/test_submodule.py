import pytest

from test.clone.base import CloneTestBase
from test.clone.cases import CloneSubmoduleCase


pytestmark = pytest.mark.slow


class TestCloneSubmodule(CloneSubmoduleCase, CloneTestBase):
    """Broad-run shard for the recursive submodule clone path."""
