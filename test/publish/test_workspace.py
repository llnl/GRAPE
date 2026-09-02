import pytest

from test.publish.base import PublishTestBase
from test.publish.cases import PublishFromNestedSubprojectCase
from test.publish.cases import PublishNestedSubprojectsCase
from test.publish.cases import PublishNewSubmoduleCase


pytestmark = [pytest.mark.publish, pytest.mark.slow]


class TestPublishNestedSubprojects(PublishNestedSubprojectsCase, PublishTestBase):
    pass


class TestPublishFromNestedSubproject(PublishFromNestedSubprojectCase, PublishTestBase):
    pass


class TestPublishNewSubmodule(PublishNewSubmoduleCase, PublishTestBase):
    pass
