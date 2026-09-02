import pytest

from test.clone.base import CloneTestBase
from test.clone.cases import CloneSmokeCase


pytestmark = pytest.mark.slow


class TestCloneSmoke(CloneSmokeCase, CloneTestBase):
    """Broad-run shard for lightweight clone coverage."""
