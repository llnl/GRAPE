import pytest

from test.merge_down.base import MergeDownTestBase
from test.merge_down.cases import MergeDownBasicCase


pytestmark = pytest.mark.slow


class TestMergeDownBasic(MergeDownBasicCase, MergeDownTestBase):
    """Broad-run shard for the basic top-level merge flows."""
