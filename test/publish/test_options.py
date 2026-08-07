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
    """Minimal grape config stub for Publish.parseArgs unit tests."""

    def getPublicBranchFor(self, topic):
        """Return the public branch used by the parseArgs fixtures."""
        return "master"

    def getMapping(self, section, option):
        """Return mappings needed by parseArgs without reading real config."""
        return {"topic/test": "0"}

    def get(self, section, option):
        """Return disabled boolean config defaults used by parseArgs."""
        return "False"


def _publish_args(code_reviews_url="https://example.org/gitlab", no_review=False):
    """Build the subset of parsed publish args needed by parseArgs tests."""
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


def _commit_message_args(no_review=False):
    """Build the subset of parsed publish args needed by loadCommitMessage."""
    return {
        "--sendEmail": False,
        "--noReview": no_review,
        "--noUpdateLog": False,
        "<CommitMessageFile>": None,
        "-m": None,
    }


def _parse_publish_args(args):
    """Run Publish.parseArgs with git and config dependencies patched out."""
    publish = Publish()
    publish._workspace_dir = "/tmp"
    with patch("vine.publish.git.currentBranch", return_value="topic/test"), \
            patch("vine.publish.config_parser_global.grapeConfig", return_value=_ParseArgsConfig()):
        publish.parseArgs(args)
    return args


def test_parse_args_defaults_gitlab_user_from_gitlab_service():
    """GitLab publish args delegate username resolution to utility."""
    args = _publish_args("https://example.org/gitlab")
    with patch("vine.publish.utility.getUserName", return_value="gitlab-user") as get_user_name:
        _parse_publish_args(args)

    get_user_name.assert_called_once_with(args)
    assert args["--user"] == "gitlab-user"


@pytest.mark.parametrize("url", ["https://example.org/bitbucket", "https://example.org/stash"])
def test_parse_args_defaults_bitbucket_user_for_bitbucket_and_stash(url):
    """Bitbucket and Stash publish args delegate username resolution to utility."""
    args = _publish_args(url)
    with patch("vine.publish.utility.getUserName", return_value="bitbucket-user") as get_user_name:
        _parse_publish_args(args)

    get_user_name.assert_called_once_with(args)
    assert args["--user"] == "bitbucket-user"


def test_parse_args_no_review_does_not_resolve_provider_user():
    """--noReview skips username lookup because no provider calls are made."""
    args = _publish_args("https://example.org/gitlab", no_review=True)
    with patch("vine.publish.utility.getUserName") as get_user_name:
        _parse_publish_args(args)

    get_user_name.assert_not_called()
    assert args["--user"] is None


def test_parse_args_unknown_provider_uses_generic_username_resolution():
    """Unknown provider URLs still delegate username resolution to utility."""
    args = _publish_args("https://example.org/reviews")
    with patch("vine.publish.utility.getUserName", return_value="env-user") as get_user_name:
        _parse_publish_args(args)

    get_user_name.assert_called_once_with(args)
    assert args["--user"] == "env-user"


def test_remote_merge_uses_code_reviews_property_and_provider_merge_signature():
    """Remote merge uses the cached provider and the neutral merge arguments."""
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


def test_load_commit_message_loads_review_metadata_without_verifying_review():
    """Commit-message loading does not run full review verification."""
    publish = Publish()
    publish.progress["commitMsg"] = "existing commit message"
    args = _commit_message_args(no_review=True)
    publish.verifyCompletedReview = Mock(side_effect=AssertionError("unexpected review verification"))

    assert publish.loadCommitMessage(args)

    publish.verifyCompletedReview.assert_not_called()
    assert args["-m"] == "existing commit message"
    assert publish.progress["reviewers"] == "No reviewers"
    assert publish.progress["author"] == ""
    assert publish.progress["author_username"] == ""
    assert publish.progress["author_email"] == ""


def test_load_commit_message_populates_review_metadata_from_pull_request():
    """Commit-message loading keeps update-log and email metadata available."""
    publish = Publish()
    publish.progress["commitMsg"] = "existing commit message"
    pull_request = Mock()
    pull_request.reviewers.return_value = [
        ("reviewer1", False, "Reviewer One"),
        ("reviewer2", True, "Reviewer Two"),
    ]
    pull_request.authorName.return_value = "Author Name"
    pull_request.author.return_value = "author.user"
    pull_request.authorEmail.return_value = "author@example.org"
    publish.openPullRequest = Mock(return_value=pull_request)
    publish.verifyCompletedReview = Mock(side_effect=AssertionError("unexpected review verification"))
    args = _commit_message_args()

    assert publish.loadCommitMessage(args)

    publish.openPullRequest.assert_called_once_with()
    publish.verifyCompletedReview.assert_not_called()
    assert publish.progress["reviewers"] == "Reviewer One, Reviewer Two"
    assert publish.progress["author"] == "Author Name"
    assert publish.progress["author_username"] == "author.user"
    assert publish.progress["author_email"] == "author@example.org"


def test_publish_flow_verifies_completed_review_once_after_target_verification():
    """Normal publish ordering invokes full review verification only at its step."""
    publish = Publish()
    publish._workspace_dir = "/tmp"
    publish.progress["commitMsg"] = "existing commit message"
    publish.progress["startingSHA"] = "abc123"
    publish.modifiedNestedProjects = []
    publish.modifiedOuter = True
    args = {
        "--abort": False,
        "--mergeUpdateLogs": False,
        "--markMRWithVersion": False,
        "--quick": False,
        "--sendEmail": False,
        "--mergeTrain": False,
        "--startAt": "verifyPublishActions",
        "--stopAt": "postVerify",
        "--printSteps": False,
        "--topic": "topic/test",
        "--public": "master",
        "--recurse": False,
        "--noverify": False,
        "--noReview": False,
        "--noUpdateLog": False,
        "<CommitMessageFile>": None,
        "-m": None,
    }

    publish.set_progress_file = Mock()
    publish.dumpProgress = Mock()
    publish._gitIdentityAvailable = Mock(return_value=True)
    publish.parseArgs = Mock()
    publish.loadPublishTargets = Mock(return_value=True)
    publish.loadReviewMetadata = Mock(return_value=True)
    publish.askWhetherToDelete = Mock(return_value=True)
    publish.ensureReview = Mock(return_value=True)
    publish.verifyCompletedReview = Mock(return_value=True)

    with patch("vine.publish.git.getModifiedSubmodules", return_value=[]), \
            patch("vine.publish.utility.userInput", return_value=True):
        assert publish.execute(args)

    publish.loadReviewMetadata.assert_called_once_with(args)
    publish.verifyCompletedReview.assert_called_once_with(args)
