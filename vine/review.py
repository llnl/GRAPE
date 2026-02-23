import ast
import io
import os
import logging
import re
import urllib
from configparser import NoSectionError, NoOptionError
from stashy import errors as stashy_errors
from vine import CodeReviewsFactory
from vine import Atlassian
from vine import Gitlab
from vine import config_parser_base
from vine import config_parser_global
from vine import config_parser_user
from vine import grape_errors
from vine import grapeGit as git
from vine import grapeMenu
from vine import multi_repo_cmd_launcher
from vine.PullRequestDescriptionModel import PullRequestDescriptionModel
from vine import submodules
from vine import utility
from vine import version
from vine import vine_logging
from vine.option import Option
from vine.workspace_dir_handler import WorkspaceDirHandler
from vine.vine_logging import log_wrapper
from vine.ReviewRule import ReviewRuleManager

# Prepare Feature Branch for review
class Review(Option, WorkspaceDirHandler):
    """
    grape review
    Usage: grape-review [--update | --add]
                        [--draft | --ready]
                        [--title=<title>]
                        [--descr=<file> | -m <description>]
                        [--user=<userName> ]
                        [--reviewers=<userNames>]
                        [--source=<topicBranch>]
                        [--target=<publicBranch>]
                        [--state=<openMergedDeclined>]
                        [--codeReviewsURL=<url>]
                        [--verifySSL=<bool>]
                        [--project=<prj>]
                        [--repo=<repo>]
                        [--recurse]
                        [--noRecurse]
                        [--noRecurseSubprojects]
                        [--skipSubproject=<project>...]
                        [--test]
                        [--prepend | --append]
                        [--subprojectsOnly]
                        [--ssh_pat_url=<url>]
                        [--ssh_pat_port=<int>]
                        [--noLocal | --pushModifiedOnly]
                        [--label_ref=<ref>]
                        [--skiplabels]

    Options:
        --update                    Update an existing pull request with a new description, set of reviewers, etc.
                                    This is the default behavior if a pull request already exists for <topicBranch>
                                    targeting <publicBranch>. If --update is set, and an open pull request doesn't
                                    exist, an error will be generated.
        --add                       Add a new pull request. Default behavior if a pull request doesn't exist for
                                    <topicBranch> targeting <publicBranch>. If a pull request already exists and --add
                                    is set, an error will be generated.
        --draft                     Mark pull request as draft.
        --ready                     Mark pull request as ready (not draft).
        --title=<title>             The pull request`s title.
        --descr=<file>              A file containing the detailed description of work done on <topicBranch>.
        -m <description>            The pull request description.
        --user=<userName>           Your Bitbucket user name.
        --reviewers=<groups>        A whitespace-separated list of reviewer groups, where each reviewer group is a comma-separated list of reviewers for <topicBranch>, optionally preceded by a rule name and colon.
        --source=<topicBranch>      The branch to review. Defaults to current branch.
        --target=<publicBranch>     The branch to publish <topicBranch> to.
                                    Defaults to .grapeconfig.topicPrefixMappings[topicBranchPrefix].
        --state=<state>             The state of the pull request to update. Valid values are open, merged, and
                                    declined.
                                    [default: open]
        --codeReviewsURL=<url>      The code review platform url, e.g. https://your.host.org/gitlab. Grape supports
                                    both Bitbucket and Gitlab code review platforms.
                                    [default: .grapeconfig.project.codeReviewsURL]
        --verifySSL=<bool>          Set to False to ignore SSL certificate verification issues.
                                    [default: .grapeconfig.project.verifySSL]
        --project=<prj>             The project key part of the codeReviews url, e.g. the "GRP" in
                                    https://your.host.org/gitlab/or/bitbucket/projects/GRP/repos/grape/browse.
                                    [default: .grapeconfig.project.name]
        --repo=<repo>               The repo name part of the codeReviews url, e.g. the "grape" in
                                    https://your.host.org/gitlab/or/bitbucket/projects/GRP/repos/grape/browse.
                                    [default: .grapeconfig.repo.name]
        --recurse                   If set, adds a pull request for each modified submodule.
                                    The pull request for the outer level repo will have a description with links to the
                                    submodules' pull requests. On by default if grapeConfig.workspace.manageSubmodules
                                    is set to true.
        --noRecurse                 Disables adding pull requests to submodules.
        --noRecurseSubprojects      Disables adding pull requests to nested subprojects.
        --skipSubproject=<project>  Nested subproject to skip for review (submodules cannot be skipped). Can be defined multiple times.
        --test                      Uses a dummy version of stashy that requires no communication to an actual Bitbucket
                                    server.
        --prepend                   Prepend <title> to the existing title instead of replacing it.
        --append                    Append <title> to the existing title instead of replacing it.
        --subprojectsOnly           As a work around to when you've only touched a subproject, this will prevent errors
                                    arising in the top level repo.
        --ssh_pat_url=<url>         SSH URL for generating Personal Access Tokens to authenticate into a Code Review service's
                                    REST API.
                                    [default: .grapeconfig.repo.ssh_pat_url]
        --ssh_pat_port=<int>        Port number to issue ssh command over to generate a Personal Access Token for authentication
                                    into a Code Review service's REST API.
                                    [default: .grapeconfig.repo.ssh_pat_port]
        --noLocal                   Do not perform any pushes of the topic branch or any git operations relying on the existence
                                    of the local branch in the local workspace. Branches must still exist on the codeReviews
                                    (Bitbucket, Gitlab) server.
        --pushModifiedOnly          Only push in repos that are modified (compared to the public branch).
                                    By default, the entire local workspace will be pushed to ensure consistency.
                                    In either case, --recurse/--noRecurse/--noRecurseSubprojects arguments are respected.
        --label_ref=<ref>           Reference SHA or branch to use for changedfilelabelmapping. This may be useful to set to a
                                    the merged result SHA to reflect the merged result diff. Defaults to current (source) branch.
        --skiplabels                Skip labeling based on changedfilelabelmapping.


    """
    def __init__(self):
        super(Review, self).__init__()
        self._key = "review"
        self._section = "Code Reviews"

    def description(self):
        return "Prepare current topic branch for review"

    def parseDescriptionArgs(self, args):
        descr = args["-m"]
        if not descr:
            descrFile = args["--descr"]
            if descrFile:
                with io.open(descrFile) as f:
                    descr = f.readlines()
                descr = ''.join(descr)
                for encoding in ['utf-8', 'windows-1252']:
                    try:
                        descr = descr.decode(encoding).encode('ascii','ignore')
                    except:
                        pass
        else:
            # Convert \n to a newline, but only if it is not escaped
            # (alternation allows newline on separate line)
            descr = re.sub(r'([^\\]|)\\n', r'\1\n', descr)

            # Remove one backslash from any escaped \n's.
            descr = re.sub(r'\\\\n', r'\\n', descr)

        return descr


    def validateReviewers(self, reviewers, reviewRules):
        """
        Validates the provided reviewers against defined review rules.

        This function checks if the specified reviewers are valid according to the review rules,
        ensuring that each reviewer is eligible and that the minimum number of reviewers is met.

        Parameters:
        ----------
        reviewers : dict
            A dictionary where each key is a review rule name and each value is a dictionary containing:
                - 'reviewers': A list of reviewers assigned to that rule.

        reviewRules : dict
            A dictionary where each key is a review rule name and each value is a ReviewRule

        Returns:
        -------
        None
            The function does not return a value. It logs errors and warnings as necessary and exits
            the program if validation fails.

        Notes:
        -----
        - The function uses regular expression matching to determine if each reviewer is eligible.
        """
        for reviewRuleName in reviewers:
            # Check the given rule name is a review rule
            if reviewRuleName not in reviewRules or not reviewRules[reviewRuleName].active:
                logging.error(f'GRAPE: ERROR: "{reviewRuleName}" is not an active review rule.')
                exit(1)

            reviewGroup = reviewers[reviewRuleName]
            reviewRule = reviewRules[reviewRuleName]

            # Check that the reviewers are allowed to approve this rule
            reviewRuleReviewers = reviewGroup['reviewers']

            for reviewRuleReviewer in reviewRuleReviewers:
                if not reviewRule.matches_reviewer(reviewRuleReviewer):
                    logging.error(f'GRAPE: ERROR: "{reviewRuleReviewer}" is not an eligible reviewer for review rule "{reviewRuleName}".')
                    exit(1)

            # Check if the minimum number of reviewers has been met
            numReviewers = len(reviewRuleReviewers)
            minNumReviewers = reviewRule.minNumReviewers

            if numReviewers < minNumReviewers:
                logging.warning(f'GRAPE: WARNING: {minNumReviewers} reviewer(s) required for review rule "{reviewRuleName}", but only {numReviewers} reviewer(s) given.')

        return


    def serializeReviewers(self, reviewers):
        """
        Serializes a dictionary of reviewers into a formatted string.

        This function takes a dictionary where each key represents a review rule name,
        and the associated value is another dictionary containing a list of reviewers.
        It constructs a string representation of the reviewers grouped by their review rule names.

        Parameters:
        ----------
        reviewers : dict
            A dictionary where each key is a review rule name (str) and each value is a dictionary
            containing:
                - 'reviewers': A list of reviewer names (str) associated with the review rule.

        Returns:
        -------
        str or None
            A string representing the serialized reviewers in the format:
            "reviewRuleName:reviewer1,reviewer2,..." for each review rule with reviewers.
            If there are no reviewers or the input dictionary is empty, returns None.

        Example:
        --------
        reviewers = {
            'code': {
                'reviewers': ['Alice', 'Bob']
            },
            'documentation': {
                'reviewers': ['Charlie']
            }
        }

        result = serializeReviewers(reviewers)
        # result would be: "code:Alice,Bob documentation:Charlie"

        Notes:
        -----
        - If a review rule has no reviewers, it will be skipped in the output.
        - If the input `reviewers` dictionary is empty or None, or all the review rules have no reviewers, the function will return None.
        """
        if reviewers:
            serializedReviewGroups = []

            for reviewRuleName in reviewers:
                reviewerGroup = reviewers[reviewRuleName]
                reviewRuleReviewers = reviewerGroup['reviewers']

                if reviewRuleReviewers:
                    if len(reviewers) == 1:
                        serializedReviewGroups.append(f'{",".join(reviewRuleReviewers)}')
                    else:
                        serializedReviewGroups.append(f'{reviewRuleName}:{",".join(reviewRuleReviewers)}')

            if serializedReviewGroups:
                return ' '.join(serializedReviewGroups)
            else:
                return None
        else:
            return None


    def getApplicableReviewers(self, repoName, allReviewers, reviewRules):
        """
        Retrieves applicable reviewers for a given repository based on defined review rules.

        This function checks the provided review rules against the specified repository name
        and returns a dictionary of reviewers that are applicable for that repository.

        Parameters:
        ----------
        repoName : str
            The name of the repository for which applicable reviewers are to be retrieved.

        allReviewers : dict
            A dictionary where each key is a review rule name and each value is a dictionary
            containing a list of reviewers associated with that rule.

        reviewRules : dict
            A dictionary where each key is a review rule name and each value is another dictionary
            containing:
                - 'repositories': A list of repository patterns (str) that the rule applies to.

        Returns:
        -------
        dict
            A dictionary where each key is a review rule name and each value is a dictionary
            containing a list of applicable reviewers for that rule. If no applicable reviewers are found, an empty dictionary is returned.

        Example:
        --------
        repoName = 'example-repo'
        allReviewers = {
            'code': {'label': 'Code Review', 'reviewers': ['Alice', 'Bob']},
            'documentation': {'label': 'Documentation Review', 'reviewers': ['Charlie']}
        }
        reviewRules = {
            'code': {
                'repositories': ['example-repo', 'another-repo']
            },
            'documentation': {
                'repositories': ['example-docs']
            }
        }

        result = self.getApplicableReviewers(repoName, allReviewers, reviewRules)
        # result would be: {'code': {'label': 'Code Review', 'reviewers': ['Alice', 'Bob']}}

        Notes:
        -----
        - The function uses regular expression matching to determine if the repository name matches
          any of the patterns defined in the review rules.
        - If no review rules match the given repository name, the function will return an empty dictionary.
        """
        applicableReviewers = {}

        for reviewRuleName in allReviewers:
            reviewRule = reviewRules[reviewRuleName]

            if reviewRule.matches_repository(repoName):
                applicableReviewers[reviewRuleName] = allReviewers[reviewRuleName]

        return applicableReviewers

    @staticmethod
    def _get_top_repo_context(git_host, user_name, project_name, repo_name, source_branch, target_branch):
        """
        Build and validate the top-level repository context needed for reviews/approvals.

        This resolves the project/repo and target branch, loads the `.grapeconfig` from the source
        branch, and returns a context dictionary used by downstream review/approval logic.

        Parameters
        ----------
        git_host : CodeReviews
            Authenticated code review / git hosting client.
        user_name : str
            Username for git host client
        project : str
            Name of project/group containing repository
        repo : str
            Name of repository
        source : str
            Name of source branch
        target : str
            Name of target branch (if None, defaults via .grapeconfig mapping)

        Returns
        -------
        dict
            Context containing:
            - project_name
            - repo_name
            - repo
            - source_branch
            - target_branch
            - grape_config (GrapeConfigParserBase)

        Exits
        -----
        Terminates the process with exit code 1 if:
        - source branch does not exist
        - `.grapeconfig` is missing on the source branch
        """

        repo = git_host.repo(project_name, repo_name)

        # Get grape config
        try:
            grapeconfig = repo.getFile('.grapeconfig', source_branch)
        except Exception as e:
            if e.response_code == 404:
                if e.error_message == '404 Commit Not Found':
                    logging.error(f'GRAPE: ERROR: Source branch "{source_branch}" does not exist in "{project_name}/{repo_name}"')
                    exit(1)
                elif e.error_message == '404 File Not Found':
                    logging.error(f'GRAPE: ERROR: File ".grapeconfig" does not exist on source branch "{source_branch}" in "{project_name}/{repo_name}"')
                    exit(1)

            raise

        config = config_parser_base.GrapeConfigParserBase(workspaceDir=None, configString=grapeconfig)

        if not target_branch:
            target_branch = config.getPublicBranchFor(source_branch)

        # Get review request
        review_request = repo.getOpenPullRequest(source_branch, target_branch)

        return {
            'project_name': project_name,
            'repo_name': repo_name,
            'repo': repo,
            'review_request': review_request,
            'source_branch': source_branch,
            'target_branch': target_branch,
            'grape_config': config
        }

    @staticmethod
    def _get_modified_repos(git_host, top_repo_context):
        """
        Determine which repositories have changes between the source and target branches.

        This builds and returns a dictionary of repository context objects for all
        repositories that have a merge/pull request:
          - the top-level repository (via `_add_top_repo_if_modified`)
          - modified submodules (via `_add_modified_submodules`)
          - modified nested subprojects (via `_add_modified_subprojects`)

        Parameters
        ----------
        git_host : CodeReviews
            Authenticated code review / git hosting client used to access repos.
        top_repo_context : dict
            Context dictionary returned by `_get_top_repo_context`.

        Returns
        -------
        dict
            Mapping of repo_name -> repo_context for each repository detected as
            modified relative to the target branch.
        """
        logging.info(f'Getting modified repositories...')

        modified_repos = {}

        Review._add_top_repo_if_modified(top_repo_context, modified_repos)
        Review._add_modified_submodules(git_host, top_repo_context, modified_repos)
        Review._add_modified_subprojects(git_host, top_repo_context, modified_repos)

        return modified_repos

    @staticmethod
    def _add_top_repo_if_modified(top_repo_context, modified_repos):
        """
        Add the top-level repository to the modified repos map if it has an open review request.

        If an open review request exists, the top repository context is added to `modified_repos`
        keyed by the repo name.

        Parameters
        ----------
        top_repo_context : dict
            Context dictionary returned by `_get_top_repo_context`, expected to include:
              - "repo_name": str
              - "review_request": review request | None
        modified_repos : dict
            Mapping of repo_name -> repo_context that will be updated in-place.

        Side Effects
        ------------
        Mutates `modified_repos` by adding an entry for the top repository when applicable.
        """
        if top_repo_context['review_request']:
            modified_repos[top_repo_context['repo_name']] = top_repo_context

    @staticmethod
    def _add_modified_submodules(git_host, top_repo_context, modified_repos):
        """
        Add modified submodules (with open review requests) to the modified repos map.

        This inspects the top repository's `.gitmodules` file on the source branch,
        parses submodule definitions, derives the corresponding target branch for
        submodules using the workspace mapping `submoduleTopicPrefixMappings` from
        the repository's `.grapeconfig`, and then checks each submodule repository
        for an open merge/pull request from source -> target.

        Submodules meeting this criterion are added to `modified_repos` keyed by
        repository name.

        Parameters
        ----------
        git_host : CodeReviews
            Authenticated code review / git hosting client.
        top_repo_context : dict
            Context dictionary for the top-level repository, expected to include:
              - "project_name": str
              - "repo": repository client for the top repo
              - "source_branch": str
              - "grape_config": config_parser_base.GrapeConfigParserBase
        modified_repos : dict
            Mapping of repo_name -> repo_context that will be updated in-place.

        Side Effects
        ------------
        Mutates `modified_repos` by adding entries for modified submodule repositories.

        Notes
        -----
        This method returns early when `.gitmodules` is missing or contains no
        submodule definitions.
        """
        # TODO: Investigate approach using top level merge request diffs if available
        top_repo = top_repo_context['repo']
        top_source_branch = top_repo_context['source_branch']

        gitmodules = top_repo.getFile(".gitmodules", top_source_branch)

        if not gitmodules:
            return

        submodules_metadata = submodules.parse_gitmodules(gitmodules.splitlines())

        if not submodules_metadata:
            return

        submodule_source_branch = top_source_branch

        config = top_repo_context['grape_config']
        submodule_branch_mappings = config.getMapping(Review.SECTION_WORKSPACE, 'submoduleTopicPrefixMappings')
        source_branch_prefix = git.branchPrefix(submodule_source_branch)
        submodule_target_branch = submodule_branch_mappings[source_branch_prefix]

        top_project_name = top_repo_context['project_name']

        # Checking top-level diffs for modified submodules is generally faster
        # than querying GitLab for each submodule repository and merge request.
        top_review_request = top_repo_context['review_request']

        if top_review_request:
            submodule_path_to_url_map = {submodule['path']: submodule['url'] for submodule in submodules_metadata.values()}

            top_diffs = top_review_request.diffs()

            for diff in top_diffs:
                new_path = diff.get('new_path')
                url = submodule_path_to_url_map.get(new_path)

                if url:
                    modified_repo_context = Review._get_modified_repo_context(
                        git_host, top_project_name, submodule_source_branch, submodule_target_branch, url
                    )

                    if modified_repo_context:
                        modified_repos[modified_repo_context['repo_name']] = modified_repo_context

        else:
            for submodule_name in submodules_metadata:
                submodule_metadata = submodules_metadata[submodule_name]
                # TODO: Check url matches the top level git service
                url = submodule_metadata['url']

                modified_repo_context = Review._get_modified_repo_context(
                    git_host, top_project_name, submodule_source_branch, submodule_target_branch, url
                )

                if modified_repo_context:
                    modified_repos[modified_repo_context['repo_name']] = modified_repo_context

    @staticmethod
    def _add_modified_subprojects(git_host, top_repo_context, modified_repos):
        """
        Add nested subprojects with changes and open review requests to the modified repos map.

        Iterates all nested subprojects defined in the top repository's `.grapeconfig`,
        resolves each subproject URL, and uses `_get_modified_repo_context` to determine
        whether the subproject has an open merge/pull request from source -> target.

        When a subproject meets this criterion, its repo context is added to
        `modified_repos` keyed by repo name.

        Parameters
        ----------
        git_host : CodeReviews
            Authenticated code review / git hosting client.
        top_repo_context : dict
            Context dictionary for the top-level repository, expected to include:
              - "project_name"
              - "source_branch"
              - "target_branch"
              - "grape_config"
        modified_repos : dict
            Mapping of repo_name -> repo_context that will be updated in-place.

        Side Effects
        ------------
        Mutates `modified_repos` by adding entries for modified nested subprojects.
        """
        top_project_name = top_repo_context['project_name']
        subproject_source_branch = top_repo_context['source_branch']
        subproject_target_branch = top_repo_context['target_branch']

        config = top_repo_context['grape_config']
        subprojects = config.getAllNestedSubprojects()

        for subproject in subprojects:
            url = config.get(f'nested-{subproject}', 'url')
            modified_repo_context = Review._get_modified_repo_context(
                git_host, top_project_name, subproject_source_branch, subproject_target_branch, url
            )

            if modified_repo_context:
                modified_repos[modified_repo_context['repo_name']] = modified_repo_context

    @staticmethod
    def _get_modified_repo_context(git_host, top_project_name, source_branch, target_branch, url):
        """
        Build repository context for a nested repo (submodule/subproject) if it has an open review request.

        This resolves the repository's project/name from the given repository URL and locates an
        open merge/pull request from `source_branch` into `target_branch` if it exists.

        Parameters
        ----------
        git_host : CodeReviews
            Authenticated code review / git hosting client.
        top_project_name : str
            Project/group name of the top-level repository. Used when the URL specifies a relative project ("..").
        source_branch : str
            Source/topic branch name to compare and to locate an open merge/pull request for.
        target_branch : str
            Target/public branch name to compare against and to locate an open merge/pull request into.
        url : str
            Repository URL (typically from .gitmodules or nested subproject config). Expected to end with `<repo>.git`
            optionally, and to include the project/group segment immediately before the repo segment.
        Returns
        -------
        dict | None
            When an open merge/pull request exists from source -> target returns a repo context dict containing:
              - project_name
              - repo_name
              - repo
              - review_request

            Otherwise returns None.
        """
        # Get project and repo
        components = url.split('/')

        project_name = components[-2]

        if project_name == '..':
            # Same as top level project
            project_name = top_project_name

        repo_name = components[-1]
        repo_name = repo_name[:-4] if repo_name.endswith('.git') else repo_name

        repo = git_host.repo(project_name, repo_name)

        # Get merge/pull request
        review_request = repo.getOpenPullRequest(source_branch, target_branch)

        if not review_request:
            return None

        return {
            'project_name': project_name,
            'repo_name': repo_name,
            'repo': repo,
            'review_request': review_request
        }

    @log_wrapper
    def execute(self, args):
        """
        A fair chunk of this stuff relies on stashy's wrapping of the STASH REST API, which is posted at
        https://developer.atlassian.com/static/rest/stash/2.12.1/stash-rest.html
        """
        config = config_parser_global.grapeConfig()
        name = utility.getUserName(args)
        logging.info(f"Logging onto {args['--codeReviewsURL']}")
        if args["--test"]:
            codeReviews = Atlassian.TestAtlassian(name)
        else:
            verify = True if args["--verifySSL"].lower() == "true" else False
            codeReviews = CodeReviewsFactory.makeCodeReviews(name, url=args["--codeReviewsURL"],
                                                verify=verify,
                                                port=int(args["--ssh_pat_port"]),
                                                ssh_path = args["--ssh_pat_url"],
                                                workspace_dir=self.workspace_dir
                                                )
        # default project (outer level project)
        project_name = args["--project"]

        # default repo (outer level repo)
        repo_name = args["--repo"]

        # determine source branch and target branch
        branch = args["--source"]
        if not branch:
            branch = git.currentBranch(execution_path=self.workspace_dir)

        #ensure branch is pushed
        if "--noLocal" not in args or not args["--noLocal"]:
            logging.info(f"Pushing {branch} to {codeReviews.url}...")
            git.push(f"origin {branch}", execution_path=self.workspace_dir)
        
        #target branch for outer level repo
        target_branch = args["--target"]
        if not target_branch:
            target_branch = config.getPublicBranchFor(branch)
        # load pull request if it already exists
        wsRepo =  codeReviews.repo(project_name, repo_name)
        existingOuterLevelRequest = getReposPullRequest(wsRepo, branch, target_branch, args)

        # determine pull request title
        title = args["--title"]
        if existingOuterLevelRequest is not None and not title:
            title = existingOuterLevelRequest.title()

        # determine draft status
        wip = None
        if args['--draft']:
            wip = True
        elif args['--ready']:
            wip = False

        #determine pull request URL
        outerLevelURL = None

        if existingOuterLevelRequest:
            outerLevelURL = existingOuterLevelRequest.link()

        # Get review rules
        reviewRuleManager = ReviewRuleManager.from_config()
        reviewRules = reviewRuleManager.reviewRules
        defaultReviewRule = reviewRuleManager.get_rule('')

        # determine pull request description
        descr = self.parseDescriptionArgs(args)

        if not descr and existingOuterLevelRequest:
            descr = existingOuterLevelRequest.description()

        descriptionModel = PullRequestDescriptionModel.from_text(descr, reviewRuleManager)

        # Determine merge/pull request reviewers
        reviewers = {}

        if existingOuterLevelRequest and existingOuterLevelRequest.reviewers():
            reviewers[defaultReviewRule.name] = {
                'label': reviewRules[defaultReviewRule.name].label,
                'reviewers': [r[0] for r in existingOuterLevelRequest.reviewers()]
            }

        non_approvers = config_parser_global.grapeConfig().get(self.SECTION_REVIEW, "non_approvers")

        non_approver_list = set()
        if non_approvers:
            if len(non_approvers.split()) > 1:
                logging.warning(f'GRAPE: WARNING: {self.SECTION_REVIEW}.non_approvers should be comma-delimited. Ignoring...')
            else:
                non_approver_list.update(non_approvers.lower().split(','))

        savedReviewers = ''
        reviewRuleModels = descriptionModel.reviewRules

        for reviewRuleLabel in reviewRuleModels:
            reviewRuleModel = reviewRuleModels[reviewRuleLabel]
            temp = ','.join(sorted(reviewRuleModel['reviewers']))

            for reviewRuleName in reviewRules:
                reviewRule = reviewRules[reviewRuleName]

                if reviewRule.label == reviewRuleLabel:
                    savedReviewers += f' {reviewRule.name}:{temp}'

        savedArgs = {'--reviewers': savedReviewers.strip()}

        reviewers.update(parseReviewers(savedArgs, reviewRuleManager))
        reviewers.update(parseReviewers(args, reviewRuleManager))
        self.validateReviewers(reviewers, reviewRules)

        # Update review rule reviewers
        if reviewers:
            for ruleName in reviewers:
                ruleInfo = reviewers[ruleName]
                ruleLabel = ruleInfo['label']
                assignedReviewers = ruleInfo['reviewers']

                if assignedReviewers:
                    # Add or update reviewers for  rule
                    if ruleLabel not in reviewRuleModels:
                        reviewRuleModels[ruleLabel] = {
                            'reviewers': set(assignedReviewers),
                            'approvals': {}
                        }
                    else:
                        reviewRuleModels[ruleLabel]['reviewers'] = set(assignedReviewers)
                else:
                    # Check if review rule model needs to be removed
                    # (i.e. no reviewers or approvals).
                    if ruleLabel in reviewRuleModels:
                        if not reviewRuleModels[ruleLabel]['approvals']:
                            del reviewRuleModels[ruleLabel]

        # Add inactive rules with empty reviewer lists in order to delete any
        # outdated approval rules.
        if reviewers:
            for reviewRuleName in reviewRules:
                if not reviewRules[reviewRuleName].active:
                    reviewers[reviewRuleName] = {
                        'label': reviewRules[reviewRuleName].label,
                        'reviewers': []
                    }

        # Store reviewers in args so that it can be added later to the
        # merge/pull request description.
        args['--reviewers'] = self.serializeReviewers(reviewers)

        # Add top level link to related reviews
        descriptionModel.add_related_pull_request(outerLevelURL)

        # Update description
        updatedDescription = descriptionModel.to_text()

        # if we're in append mode, only append what was asked for:
        if args["--append"] or args["--prepend"]:
            title = args["--title"]

        logging.info(f"Updating remote tracking branches for {target_branch}...")

        # Fetch the remote tracking branch for the target branch
        git.fetch(f"origin {target_branch}", execution_path=self.workspace_dir)
        # Skip fetching of remote tracking branch in submodules if no gitlink changes were fetched
        if "--noLocal" in args and args["--noLocal"]:
           submodulesModifiedInOrigin = False
        else:
           submodulesModifiedInOrigin = git.getModifiedSubmodules(self.workspace_dir, "origin/"+target_branch, target_branch)
                     
        upArgs = ['up', f'--public={target_branch}', '--updateRemoteOnly']
        if not submodulesModifiedInOrigin:
           upArgs.extend(['--noRecurse', '--recurseSubprojects'])

        upToDate = grapeMenu.menu().applyMenuChoice('up', upArgs)
        if not upToDate:
            logging.info("Failed to update local branches.")
            return False

        runInSubmodules = not args["--noRecurse"] and (args["--recurse"] or config.getboolean(self.SECTION_WORKSPACE, "manageSubmodules"))

        # assemble arguments for parallel execution of code reviews
        listOfRepoBranchArgTuples=[]

        ##  Submodule Repos
        if runInSubmodules:
            activeSubmodules = git.getActiveSubmodules(execution_path=self.workspace_dir)
            url_map = git.getAllSubmoduleURLMap(execution_path=self.workspace_dir)
            modifiedSubmodules = git.getModifiedSubmodules(self.workspace_dir, target_branch, branch, includeAdded=True)

            # update target branch based off of branch prefix
            submoduleBranchMappings = config.getMapping(self.SECTION_WORKSPACE, "submoduleTopicPrefixMappings")

            # determine branch prefix
            prefix = git.branchPrefix(branch)
            sub_target_branch = submoduleBranchMappings[prefix]

            for submodule in modifiedSubmodules:
                if not submodule:
                    continue
                changed = False
                if submodule in activeSubmodules:
                    if git.log(f"--oneline origin/{sub_target_branch}..{branch}", execution_path=os.path.join(self.workspace_dir, submodule)):
                        changed = True
                else:
                    url = url_map[submodule]
                    targetHead = f"refs/heads/{sub_target_branch}"
                    branchHead = f"refs/heads/{branch}"
                    remotes = git.lsRemote(f"--heads {git.parseSubprojectRemoteURL(url, execution_path=self.workspace_dir)} {targetHead} {branchHead}", execution_path=self.workspace_dir)
                    targetSHA = None
                    branchSHA = None
        
                    for entry in remotes.splitlines():
                       if entry:
                          SHA_and_ref = entry.split()
                          if SHA_and_ref[1] == targetHead:
                             targetSHA = SHA_and_ref[0]
                          elif SHA_and_ref[1] == branchHead:
                             branchSHA = SHA_and_ref[0]
                          if branchSHA and targetSHA:
                             break
                    if targetSHA and branchSHA and targetSHA != branchSHA:
                       changed = True 

                if changed:
                    submoduleReviewers = self.getApplicableReviewers(submodule, reviewers, reviewRules)

                    listOfRepoBranchArgTuples.append((submodule,branch,[{"codeReviews":codeReviews,
                                                                         "isSubmodule": True,
                                                                         "isNested": False,
                                                                         "args": args,
                                                                         "target_branch": sub_target_branch,
                                                                         "descr": updatedDescription,
                                                                         "title": title,
                                                                         "proj": submodule,
                                                                         "outerLevelURL": outerLevelURL,
                                                                         "reviewers": submoduleReviewers,
                                                                         "non_approver_list" : non_approver_list,
                                                                         "wip" : wip,
                                                                         "active": submodule in activeSubmodules }]))

        ## NESTED SUBPROJECT REPOS
        if not args["--noRecurseSubprojects"]:
           activeNestedSubprojects = config_parser_user.getAllActiveNestedSubprojects(workspaceDir=self.workspace_dir)
           nestedProjects = config_parser_user.getAllModifiedNestedSubprojects(
               "origin/"+target_branch, now=branch, workspaceDir=self.workspace_dir, checkRemote=True, skippedRepos=args["--skipSubproject"])
           nestedProjectPrefixes = [config.get(f"nested-{name}", "prefix") for name in nestedProjects]

           for proj, prefix in zip(nestedProjects, nestedProjectPrefixes):
               subprojectReviewers = self.getApplicableReviewers(proj, reviewers, reviewRules)

               prefix_path = os.path.join(self.workspace_dir, prefix)
               listOfRepoBranchArgTuples.append((prefix_path,branch,[{"codeReviews":codeReviews,
                                                                    "isSubmodule": False,
                                                                    "isNested": True,
                                                                    "args": args,
                                                                    "target_branch": target_branch,
                                                                    "descr": updatedDescription,
                                                                    "title": title,
                                                                    "proj": proj,
                                                                    "outerLevelURL": outerLevelURL,
                                                                    "reviewers": subprojectReviewers,
                                                                    "non_approver_list" : non_approver_list,
                                                                    "wip" : wip,
                                                                    "active": proj in activeNestedSubprojects}]))

        launcher = multi_repo_cmd_launcher.MultiRepoCommandLauncher(PostPullRequestForRepo, listOfRepoBranchArgTuples=listOfRepoBranchArgTuples, workspace_dir=self.workspace_dir)
        pullRequestLinks = launcher.launchFromWorkspaceDir(noPause=True, handleMRE=HandlePostPullRequestForRepoMRE)

        ## OUTER LEVEL REPO
        # load the repo level REST resource
        if not args["--subprojectsOnly"]:
            if "--noLocal" in args and args["--noLocal"]:
                pass
            else:
                if not git.hasBranch(branch, execution_path=self.workspace_dir):
                    logging.info(
                        f"Top level repository does not have a branch {branch}," +
                        " not generating a Pull Request")
                    return True
                if git.branchUpToDateWith(target_branch, branch, execution_path=self.workspace_dir):
                    logging.info(
                        f"{target_branch} up to date with {branch}," +
                        " not generating a Pull Request in Top Level repo")
                    return True
                if not git.log(f"--oneline origin/{target_branch}..{branch}", execution_path=self.workspace_dir):
                    logging.info(
                        f"{branch} is in the history of {target_branch}," +
                        " not generating a Pull Request in Top Level repo")
                    return True

            add_labels = []
            remove_labels = []
            if not args["--skiplabels"]:
               try:
                  changedfilelabelmapping = config.getMapping(self.SECTION_REVIEW, "changedfilelabelmapping")
                  if changedfilelabelmapping:
                      label_ref = args["--label_ref"]
                      if not label_ref:
                          label_ref = branch
                      # find the common ancestor between the reference for labels and the target branch
                      mergeBase = git.mergeBase(f"{target_branch} {label_ref}", execution_path=self.workspace_dir)
                      for path,label in changedfilelabelmapping.items():
                          try:
                             # check if the file has changes from the ancestor
                             if git.diff(f"--name-only {label_ref} {mergeBase} {path}", execution_path=self.workspace_dir):
                                 add_labels.append(label)
                             else:
                                 remove_labels.append(label)
                          except grape_errors.GrapeGitError:
                             logging.warning(f"GRAPE: WARNING: .grapeconfig [review] changedfilelabelmapping, '{path}' not found, ignoring...")
               except NoSectionError:
                  pass
               except NoOptionError:
                  pass

            repo_name = args["--repo"]
            repo = CodeReviewsFactory.repoObject(codeReviews, repoName=repo_name, projectName=project_name)
            logging.info(f"Posting pull request to {project_name},{repo_name}")

            outerReviewers = self.getApplicableReviewers(repo_name, reviewers, reviewRules)

            request = postPullRequest(repo, title, branch, target_branch, updatedDescription, outerReviewers, args, self.workspace_dir, non_approver_list=non_approver_list, wip=wip, add_labels=add_labels, remove_labels=remove_labels)

            # Update related reviews
            outerLevelURL = request.link()

            if runInSubmodules and not args["--noRecurseSubprojects"]:
                # Ignore related review links scraped from the outer level
                # merge/pull request description. Then add all the new
                # submodule/subproject links. Only add the outer level link
                # if there are any submodule/subproject links.
                descriptionModel.clear_related_pull_requests()
                descriptionModel.add_related_pull_request(outerLevelURL)

                for link in pullRequestLinks:
                    descriptionModel.add_related_pull_request(link)
            else:
                # Start with related review links scraped from the outer level
                # merge/pull request description. Then add all the new links if
                # they are not already in the list.
                descriptionModel.add_related_pull_request(outerLevelURL)

                for link in pullRequestLinks:
                    descriptionModel.add_related_pull_request(link)

            updatedDescription = descriptionModel.to_text()
            pre_update_description = request.description()

            if updatedDescription != pre_update_description:
                request = postPullRequest(repo, title, branch, target_branch,
                                          updatedDescription,
                                          outerReviewers,
                                          args,
                                          self.workspace_dir,
                                          non_approver_list=non_approver_list, wip=wip,
                                          add_labels=add_labels, remove_labels=remove_labels)

            logging.debug(f"Request generated/updated:\n\n{request}")

        if ("--pushModifiedOnly" not in args or not args["--pushModifiedOnly"]) and ("--noLocal" not in args or not args["--noLocal"]):
            logging.info(f"Pushing {branch} from workspace (use --pushModifiedOnly/--noLocal to skip this step)...")
            
            # top level was already pushed at the beginning
            pushArgs = ['push', '--noTopLevel']
            if not runInSubmodules:
                pushArgs.append('--noRecurse')
            if args["--noRecurseSubprojects"]:
                pushArgs.append('--noRecurseSubprojects')

            pushed = grapeMenu.menu().applyMenuChoice("push", pushArgs)
            if not pushed:
                return False
        return True


    def setDefaultConfig(self, config):
        config.ensureSection(self.SECTION_PROJECT)
        config.set(self.SECTION_PROJECT, "codeReviewsURL", "https://your.host.org/gitlab/or/bitbucket")
        config.set(self.SECTION_PROJECT, "verifySSL", "True")
        config.set(self.SECTION_PROJECT, "name", "My unnamed project")
        config.set(self.SECTION_REPO, "ssh_pat_url", "git@gitlab.your.host.org")
        config.set(self.SECTION_REPO, "ssh_pat_port", "7999")
        config.ensureSection(self.SECTION_REVIEW)
        config.set(self.SECTION_REVIEW, "non_approvers", "gitlabduo")


