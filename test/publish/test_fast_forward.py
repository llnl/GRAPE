import pytest

from test.publish.base import PublishTestBase
from test.publish.cases import PublishFFCascadeCase
from test.publish.cases import PublishFFDefaultCase
from test.publish.cases import PublishFFMergeCase
from test.publish.cases import PublishFFRebaseCase
from test.publish.cases import PublishFFSquashCase


pytestmark = [pytest.mark.publish, pytest.mark.slow]


class TestPublishFFDefault(PublishFFDefaultCase, PublishTestBase):
    pass


class TestPublishFFMerge(PublishFFMergeCase, PublishTestBase):
    pass


class TestPublishFFSquash(PublishFFSquashCase, PublishTestBase):
    pass


class TestPublishFFCascade(PublishFFCascadeCase, PublishTestBase):
    pass


class TestPublishFFRebase(PublishFFRebaseCase, PublishTestBase):
    pass
