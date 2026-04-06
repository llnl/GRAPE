import pytest

from test.publish.base import PublishTestBase
from test.publish.cases import PublishCustomBuildCase
from test.publish.cases import PublishCustomTestCase
from test.publish.cases import PublishFFCascadeCase
from test.publish.cases import PublishFFDefaultCase
from test.publish.cases import PublishFFMergeCase
from test.publish.cases import PublishFFRebaseCase
from test.publish.cases import PublishFFSquashCase
from test.publish.cases import PublishFromNestedSubprojectCase
from test.publish.cases import PublishNestedSubprojectsCase
from test.publish.cases import PublishNewSubmoduleCase
from test.publish.cases import PublishStartStopCase
from test.publish.cases import PublishTopicConfigCase
from test.publish.cases import PublishVersionTickCase


pytestmark = [pytest.mark.publish, pytest.mark.serial, pytest.mark.slow]


class TestPublish(
    PublishFFDefaultCase,
    PublishFFMergeCase,
    PublishFFSquashCase,
    PublishFFCascadeCase,
    PublishFFRebaseCase,
    PublishTopicConfigCase,
    PublishCustomBuildCase,
    PublishCustomTestCase,
    PublishVersionTickCase,
    PublishStartStopCase,
    PublishNestedSubprojectsCase,
    PublishFromNestedSubprojectCase,
    PublishNewSubmoduleCase,
    PublishTestBase,
):
    """Legacy aggregate publish suite."""
