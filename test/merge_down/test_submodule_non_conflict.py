import pytest

from test.merge_down.base import MergeDownTestBase
from test.merge_down.cases import MergeDownSubmoduleNonConflictCase


pytestmark = pytest.mark.slow


class TestMergeDownSubmoduleNonConflict(MergeDownSubmoduleNonConflictCase, MergeDownTestBase):
    """Broad-run shard for non-conflicting submodule merges."""
