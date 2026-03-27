import pytest

from test.merge_down.base import MergeDownTestBase
from test.merge_down.cases import MergeDownNestedSubprojectConflictCase


pytestmark = pytest.mark.slow


class TestMergeDownNestedSubproject(MergeDownNestedSubprojectConflictCase, MergeDownTestBase):
    """Broad-run shard for nested-subproject merge conflicts."""
