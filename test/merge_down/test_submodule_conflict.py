import pytest

from test.merge_down.base import MergeDownTestBase
from test.merge_down.cases import MergeDownSubmoduleConflictCase


pytestmark = pytest.mark.slow


class TestMergeDownSubmoduleConflict(MergeDownSubmoduleConflictCase, MergeDownTestBase):
    """Broad-run shard for submodule-conflict merge flows."""