def MRLinkText():
    return "This merge request is related to the merge request at: "


def HandlePostPullRequestForRepoMRE(mre):
    for e, repo, branch in zip(mre.exceptions(), mre.repos(), mre.branches()):
        raise e


def PostPullRequestForRepo(repo, branch, args, *, workspace_dir):
    kwargs = args[0]
    codeReviews = kwargs["codeReviews"]
    isSubmodule = kwargs["isSubmodule"]
    isNested = kwargs["isNested"]
    review_args = kwargs["args"]
    target_branch = kwargs["target_branch"]
    descr = kwargs["descr"]
    title = kwargs["title"]
    proj = kwargs["proj"]
    outerLevelURL = kwargs["outerLevelURL"]
    reviewers = kwargs["reviewers"]
    non_approver_list  = kwargs["non_approver_list"]
    wip = kwargs["wip"]
    active = kwargs["active"]

    # push branch
    if active and ("--noLocal" not in review_args or ("--noLocal" in review_args and not review_args["--noLocal"])):
        logging.info(f"Pushing {branch} to {codeReviews.url} in {repo}")
        git.push(f"origin {branch}", execution_path=repo)

    if isNested:
        codeReview_repo = CodeReviewsFactory.repoFromNestedSubprojectName(codeReviews, proj)
    elif isSubmodule:
        codeReview_repo = CodeReviewsFactory.repoFromSubmodulePath(codeReviews, proj)
    else:
        codeReview_repo = CodeReviewsFactory.repoObject(codeReviews)

    newRequest = postPullRequest(codeReview_repo, title, branch, target_branch, descr, reviewers,
                                 review_args, repo, non_approver_list=non_approver_list, wip=wip)
    if newRequest:
        return newRequest.link()
    else:
        return ""


