import pytest

from test.publish.base import PublishTestBase
from test.publish.cases import PublishCustomBuildCase
from test.publish.cases import PublishCustomTestCase
from test.publish.cases import PublishStartStopCase
from test.publish.cases import PublishTopicConfigCase
from test.publish.cases import PublishVersionTickCase


pytestmark = [pytest.mark.publish, pytest.mark.slow]


class TestPublishTopicConfig(PublishTopicConfigCase, PublishTestBase):
    pass


class TestPublishCustomBuild(PublishCustomBuildCase, PublishTestBase):
    pass


class TestPublishCustomTest(PublishCustomTestCase, PublishTestBase):
    pass


class TestPublishVersionTick(PublishVersionTickCase, PublishTestBase):
    pass


class TestPublishStartStop(PublishStartStopCase, PublishTestBase):
    pass
