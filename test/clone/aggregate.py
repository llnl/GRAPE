import pytest

from test.clone.base import CloneTestBase
from test.clone.cases import CloneNestedCase
from test.clone.cases import CloneSmokeCase
from test.clone.cases import CloneSubmoduleCase


pytestmark = pytest.mark.slow


class TestClone(CloneSmokeCase, CloneSubmoduleCase, CloneNestedCase, CloneTestBase):
    """Legacy aggregate clone suite preserved for direct `grape test Clone` use."""