def getReposPullRequest(repo, branch, target_branch, args):
    pull_requests = repo.pullRequests(direction="OUTGOING", at=f"refs/heads/{branch}", state=args["--state"])
    # check to see if pull request already exists for this branch
    request = None
    for rqst in pull_requests:
        if rqst.toRef() == target_branch and rqst.fromRef() == branch:
            request = rqst
            break
    return request


def pullRequestAlreadyMerged(errorMessage):
    if "already up-to-date with branch" in errorMessage or \
            "This pull request has already been merged" in errorMessage:
        return True
    return False


def targetBranchMissing(errorMessage):
    if "Repository" in errorMessage and "of project with key" in errorMessage and "has no branch" in errorMessage:
        return True
    return False


def postPullRequest(repo, title, branch, target_branch, descr, reviewers, args, git_execution_path,
                    non_approver_list=[], wip=None, add_labels=[], remove_labels=[]):
    config = config_parser_global.grapeConfig()
    repo_name = repo.project.name


    # get the open pull requests outgoing from our public branch
    logging.info(f"Gathering active pull requests on {branch} for repo {args['--repo']}")
    request = getReposPullRequest(repo, branch, target_branch, args)

    if not request:
        if not args["--update"]:
            # add a new pull request
            if not title:
                title = branch
            try:
                logging.info(
                    f"Creating new pull request titled '{title}' " + "\n" +
                    f" for branch {branch} targeting {target_branch}. ")
                logging.info(f"reviewers: {reviewers}, labels={add_labels}")
                request = repo.createPullRequest(title, branch, target_branch, description=descr, reviewers=reviewers,
                                                 non_approvers=non_approver_list, wip=wip,
                                                 labels=add_labels)
                if request:
                   url = request.link()
                   logging.info(f"Pull request created at {url} .")
            except stashy_errors.GenericException as e:
                logging.error(f"BITBUCKET: {e.data['errors'][0]['message']}")
                if not pullRequestAlreadyMerged(e.data["errors"][0]["message"]):
                    exit(1)
            except stashy_errors.NotFoundException as e:
                if targetBranchMissing(e.data["errors"][0]["message"]):
                    if utility.userInput(f"Target branch {target_branch} in {git_execution_path} is missing ... would you like to create and push it? [y/n]"):
                        start_branch = utility.userInput(f"Where should {target_branch} branch off of?")
                        git.branch(f"{target_branch} {start_branch}", execution_path=git_execution_path)
                        git.push(f"origin {target_branch}", execution_path=git_execution_path)
                        postPullRequest(repo, title, branch, target_branch, descr, reviewers,
                                        args, git_execution_path,
                                        non_approver_list=non_approver_list, wip=wip,
                                        add_labels=add_labels, remove_labels=remove_labels)
        else:
            logging.info(
                f"No pull request from {branch} to {target_branch} to update")

    else:
        if not args["--add"]:
            # update the pull request
            logging.info("Updating pull request...")
            try:
                logging.info(f"reviewer list is: {reviewers}")
                ver = request.version()

                if title is not None and (args["--prepend"] or args["--append"]):
                    currentTitle = request.title()
                    if args["--prepend"]:
                        if currentTitle.startswith(title):
                            title = currentTitle
                        else:
                            title = title + currentTitle
                    elif args["--append"]:
                        if currentTitle.endswith(title):
                            title = currentTitle
                        else:
                            title = currentTitle + title

                author = request.author()
                subReviewers = reviewers.copy()

                for reviewRuleName in subReviewers:
                    if author in subReviewers[reviewRuleName]['reviewers']:
                        logging.info(
                                f"{author} is the author of the pull" +
                                " request and cannot be a reviewer")
                        subReviewers[reviewRuleName]['reviewers'].remove(author)

                url = request.link()

                if title is not None or descr is not None or subReviewers or add_labels or remove_labels or wip is not None:
                    # Determine if any labels will be changing
                    have_changed_labels = False
                    if add_labels or remove_labels:
                       current_labels = set(request.labels())
                       have_changed_labels = bool(current_labels.intersection(set(remove_labels)))
                       if not have_changed_labels:
                          for label in add_labels:
                             if label not in current_labels:
                                have_changed_labels = True
                                break

                    # Check to see if we actually have something to change
                    updates = []
                    if title != request.title():
                        updates.append(f"title={title}")
                    if wip is not None:
                        updates.append(f"draft={wip}")
                    if descr.strip() != request.description().strip():
                        # Note that the description will change whenever the reviewers change.
                        updates.append(f"description={descr}")

                    # Rely on request.update to determine if reviewers have actually changed.
                    if subReviewers:
                        updates.append(f"reviewers={subReviewers}")

                    if have_changed_labels:
                        if add_labels:
                           updates.append(f"add_labels={add_labels}")
                        if remove_labels:
                           updates.append(f"remove_labels={remove_labels}")

                    if updates:
                        # Only perform the request is something actually changed
                        logging.info(f"updating request with {', '.join(updates)}")
                        request = request.update(ver, title=title, description=descr, reviewers=subReviewers,
                                                 non_approvers=non_approver_list, wip=wip,
                                                 add_labels=add_labels, remove_labels=remove_labels)
                        if have_changed_labels:
                           logging.info("Regenerating pipeline...")
                           request.regeneratePipeline()
                        logging.info(f"Pull request updated at {url} .")
                    else:
                        logging.info(f"Pull request unchanged at {url} .")
                else:
                    logging.info(f"Pull request unchanged at {url} .")
            except stashy_errors.GenericException as e:
                logging.error(f"BITBUCKET: {e.data['errors'][0]['message']}")
                logging.error(f"BITBUCKET: {e.data}")
                if not pullRequestAlreadyMerged(e.data["errors"][0]["message"]):
                    exit(1)
        else:
            logging.info(f"Pull request from {branch} to " +
                         f"{target_branch} already exists, can't add a new one")

    return request


