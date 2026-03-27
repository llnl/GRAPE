import pytest

from test.merge_down.base import MergeDownTestBase
from test.merge_down.cases import MergeDownBasicCase
from test.merge_down.cases import MergeDownNestedSubprojectConflictCase
from test.merge_down.cases import MergeDownSubmoduleConflictCase
from test.merge_down.cases import MergeDownSubmoduleNonConflictCase


pytestmark = pytest.mark.slow


class TestMD(
    MergeDownBasicCase,
    MergeDownSubmoduleNonConflictCase,
    MergeDownSubmoduleConflictCase,
    MergeDownNestedSubprojectConflictCase,
    MergeDownTestBase,
):
    """Legacy aggregate merge-down suite preserved for direct selectors."""
