import pytest
from unittest.mock import Mock
from unittest.mock import patch

from test.publish.base import PublishTestBase
from test.publish.cases import PublishCustomBuildCase
from test.publish.cases import PublishCustomTestCase
from test.publish.cases import PublishStartStopCase
from test.publish.cases import PublishTopicConfigCase
from test.publish.cases import PublishVersionTickCase
from vine.publish import Publish


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


class _ParseArgsConfig:
    def getPublicBranchFor(self, topic):
        return "master"

    def getMapping(self, section, option):
        return {"topic/test": "0"}

    def get(self, section, option):
        return "False"


def _publish_args(code_reviews_url="https://example.org/gitlab", no_review=False):
    return {
        "--topic": "topic/test",
        "--startAt": None,
        "--public": None,
        "--useBitbucket": "True",
        "--noReview": no_review,
        "--verifySSL": "True",
        "--user": None,
        "--printSteps": False,
        "--tickVersion": "False",
        "--tickOnCascade": 0,
        "--mergeTrain": False,
        "--skipBuild": False,
        "--skipTest": False,
        "--codeReviewsURL": code_reviews_url,
    }


def _parse_publish_args(args):
    publish = Publish()
    publish._workspace_dir = "/tmp"
    with patch("vine.publish.git.currentBranch", return_value="topic/test"), \
            patch("vine.publish.config_parser_global.grapeConfig", return_value=_ParseArgsConfig()):
        publish.parseArgs(args)
    return args


def test_parse_args_defaults_gitlab_user_from_gitlab_service():
    args = _publish_args("https://example.org/gitlab")
    with patch("vine.publish.utility.getUserName", return_value="gitlab-user") as get_user_name:
        _parse_publish_args(args)

    get_user_name.assert_called_once_with(service="GitLab")
    assert args["--user"] == "gitlab-user"


@pytest.mark.parametrize("url", ["https://example.org/bitbucket", "https://example.org/stash"])
def test_parse_args_defaults_bitbucket_user_for_bitbucket_and_stash(url):
    args = _publish_args(url)
    with patch("vine.publish.utility.getUserName", return_value="bitbucket-user") as get_user_name:
        _parse_publish_args(args)

    get_user_name.assert_called_once_with(service="Bitbucket")
    assert args["--user"] == "bitbucket-user"


def test_parse_args_no_review_does_not_resolve_provider_user():
    args = _publish_args("https://example.org/gitlab", no_review=True)
    with patch("vine.publish.utility.getUserName") as get_user_name:
        _parse_publish_args(args)

    get_user_name.assert_not_called()
    assert args["--user"] is None


def test_remote_merge_uses_code_reviews_property_and_provider_merge_signature():
    publish = Publish()
    publish._workspace_dir = "/tmp"
    publish._codeReviews = object()
    pull_request = Mock()
    pull_request.merge.return_value = True
    remote_repo = Mock()
    remote_repo.getOpenPullRequest.return_value = pull_request
    args = {"-m": "merge message", "--deleteTopic": "True"}

    with patch("vine.publish.CodeReviewsFactory.repoObject", return_value=remote_repo) as repo_object, \
            patch("vine.publish.git.checkout") as checkout, \
            patch("vine.publish.git.pull") as pull:
        assert publish.remoteMerge("master", "topic/test", "repo1", args, False, False)

    repo_object.assert_called_once_with(publish._codeReviews)
    remote_repo.getOpenPullRequest.assert_called_once_with("topic/test", "master")
    pull_request.merge.assert_called_once_with(
        merge_commit_message="merge message",
        should_remove_source_branch=True,
        merge_when_pipeline_succeeds=False,
    )
    checkout.assert_called_once_with("master", execution_path="/tmp")
    pull.assert_called_once_with("", execution_path="/tmp")