def parseReviewers(args, reviewRuleManager):
    '''
    Extracts reviewer groups from the --reviewers argument.
    The argument should consist of whitespace separated groups, where
    each group is in one of the following forms:

    <username>[,<username>]* -> these reviewers are assigned to the default rule
    <rule>:<username>[,<username>] -> these reviewers are assigned to the given rule

    e.g.

    --reviewers="username1,username2 rule1:username1 rule2:username2,username3"

    In this case, username1 and username2 will be assigned to the default
    review rule. username1 will also be assigned to rule1, and username2
    along with username3 will be assigned to rule2.

    :param args: A dictionary containing arguments to a prior or current GRAPE call
    :param reviewRuleManager: ReviewRuleManager instance containing review rules configuration
    :return: A dictionary where each key is a review rule name and the value is a dictionary containing a label and a unique list of reviewers.
    '''

    reviewers = {}
    reviewRules = reviewRuleManager.reviewRules
    reviewRuleMap = reviewRuleManager.reviewRuleMap
    defaultReviewRuleName = reviewRuleManager.defaultReviewRuleName

    # Parse reviewers from saved arguments
    arg = args.get("--reviewers")

    if arg is not None:
        if not arg:
            # The empty string means remove all reviewers
            for reviewRuleName in reviewRuleManager.activeRuleNames:
                reviewers[reviewRuleName] = {
                    'label': reviewRules[reviewRuleName].label,
                    'reviewers': []
                }

            return reviewers

        # Otherwise, parse the given string
        reviewerGroups = arg.split()

        for reviewerGroup in reviewerGroups:
            tokens = reviewerGroup.split(":")

            if len(tokens) == 1:
                # Use the default rule
                reviewRuleName = defaultReviewRuleName

                if reviewRuleName in reviewers:
                    logging.error(f'GRAPE: ERROR: Reviewers must be separated by commas.')
                    exit(1)

                reviewRuleReviewers = tokens[0].lower().split(',')
            elif len(tokens) == 2:
                # Use the given rule
                reviewRuleName = tokens[0]

                if reviewRuleName in reviewRuleMap:
                    reviewRuleName = reviewRuleMap[reviewRuleName]

                # Check the given rule name is a review rule
                if reviewRuleName not in reviewRules or not reviewRules[reviewRuleName].active:
                    logging.error(f'GRAPE: ERROR: "{reviewRuleName}" is not an active review rule.')
                    exit(1)

                if tokens[1]:
                    reviewRuleReviewers = tokens[1].lower().split(',')
                else:
                    reviewRuleReviewers = []

                if reviewRuleName in reviewers:
                    logging.warning(f'GRAPE: WARNING: "{reviewRuleName}" should be specified only once.')
                    reviewRuleReviewers.extend(reviewers[reviewRuleName]['reviewers'])
            else:
                logging.error(f'GRAPE: ERROR: The --reviewers argument should consist of whitespace separated groups, where each group is in one of the following forms:\n\t<username>[,<username>]*\n\t<rule>:<username>[,<username>]*\n\te.g. --reviewers="username1,username2 rule:username3,username4"')
                exit(1)

            reviewRule = reviewRules[reviewRuleName]

            # Check for duplicate reviewers
            uniqueReviewRuleReviewers = set(reviewRuleReviewers)

            if len(reviewRuleReviewers) != len(uniqueReviewRuleReviewers):
                logging.warning(f'GRAPE: WARNING: "{reviewRuleName}" has duplicate reviewers. Duplicates will be removed.')
                reviewRuleReviewers = list(uniqueReviewRuleReviewers)

            reviewers[reviewRuleName] = {
                'label': reviewRule.label,
                'reviewers': reviewRuleReviewers
            }

    # Return the dictionary of reviewers
    return reviewers


if __name__ == "__main__":
    grapeMenu.menu().applyMenuChoice("review",[])
