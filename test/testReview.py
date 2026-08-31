import os
import sys
from test import testGrape
from unittest import mock
from vine import Gitlab
from vine import review
from vine import utility
from vine.ReviewRule import ReviewRuleManager


class FakeDiscussion:
    """Minimal GitLab discussion stub for unresolved-thread unit tests."""

    def __init__(self, data):
        self._data = data

    def asdict(self):
        return self._data


class FakeDiscussions:
    """Container stub matching the merge-request discussions API."""

    def __init__(self, discussions):
        self._discussions = discussions

    def list(self, get_all=False):
        return self._discussions


class FakeMergeRequest:
    """Merge-request stub that exposes discussions and a web URL."""

    def __init__(self, discussions, web_url='https://gitlab.example/mr/1'):
        self.discussions = FakeDiscussions(discussions)
        self.web_url = web_url


class FakeRequest:
    """Review-request stub used by the report-formatting helpers."""

    def __init__(self, url='https://gitlab.example/mr/1', threads=None):
        self._url = url
        self._threads = [] if threads is None else threads

    def unresolved_threads(self, ignored_commenters=None):
        return self._threads

    def link(self):
        return self._url


class FakeDescriptionModel:
    """Minimal description model stub for review.execute unit tests."""

    def __init__(self, text='test description'):
        self.reviewRules = {}
        self._text = text

    def add_related_pull_request(self, _url):
        return None

    def clear_related_pull_requests(self):
        return None

    def to_text(self):
        return self._text


class FakeGitlabUser:
    """Minimal user object returned by python-gitlab user lookups."""

    def __init__(self, user_id):
        self.id = user_id


class FakeGitlabUsers:
    """User lookup stub keyed by username."""

    def __init__(self, users):
        self._users = users

    def list(self, all=False, username=None):
        if username in self._users:
            return [FakeGitlabUser(self._users[username])]
        return []


class FakeGitlabMergeRequest:
    """Merge-request stub for update tests."""

    def __init__(self):
        self.title = 'Existing title'
        self.description = 'Existing description'
        self.labels = []
        self.reviewer_ids = []
        self.approvals = mock.Mock()
        self.approvals.set_approvers.side_effect = AssertionError('approval rules should not be updated')
        self.approval_rules = mock.Mock()
        self.save = mock.Mock()


class FakeExistingReviewRequest:
    """Existing review request stub for postPullRequest tests."""

    def __init__(self):
        self.update = mock.Mock(side_effect=AssertionError('request should be unchanged'))

    def toRef(self):
        return 'master'

    def fromRef(self):
        return 'topic/test'

    def version(self):
        return 123

    def title(self):
        return 'Existing title'

    def description(self):
        return 'Existing description'

    def author(self):
        return 'author'

    def link(self):
        return 'https://gitlab.example/mr/1'

    def labels(self):
        return []


class FakeRepoWithExistingRequest:
    """Repo stub returning a single existing pull request."""

    def __init__(self, request):
        self.project = mock.Mock(name='repo1')
        self._request = request

    def pullRequests(self, direction='OUTGOING', at=None, state='open'):
        return [self._request]


class FakeReviewRule:
    """Review-rule stub with configurable repository applicability."""

    def __init__(self, applies):
        self._applies = applies

    def matches_repository(self, _repo_name):
        return self._applies


class TestReview(testGrape.TestGrape):

    def testReview(self):
        args = ["review", "--test", "--user=user", "--proj=proj1", "--repo=repo1"]
        try:
            ret = self.menu.applyMenuChoice("review", args)
        except SystemExit:
            self.fail(f"grape-review failed with output {self.get_output()}")
        self.assertTrue(ret)

    def testReviewWithPrintUnresolvedCommentsOption(self):
        """The CLI should accept the reporting-only flag in test mode."""

        args = ["review", "--test", "--user=user", "--proj=proj1", "--repo=repo1", "--printUnresolvedComments"]
        try:
            ret = self.menu.applyMenuChoice("review", args)
        except SystemExit:
            self.fail(f"grape-review failed with output {self.get_output()}")
        self.assertTrue(ret)

    def testFormatUnresolvedThreadComments(self):
        """Rendered thread output should include file context and note bodies."""

        output = review.formatUnresolvedThreadComments([
            {
                'path': 'src/example.py',
                'line': 42,
                'notes': [
                    {'author': 'alice', 'created_at': '2026-03-19T12:00:00Z', 'body': 'Please rename this.'},
                    {'author': 'bob', 'created_at': None, 'body': 'Working on it.\nWill update shortly.'}
                ]
            }
        ])

        self.assertIn('Unresolved merge request thread comments:', output)
        self.assertIn('[1] src/example.py:42', output)
        self.assertIn('alice (2026-03-19T12:00:00Z)', output)
        self.assertIn('Please rename this.', output)
        self.assertIn('Will update shortly.', output)

    def testFormatUnresolvedThreadCommentsByRepo(self):
        """Repo summaries should include the MR link and numbered threads."""

        output = review.formatUnresolvedThreadCommentsByRepo({
            'grp/repo1': {
                'review_request': FakeRequest(),
                'threads': [
                    {
                        'path': 'src/example.py',
                        'line': 42,
                        'notes': [
                            {'author': 'alice', 'created_at': '2026-03-19T12:00:00Z', 'body': 'Please rename this.'}
                        ]
                    }
                ]
            }
        })

        self.assertIn('Unresolved merge request thread comments by repo:', output)
        self.assertIn('grp/repo1', output)
        self.assertIn('Merge request: https://gitlab.example/mr/1', output)
        self.assertIn('[1] src/example.py:42', output)

    def testGitlabPullRequestUnresolvedThreads(self):
        """Resolved threads and system notes should be filtered from the report."""

        unresolved_discussion = FakeDiscussion({
            'id': 'thread-1',
            'resolved': False,
            'notes': [
                {
                    'system': False,
                    'body': 'Please update the variable name.',
                    'created_at': '2026-03-19T12:00:00Z',
                    'author': {'username': 'alice'},
                    'position': {'new_path': 'src/example.py', 'new_line': 12}
                },
                {
                    'system': True,
                    'body': 'changed this line in version 2',
                    'created_at': '2026-03-19T12:05:00Z',
                    'author': {'username': 'gitlab'}
                },
                {
                    'system': False,
                    'body': 'Ack.',
                    'created_at': '2026-03-19T12:10:00Z',
                    'author': {'name': 'Bob Reviewer'}
                }
            ]
        })
        resolved_discussion = FakeDiscussion({
            'id': 'thread-2',
            'resolved': True,
            'notes': [
                {
                    'system': False,
                    'body': 'Looks good now.',
                    'created_at': '2026-03-19T12:20:00Z',
                    'author': {'username': 'charlie'}
                }
            ]
        })

        pull_request = Gitlab.PullRequest(FakeMergeRequest([unresolved_discussion, resolved_discussion]), gitlab=None)
        unresolved_threads = pull_request.unresolved_threads()

        self.assertEqual(1, len(unresolved_threads))
        self.assertEqual('thread-1', unresolved_threads[0]['id'])
        self.assertEqual('src/example.py', unresolved_threads[0]['path'])
        self.assertEqual(12, unresolved_threads[0]['line'])
        self.assertEqual(2, len(unresolved_threads[0]['notes']))
        self.assertEqual('alice', unresolved_threads[0]['notes'][0]['author'])
        self.assertEqual('Bob Reviewer', unresolved_threads[0]['notes'][1]['author'])

    def testGitlabPullRequestUnresolvedThreadsWhenDiscussionResolvedButNoteUnresolved(self):
        """A still-open resolvable note keeps the discussion in the output."""

        discussion = FakeDiscussion({
            'id': 'thread-1',
            'resolved': True,
            'notes': [
                {
                    'system': False,
                    'body': 'This still needs work.',
                    'created_at': '2026-03-19T12:00:00Z',
                    'author': {'username': 'alice'},
                    'resolvable': True,
                    'resolved': False,
                    'position': {'new_path': 'src/example.py', 'new_line': 12}
                }
            ]
        })

        pull_request = Gitlab.PullRequest(FakeMergeRequest([discussion]), gitlab=None)
        unresolved_threads = pull_request.unresolved_threads()

        self.assertEqual(1, len(unresolved_threads))
        self.assertEqual('thread-1', unresolved_threads[0]['id'])

    def testGitlabPullRequestUnresolvedThreadsIgnoresFilteredCommenters(self):
        """Ignored commenters should be dropped without hiding human feedback."""

        discussion = FakeDiscussion({
            'id': 'thread-1',
            'resolved': False,
            'notes': [
                {
                    'system': False,
                    'body': 'Duo suggestion',
                    'created_at': '2026-03-19T12:00:00Z',
                    'author': {'username': 'GitLabDuo'}
                },
                {
                    'system': False,
                    'body': 'Human feedback',
                    'created_at': '2026-03-19T12:10:00Z',
                    'author': {'username': 'alice'}
                }
            ]
        })

        pull_request = Gitlab.PullRequest(FakeMergeRequest([discussion]), gitlab=None)
        unresolved_threads = pull_request.unresolved_threads(ignored_commenters={'gitlabduo'})

        self.assertEqual(1, len(unresolved_threads))
        self.assertEqual(1, len(unresolved_threads[0]['notes']))
        self.assertEqual('alice', unresolved_threads[0]['notes'][0]['author'])

    def testGetUserNameAcceptsLegacyDefaultNameArgument(self):
        """Legacy callers can still pass a default user name positionally."""

        fake_home = os.path.join(self.repo, 'fake-home')
        os.makedirs(fake_home)

        with mock.patch('vine.utility.config_parser_global.get_env_config_path', return_value=fake_home):
            with mock.patch('vine.utility.userInput', side_effect=['probinso', False]) as user_input:
                user_name = utility.getUserName('probinso')

        self.assertEqual('probinso', user_name)
        user_input.assert_any_call('Enter LC User Name:', 'probinso')

    def testGetUserNameInfersGitLabServiceFromArgs(self):
        """Parsed code review args select the GitLab service key."""

        fake_home = os.path.join(self.repo, 'fake-home-gitlab')
        os.makedirs(fake_home)

        args = {'--user': None, '--codeReviewsURL': 'https://example.org/gitlab'}
        with mock.patch('vine.utility.config_parser_global.get_env_config_path', return_value=fake_home):
            with mock.patch('vine.utility.userInput', side_effect=['git-user', False]) as user_input:
                user_name = utility.getUserName(args)

        self.assertEqual('git-user', user_name)
        user_input.assert_any_call('Enter GitLab User Name:', os.getenv('USER'))

    def testGetUserNameInfersBitbucketServiceFromArgs(self):
        """Bitbucket and Stash URLs continue to use the Bitbucket service key."""

        fake_home = os.path.join(self.repo, 'fake-home-bitbucket')
        os.makedirs(fake_home)

        args = {'--user': None, '--codeReviewsURL': 'https://example.org/stash'}
        with mock.patch('vine.utility.config_parser_global.get_env_config_path', return_value=fake_home):
            with mock.patch('vine.utility.userInput', side_effect=['bb-user', False]) as user_input:
                user_name = utility.getUserName(args)

        self.assertEqual('bb-user', user_name)
        user_input.assert_any_call('Enter Bitbucket User Name:', os.getenv('USER'))

    def testGetUserNameUnknownProviderUsesGenericService(self):
        """Unknown provider URLs keep the historical LC service behavior."""

        fake_home = os.path.join(self.repo, 'fake-home-generic')
        os.makedirs(fake_home)

        args = {'--user': None, '--codeReviewsURL': 'https://example.org/reviews'}
        with mock.patch('vine.utility.config_parser_global.get_env_config_path', return_value=fake_home):
            with mock.patch('vine.utility.userInput', side_effect=['generic-user', False]) as user_input:
                user_name = utility.getUserName(args)

        self.assertEqual('generic-user', user_name)
        user_input.assert_any_call('Enter LC User Name:', os.getenv('USER'))

    def testGitlabUpdateAssignsReviewersWithoutApprovalRules(self):
        """GitLab reviewer updates should not create or update approval rules."""

        merge_request = FakeGitlabMergeRequest()
        merge_request.approval_rules.list.side_effect = AssertionError('approval rules should not be listed')
        gitlab = mock.Mock()
        gitlab.users = FakeGitlabUsers({'alice': 101, 'bob': 102})
        pull_request = Gitlab.PullRequest(merge_request, gitlab)

        pull_request.update(
            123,
            reviewers=['alice', 'bob']
        )

        self.assertCountEqual([101, 102], merge_request.reviewer_ids)
        merge_request.approvals.set_approvers.assert_not_called()
        merge_request.save.assert_called_once()

    def testGitlabUpdateClearsReviewersWithEmptyList(self):
        """An empty reviewer list should clear GitLab MR reviewers."""

        merge_request = FakeGitlabMergeRequest()
        merge_request.reviewer_ids = [101]
        gitlab = mock.Mock()
        gitlab.users = FakeGitlabUsers({})
        pull_request = Gitlab.PullRequest(merge_request, gitlab)

        pull_request.update(123, reviewers=[])

        self.assertEqual([], merge_request.reviewer_ids)
        merge_request.save.assert_called_once()

    def testGitlabUpdateRetargetsMergeRequest(self):
        """GitLab target updates are persisted with other MR metadata."""
        merge_request = FakeGitlabMergeRequest()
        merge_request.target_branch = 'master'
        pull_request = Gitlab.PullRequest(merge_request, mock.Mock())

        pull_request.update(123, target_branch='topic/parent')

        self.assertEqual('topic/parent', merge_request.target_branch)
        merge_request.save.assert_called_once()

    def testGetApplicableReviewersReturnsUserList(self):
        """Provider adapters should receive usernames, not review-rule groups."""

        review_option = review.Review()
        reviewer_usernames = review_option.getApplicableReviewers(
            'repo1',
            {
                'code': {'label': 'Code Review', 'reviewers': ['alice', 'bob']},
                'docs': {'label': 'Docs Review', 'reviewers': ['alice', 'carol']},
                'other': {'label': 'Other Review', 'reviewers': ['dave']},
            },
            {
                'code': FakeReviewRule(applies=True),
                'docs': FakeReviewRule(applies=True),
                'other': FakeReviewRule(applies=False),
            }
        )

        self.assertEqual(['alice', 'bob', 'carol'], reviewer_usernames)

    def testGetApplicableReviewersDistinguishesNoMatchFromClearReviewers(self):
        """No matching rule leaves reviewers alone; matching empty rules clear them."""

        review_option = review.Review()

        no_match = review_option.getApplicableReviewers(
            'repo1',
            {'code': {'label': 'Code Review', 'reviewers': ['alice']}},
            {'code': FakeReviewRule(applies=False)}
        )
        clear_reviewers = review_option.getApplicableReviewers(
            'repo1',
            {'code': {'label': 'Code Review', 'reviewers': []}},
            {'code': FakeReviewRule(applies=True)}
        )

        self.assertIsNone(no_match)
        self.assertEqual([], clear_reviewers)

    def testPostPullRequestLeavesUnchangedRequestAlone(self):
        """Unchanged review requests should not be updated."""

        existing_request = FakeExistingReviewRequest()
        repo = FakeRepoWithExistingRequest(existing_request)
        args = {
            '--state': 'open',
            '--update': False,
            '--add': False,
            '--prepend': False,
            '--append': False,
            '--repo': 'repo1',
        }

        request = review.postPullRequest(
            repo,
            'Existing title',
            'topic/test',
            'master',
            'Existing description',
            None,
            args,
            self.repo,
        )

        self.assertIs(existing_request, request)
        existing_request.update.assert_not_called()

    def testPostPullRequestRetargetsStackReviewInsteadOfDuplicating(self):
        """A source-matched stack MR is repaired when its target changed."""
        existing_request = FakeExistingReviewRequest()
        existing_request.toRef = mock.Mock(return_value='master')
        existing_request.supportsTargetUpdate = mock.Mock(return_value=True)
        existing_request.update = mock.Mock(return_value=existing_request)
        repo = FakeRepoWithExistingRequest(existing_request)
        args = {
            '--state': 'open',
            '--update': False,
            '--add': False,
            '--prepend': False,
            '--append': False,
            '--repo': 'repo1',
            '--stackRetarget': True,
        }

        request = review.postPullRequest(
            repo, 'Existing title', 'topic/test', 'topic/parent',
            'Existing description', None, args, self.repo)

        self.assertIs(existing_request, request)
        existing_request.update.assert_called_once_with(
            123, title='Existing title', description='Existing description',
            reviewers=None, wip=None, add_labels=[], remove_labels=[],
            target_branch='topic/parent')

    def testDefaultGrapeReviewRuleLabelIsStable(self):
        """The built-in GRAPE review-rule label should remain backwards compatible."""

        default_rule = ReviewRuleManager.get_default_grape_rule(active=True)

        self.assertEqual('GRAPE Reviewers', default_rule.label)

    def testGetIgnoredCommenters(self):
        """Configured ignored commenters should be normalized to lowercase."""

        ignored_commenters = review.getIgnoredCommenters({
            '--ignoreCommenter': ['Alice', 'bob']
        })

        self.assertEqual({'alice', 'bob'}, ignored_commenters)

    def testGetIgnoredCommentersUsesGitlabDuoByDefault(self):
        """GitLab Duo is ignored by default when no override is provided."""

        ignored_commenters = review.getIgnoredCommenters({
            '--ignoreCommenter': []
        })

        self.assertEqual({'gitlabduo'}, ignored_commenters)

    def testPrintUnresolvedCommentsByRepo(self):
        """Only repos with unresolved threads should appear in the report."""

        repo_contexts = {
            'grp/repo1': {
                'review_request': FakeRequest('https://gitlab.example/mr/1', [
                    {
                        'path': 'src/example.py',
                        'line': 42,
                        'notes': [
                            {'author': 'alice', 'created_at': '2026-03-19T12:00:00Z', 'body': 'Please rename this.'}
                        ]
                    }
                ])
            },
            'grp/repo2': {
                'review_request': FakeRequest('https://gitlab.example/mr/2', [])
            }
        }

        with mock.patch('vine.review.Review._get_report_repo_contexts', return_value=repo_contexts):
            with self.assertLogs(level='INFO') as logs:
                ret = review.printUnresolvedCommentsByRepo(
                    git_host=None,
                    top_repo_context=None,
                    args={'--ignoreCommenter': []}
                )

        self.assertTrue(ret)
        output = '\n'.join(logs.output)
        self.assertIn('grp/repo1', output)
        self.assertNotIn('\ngrp/repo2\n  Merge request:', output)

    def testPrintUnresolvedCommentsPathSkipsPushAndUpdate(self):
        """The reporting-only path must not push branches or update the MR."""

        fake_request = mock.Mock()
        fake_request.unresolved_threads.return_value = []
        fake_request.link.return_value = 'https://gitlab.example/mr/1'

        top_repo_context = {
            'project_name': 'grp',
            'repo_name': 'repo1',
            'review_request': fake_request,
            'source_branch': 'topic/test',
            'target_branch': 'master',
            'grape_config': mock.Mock()
        }

        args = {
            '--test': False,
            '--verifySSL': 'true',
            '--codeReviewsURL': 'https://example.org/gitlab',
            '--ssh_pat_port': '7999',
            '--ssh_pat_url': 'git@example.org',
            '--project': 'grp',
            '--repo': 'repo1',
            '--source': 'topic/test',
            '--target': 'master',
            '--printUnresolvedComments': True,
            '--noLocal': False,
            '--state': 'open',
            '--subprojectsOnly': False,
            '--noRecurse': True,
            '--recurse': False,
            '--noRecurseSubprojects': True
        }

        review_option = review.Review()
        review_option.workspace_dir = self.repo

        with mock.patch('vine.review.utility.getUserName', return_value='user'):
            with mock.patch('vine.review.CodeReviewsFactory.makeCodeReviews', return_value=mock.Mock(url='https://example.org/gitlab')):
                with mock.patch.object(review.Review, '_get_top_repo_context', return_value=top_repo_context):
                    with mock.patch('vine.review.printUnresolvedCommentsByRepo', return_value=True) as print_comments:
                        with mock.patch('vine.review.git.push', side_effect=AssertionError('push should not be called')):
                            with mock.patch('vine.review.postPullRequest', side_effect=AssertionError('postPullRequest should not be called')):
                                ret = review_option.execute(args)

        self.assertTrue(ret)
        print_comments.assert_called_once()

    def testReviewUsesQuietRemoteMessagesForPushes(self):
        """Review-triggered pushes should suppress surfaced remote notices."""

        args = {
            '--test': True,
            '--verifySSL': 'true',
            '--codeReviewsURL': 'https://example.org/gitlab',
            '--ssh_pat_port': '7999',
            '--ssh_pat_url': 'git@example.org',
            '--project': 'grp',
            '--repo': 'repo1',
            '--source': 'topic/test',
            '--target': 'master',
            '--printUnresolvedComments': False,
            '--noLocal': False,
            '--state': 'open',
            '--subprojectsOnly': False,
            '--noRecurse': True,
            '--recurse': False,
            '--noRecurseSubprojects': True,
            '--draft': False,
            '--ready': False,
            '--title': None,
            '--descr': None,
            '-m': None,
            '--update': False,
            '--add': False,
            '--prepend': False,
            '--append': False,
            '--reviewers': None,
            '--skiplabels': True,
            '--label_ref': None,
            '--pushModifiedOnly': False,
            '--skipSubproject': [],
            '--ignoreCommenter': [],
            '--user': 'user',
        }

        review_option = review.Review()
        review_option.workspace_dir = self.repo

        fake_request = mock.Mock()
        fake_request.link.return_value = 'https://gitlab.example/mr/1'
        fake_request.description.return_value = 'test description'

        fake_menu = mock.Mock()
        fake_menu.applyMenuChoice.side_effect = lambda choice, argv: True

        fake_review_rule_manager = mock.Mock()
        fake_review_rule_manager.reviewRules = {}
        fake_review_rule_manager.get_default_rule.return_value = mock.Mock(name='default', label='Default')

        top_repo_context = {
            'project_name': 'grp',
            'repo_name': 'repo1',
            'review_request': None,
            'source_branch': 'topic/test',
            'target_branch': 'master',
            'grape_config': mock.Mock()
        }

        with mock.patch('vine.review.utility.getUserName', return_value='user'):
            with mock.patch('vine.review.CodeReviewsFactory.makeCodeReviews', return_value=mock.Mock(url='https://example.org/gitlab')):
                with mock.patch.object(review.Review, '_get_top_repo_context', return_value=top_repo_context):
                    with mock.patch('vine.review.git.push') as git_push:
                        with mock.patch('vine.review.ReviewRuleManager.from_config', return_value=fake_review_rule_manager):
                            with mock.patch('vine.review.PullRequestDescriptionModel.from_text', return_value=FakeDescriptionModel()):
                                with mock.patch('vine.review.parseReviewers', return_value={}):
                                    with mock.patch('vine.review.CodeReviewsFactory.repoObject', return_value=mock.Mock()):
                                        with mock.patch('vine.review.postPullRequest', return_value=fake_request):
                                            with mock.patch('vine.review.git.hasBranch', return_value=True):
                                                with mock.patch('vine.review.git.branchUpToDateWith', return_value=False):
                                                    with mock.patch('vine.review.git.log', return_value='abc123 commit'):
                                                        with mock.patch('vine.review.grapeMenu.menu', return_value=fake_menu):
                                                            ret = review_option.execute(args)

        self.assertTrue(ret)
        git_push.assert_called_with('origin topic/test', execution_path=self.repo,
                                    quietRemoteMessages=True)
        fake_menu.applyMenuChoice.assert_any_call(
            'push',
            ['push', '--noTopLevel', '--quietRemoteMessages', '--noRecurse', '--noRecurseSubprojects']
        )
