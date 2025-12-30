import logging
import configparser
from io import StringIO
from vine import CodeReviewsFactory
from vine import config_parser_base
from vine import config_parser_global
from vine import config_parser_user
from vine import grapeGit as git
from vine import multi_repo_cmd_launcher
from vine import review
from vine import submodules
from vine import vine_subprocess
from vine.option import Option
from vine.workspace_dir_handler import WorkspaceDirHandler
from vine.vine_logging import log_wrapper
from vine import utility
import re
import sys

class Approve(Option, WorkspaceDirHandler):
    """
    grape approve
    Manage approval for a pull/merge request.
    Usage: grape-approve [--rule=<ruleName>]
                         [--source=<topicBranch>]
                         [--target=<publicBranch>]
                         [--project=<prj>]
                         [--repo=<repo>]
                         [--user=<userName>]
                         [--codeReviewsURL=<url>]
                         [--verifySSL=<bool>]
                         [--ssh_pat_url=<url>]
                         [--ssh_pat_port=<int>]

    Options:
        --rule=<ruleName>           The name of the review rule to apply.
        --source=<topicBranch>      The branch to approve the merge request for.
        --target=<publicBranch>     The public branch targeted by the merge request.
                                    Defaults to mapping for source branch.
        --project=<prj>             The project/group name.
                                    [default: .grapeconfig.project.name]
        --repo=<repo>               The repository name.
                                    [default: .grapeconfig.repo.name]
        --user=<userName>           Your GitLab user name.
        --codeReviewsURL=<url>      The code review platform url, e.g. https://your.host.org/gitlab.
                                    [default: .grapeconfig.project.codeReviewsURL]
        --verifySSL=<bool>          Set to False to ignore SSL certificate verification issues.
                                    [default: .grapeconfig.project.verifySSL]
        --ssh_pat_url=<url>         SSH URL for generating Personal Access Tokens to authenticate into a Code Review service's
                                    REST API.
                                    [default: .grapeconfig.repo.ssh_pat_url]
        --ssh_pat_port=<int>        Port number to issue ssh command over to generate a Personal Access Token for authentication
                                    into a Code Review service's REST API.
                                    [default: .grapeconfig.repo.ssh_pat_port]
    """
    def __init__(self):
        super(Approve, self).__init__()
        self._key = "approve"
        self._section = "Code Reviews"

    def description(self):
        return "Approve a merge/pull request."

    @log_wrapper
    def execute(self, args):
        user_name = Approve._get_user_name(args)
        git_host = Approve._authenticate_to_git_host(user_name, args)
        top_repo_context = Approve._get_top_repo_context(git_host, args)
        rule = Approve._get_review_rule(top_repo_context, args)
        Approve._approve(user_name, git_host, top_repo_context, rule)

    def setDefaultConfig(self, config):
        config.ensureSection(self.SECTION_PROJECT)
        config.set(self.SECTION_PROJECT, "codeReviewsURL", "https://your.host.org/gitlab/or/bitbucket")
        config.set(self.SECTION_PROJECT, "verifySSL", "True")
        config.set(self.SECTION_PROJECT, "name", "My unnamed project")
        config.ensureSection(self.SECTION_REPO)
        config.set(self.SECTION_REPO, "ssh_pat_url", "git@gitlab.your.host.org")
        config.set(self.SECTION_REPO, "ssh_pat_port", "7999")
        config.set(self.SECTION_REPO, "name", "My unnamed repo")

    @staticmethod
    def _get_user_name(args):
        """
        Resolve the user name from parsed command line arguments.

        This method first checks the `--user` option in the given `args`
        dictionary. If a value is provided for `--user`, that value is
        returned. Otherwise, it falls back to `utility.getUserName()`.

        Parameters
        ----------
        args : dict
            Dictionary of command line arguments. May contain the key `"--user"`.

        Returns
        -------
        str
            The user name supplied via `--user`, or the default user name
            returned by `utility.getUserName()` if `--user` is not set or is
            falsey.
        """
        return args['--user'] or utility.getUserName()

    @staticmethod
    def _authenticate_to_git_host(user_name, args):
        """
        Authenticate to the git hosting service and create a client instance.

        This method builds the connection parameters from the provided
        command line arguments, logs the target URL, and delegates client
        creation to `CodeReviewsFactory.makeCodeReviews`.

        Parameters
        ----------
        user_name : str
            The user name to authenticate as.
        args : dict
            Dictionary of command line arguments, expected to contain:

            - `"--codeReviewsURL"` : str
            Base URL of the code review or Git host.
            - `"--verifySSL"` : str
            String flag indicating whether SSL certificates should be
            verified, for example `"true"` or `"false"`.
            - `"--ssh_pat_port"` : str or int
            Port number used for SSH or PAT based communication.
            - `"--ssh_pat_url"` : str
            SSH or PAT endpoint or URL segment used for authentication.

        Returns
        -------
        CodeReviews
            An instance returned by `CodeReviewsFactory.makeCodeReviews`
            configured for the given user and git hosting service.

        Side Effects
        ------------
        Logs an informational message indicating the URL that is being used
        to authenticate.

        Notes
        -----
        The `"--verifySSL"` argument is treated as case insensitive; only
        the string `"true"` (ignoring case) results in certificate
        verification being enabled.
        """
        url = args['--codeReviewsURL']
        verify = True if args['--verifySSL'].lower() == 'true' else False
        logging.info(f'Logging onto {url}')

        return CodeReviewsFactory.makeCodeReviews(
            user_name,
            url=url,
            verify=verify,
            port=int(args['--ssh_pat_port']),
            ssh_path=args['--ssh_pat_url'],
            workspace_dir=Approve.workspace_dir
        )

    @staticmethod
    def _get_top_repo_context(git_host, args):
        """
        Build and validate the top-level repository context needed for approvals.

        This resolves the project/repo from CLI args, validates the existence of
        the source and target branches, loads the `.grapeconfig` from the source
        branch, and returns a context dictionary used by downstream approval
        logic.

        Parameters
        ----------
        git_host : CodeReviews
            Authenticated code review / git hosting client.
        args : dict
            Parsed command-line arguments. Expected keys:
            - "--project" : str
            - "--repo" : str
            - "--source" : str (optional; may be prompted)
            - "--target" : str (optional; defaults via .grapeconfig mapping)

        Returns
        -------
        dict
            Context containing:
            - repo_name
            - project_name
            - repo
            - source_branch
            - source_commit
            - target_branch
            - target_commit
            - grape_config (GrapeConfigParserBase)

        Exits
        -----
        Terminates the process with exit code 1 if:
        - source branch does not exist
        - `.grapeconfig` is missing on the source branch
        - target branch does not exist
        """
        # Get repo info
        project_name = args['--project']
        repo_name = args['--repo']
        repo = git_host.project(project_name).repo(repo_name)

        # Get and validate source branch
        source_branch = args["--source"]

        if not source_branch:
            source_branch = utility.userInput(f'Please enter the name of the branch being approved: ')

            if not source_branch:
                logging.error(f'GRAPE: ERROR: Source branch is required.')
                exit(1)

        source_commit = repo.getBranchHeadCommitHash(source_branch)

        if not source_commit:
            logging.error(f'GRAPE: ERROR: Source branch "{source_branch}" does not exist in "{project_name}/{repo_name}"')
            exit(1)

        # Get grape config
        grapeconfig = repo.getFile('.grapeconfig', source_branch)

        if not grapeconfig:
            logging.error(f'GRAPE: ERROR: File ".grapeconfig" does not exist in "{project_name}/{repo_name}"')
            exit(1)

        config = config_parser_base.GrapeConfigParserBase(workspaceDir=None, configString=grapeconfig)

        # Get and validate target branch
        target_branch = args['--target']

        if not target_branch:
            target_branch = config.getPublicBranchFor(source_branch)

        target_commit = repo.getBranchHeadCommitHash(target_branch)

        if not target_commit:
            logging.error(f'GRAPE: ERROR: Target branch "{target_branch}" does not exist in "{project_name}/{repo_name}"')
            exit(1)

        return {
            'repo_name': repo_name,
            'project_name': project_name,
            'repo': repo,
            'source_branch': source_branch,
            'source_commit': source_commit,
            'target_branch': target_branch,
            'target_commit': target_commit,
            'grape_config': config
        }

    @staticmethod
    def _get_review_rule(top_repo_context, args):
        """
        Resolve and validate the active review rule to apply.

        This loads review rules from the repository's `.grapeconfig`, filters to
        active rules, obtains the requested rule name from `args["--rule"]` or
        prompts the user, validates that the rule is active, and returns the rule
        definition.

        Parameters
        ----------
        top_repo_context : dict
            Context dictionary returned by `_get_top_repo_context`, expected to
            include:
            - "grape_config": config_parser_base.GrapeConfigParserBase
        args : dict
            Parsed command-line arguments. Expected key:
            - "--rule": str (optional)

        Returns
        -------
        dict
            The selected review rule definition.

        Exits
        -----
        Terminates the process with exit code 1 if the selected rule name is not
        among the active rules.
        """
        rules = review.parseReviewRules(top_repo_context['grape_config'])
        active_rule_names = [rule_name for rule_name in rules if rules[rule_name]['active']]

        rule_name = args['--rule']

        if not rule_name:
            rule_name = utility.userInput(f'Please enter a review rule name ({", ".join(active_rule_names)}): ')

        if rule_name not in active_rule_names:
            logging.error(f'GRAPE: ERROR: Review rule "{rule_name}" is invalid. Active rules: {", ".join(active_rule_names)}.')
            exit(1)

        return rules[rule_name]

    @staticmethod
    def _approve(user_name, git_host, top_repo_context, rule):
        """
        Perform the end-to-end approval workflow for a review rule.

        This method:
          1) Validates that `user_name` is eligible to approve `rule`.
          2) Detects which repositories (top repo, submodules, subprojects) have changes
             between the source and target branches and have open review requests.
          3) Prompts the user for per-repository approval and collects any rule-defined input.
          4) Applies the configured approve actions (e.g., approve, tag, update description)
             to each relevant open review request.

        Parameters
        ----------
        user_name : str
            User name of the approver.
        git_host : CodeReviews
            Authenticated code review / git hosting client.
        top_repo_context : dict
            Context dictionary returned by `_get_top_repo_context`.
        rule : dict
            Review rule definition returned by `_get_review_rule`.

        Side Effects
        ------------
        May prompt the user for input and may update/approve/tag merge/pull requests.

        Exits
        -----
        May terminate the process (via downstream calls) when validation fails or when
        no approvals are granted.
        """
        Approve._validate_approver(user_name, rule)
        modified_repos = Approve._get_modified_repos(git_host, top_repo_context)
        approve_input = Approve._get_approve_input(rule, modified_repos)
        Approve._apply_approve_actions(rule, approve_input)

    @staticmethod
    def _validate_approver(user_name, rule):
        """
        Validate that the given user is eligible to approve the provided review rule.

        This checks the supplied `user_name` against each regex pattern in
        `rule["eligibleReviewers"]`. If any pattern matches (via `re.fullmatch`),
        the user is considered eligible and the method returns normally.

        Parameters
        ----------
        user_name : str
            User name to validate.
        rule : dict
            Review rule definition containing:
            - "eligibleReviewers": list[str] of regex patterns for eligible approvers
            - "name": str rule name (used for error messages)

        Exits
        -----
        Terminates the process with exit code 1 if the user does not match any
        eligible reviewer pattern.
        """
        for approver_pattern in rule['eligibleReviewers']:
            if re.fullmatch(approver_pattern, user_name):
                return

        logging.error(f'GRAPE: ERROR: User "{user_name}" cannot approve review rule "{rule["name"]}".')
        exit(1)

    @staticmethod
    def _get_modified_repos(git_host, top_repo_context):
        """
        Determine which repositories have changes between the source and target branches.

        This builds and returns a dictionary of repository context objects for all
        repositories that have differing head commits between the source and target
        branches, including:
          - the top-level repository (if source_commit != target_commit)
          - modified submodules (via `_add_modified_submodules`)
          - modified nested subprojects (via `_add_modified_subprojects`)

        Parameters
        ----------
        git_host : CodeReviews
            Authenticated code review / git hosting client used to access repos.
        top_repo_context : dict
            Context dictionary returned by `_get_top_repo_context`, expected to
            contain at least:
              - repo_name
              - source_commit
              - target_commit
              - source_branch
              - target_branch
              - project_name
              - repo

        Returns
        -------
        dict
            Mapping of repo_name -> repo_context for each repository detected as
            modified relative to the target branch.
        """
        modified_repos = {}

        if top_repo_context['source_commit'] != top_repo_context['target_commit']:
            modified_repos[top_repo_context['repo_name']] = top_repo_context

        Approve._add_modified_submodules(git_host, top_repo_context, modified_repos)
        Approve._add_modified_subprojects(git_host, top_repo_context, modified_repos)

        return modified_repos

    @staticmethod
    def _add_modified_submodules(git_host, top_repo_context, modified_repos):
        """
        Add modified submodules (with open review requests) to the modified repos map.

        This inspects the top repository's `.gitmodules` file on the source branch,
        parses submodule definitions, derives the corresponding target branch for
        submodules using the workspace mapping `submoduleTopicPrefixMappings` from
        the repository's `.grapeconfig`, and then checks each submodule repository
        for:
          - existence of the source branch,
          - existence of the derived target branch (fatal if missing),
          - differing head commits between source and target, and
          - an open merge/pull request from source -> target.

        Submodules meeting these criteria are added to `modified_repos` keyed by
        repository name.

        Parameters
        ----------
        git_host : CodeReviews
            Authenticated code review / git hosting client.
        top_repo_context : dict
            Context dictionary for the top-level repository, expected to include:
              - "repo": repository client for the top repo
              - "source_branch": str
              - "project_name": str
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
        submodule_branch_mappings = config.getMapping(Approve.SECTION_WORKSPACE, 'submoduleTopicPrefixMappings')
        source_branch_prefix = git.branchPrefix(submodule_source_branch)
        submodule_target_branch = submodule_branch_mappings[source_branch_prefix]

        top_project_name = top_repo_context['project_name']

        for submodule_name in submodules_metadata:
            submodule_metadata = submodules_metadata[submodule_name]
            # TODO: Check url matches the top level git service
            url = submodule_metadata['url']

            modified_repo_context = Approve._get_modified_repo_context(
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
        whether the subproject:
          - has a source branch,
          - has the required target branch,
          - differs between source and target commits, and
          - has an open merge/pull request from source -> target.

        When a subproject meets these criteria, its repo context is added to
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
            modified_repo_context = Approve._get_modified_repo_context(
                git_host, top_project_name, subproject_source_branch, subproject_target_branch, url
            )

            if modified_repo_context:
                modified_repos[modified_repo_context['repo_name']] = modified_repo_context

    @staticmethod
    def _get_modified_repo_context(git_host, top_project_name, source_branch, target_branch, url):
        """
        Build repository context for a nested repo (submodule/subproject) only if it has changes and an open review request.

        This resolves the repository's project/name from the given repository URL, verifies that the source branch exists,
        verifies that the target branch exists (fatal if missing), compares the branch head commits to determine whether
        there are changes, and finally locates an open merge/pull request from `source_branch` into `target_branch`.

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
            Returns a repo context dict when:
              - the source branch exists
              - the target branch exists
              - source and target head commits differ
              - an open merge/pull request exists from source -> target

            Otherwise returns None when:
              - the source branch does not exist (treated as "no changes")
              - source and target commits are identical ("no changes")
              - no open merge/pull request exists (skips with warning)

            The returned dict contains:
              - repo_name
              - project_name
              - repo
              - review_request
              - source_branch
              - source_commit

        Exits
        -----
        Terminates the process with exit code 1 if the target branch does not exist in the repository.
        """
        # Get repo
        components = url.split('/')
        repo_name = components[-1].split('.')[0] # Remove .git if present
        project_name = components[-2]

        if project_name == '..':
            project_name = top_project_name

        repo = git_host.project(project_name).repo(repo_name)

        # Check source branch
        source_commit = repo.getBranchHeadCommitHash(source_branch)

        if not source_commit:
            # Source branch does not exist, which means there are no changes
            return None

        # Check target branch
        target_commit = repo.getBranchHeadCommitHash(target_branch)

        if not target_commit:
            logging.error(f'GRAPE: ERROR: Repository "{repo_name}" is missing target branch "{target_branch}".')
            exit(1)

        # Compare source and target branches
        if source_commit == target_commit:
            # No changes
            return None

        # Check merge/pull request
        review_request = repo.getOpenPullRequest(source_branch, target_branch)

        if not review_request:
            logging.warning(f'GRAPE: WARNING: Repository "{repo_name}" is missing open merge/pull request for "{source_branch}" targeting "{target_branch}". Skipping...')
            return None

        return {
            'repo_name': repo_name,
            'project_name': project_name,
            'repo': repo,
            'review_request': review_request,
            'source_branch': source_branch,
            'source_commit': source_commit
        }

    @staticmethod
    def _get_approve_input(rule, modified_repos):
        """
        Prompt the user for approvals and collect rule-defined input per modified repository.

        For each repository in `modified_repos`, this method initializes default approval state
        (`approved=False`, `input={}`), checks whether the given `rule` applies to the repo via
        `_rule_applies`, and if so prompts the user to approve the changes on the repo's source
        branch/commit. When approval is granted, it gathers any additional input fields defined
        in `rule["input"]` and stores them in the repo context.

        Parameters
        ----------
        rule : dict
            Review rule definition. Expected keys:
              - "name": str
              - "input": list[str]
              - "repositories": list[str]
        modified_repos : dict
            Mapping of repo_name -> repo_context. Each repo_context is mutated in-place to add:
              - "approved": bool
              - "input": dict

        Returns
        -------
        dict
            The same `modified_repos` mapping with per-repo approval state and collected input.

        Exits
        -----
        Exits with status code 0 when no approvals are granted.
        """
        any_approvals = False

        for repo_name in modified_repos:
            # Set default approval and input state
            repo_context = modified_repos[repo_name]
            repo_context['approved'] = False
            repo_context['input'] = {}

            # Check if rule applies
            if not Approve._rule_applies(repo_name, rule):
                continue

            # Ask for approval
            logging.info(f'Applying review rule "{rule["name"]}" to project "{repo_name}"...')
            source_branch = repo_context['source_branch']
            source_commit = repo_context['source_commit']
            approval_granted = utility.userInput(
                f'I approve the changes on branch "{source_branch}" ({source_commit}).',
                default='y'
            ).lower() == 'y'

            if not approval_granted:
                continue

            any_approvals = True

            # Ask for input
            repo_input = repo_context['input']

            for rule_input in rule['input']:
                # TODO: Add case for username/user display name
                if rule_input == 'commit':
                    repo_input[rule_input] = source_commit
                else:
                    repo_input[rule_input] = utility.userInput(f'{rule_input}: ')

        # Check if any approvals were granted
        if not any_approvals:
            logging.info(f'No merge/pull requests approved. Exiting...')
            exit(0)

        return modified_repos

    @staticmethod
    def _rule_applies(repo_name, rule):
        """
        Determine whether a review rule applies to a repository.

        Checks the given `repo_name` against each regex pattern listed in
        `rule["repositories"]` using `re.fullmatch`.

        Parameters
        ----------
        repo_name : str
            Repository name to test.
        rule : dict
            Review rule definition containing:
            - "repositories": list[str] of regex patterns.

        Returns
        -------
        bool
            True if any repository pattern fully matches `repo_name`, otherwise
            False.
        """
        for repo_pattern in rule["repositories"]:
            if re.fullmatch(repo_pattern, repo_name):
                return True

        return False

    def _apply_approve_actions(rule, modified_repos):
        # Build rule section for merge request description
        rule_section = ''

        if 'update_description' in rule['approve_actions']:
            rule_section = f'# {rule["label"]}'

            for name in sorted(modified_repos.keys()):
                repo_context = modified_repos[name]

                if repo_context['approved']:
                    rule_section += f'\n\n## {name}'
                    approval_inputs = repo_context['input']

                    for approval_input in sorted(approval_inputs.keys()):
                        rule_section += f'\n\n{approval_input}: {approval_inputs[approval_input]}'

        # Now apply approvals. All modified repositories are included because they may need to have their merge request description updated
        for name in modified_repos:
            repo_context = modified_repos[modified_repo_name]
            repo = repo_context['repo']
            source_commit = repo_context['source_commit']
            review_request = repo_context['review_request']

            # Update merge request description
            if 'update_description' in rule['approve_actions']:
                current_description = review_request.description().decode("utf-8").strip()
                section_header = f'# {rule["label"]}'

                if section_header in current_description:
                    # Pattern:
                    # - Match "# {section_name}" at line start
                    # - Capture everything until next top-level header ("# " at line start) or end of string
                    pattern = (
                        rf'^{re.escape(section_header)}\s*\n'    # Section header
                        r'(.*?)'                                 # Section content (non-greedy capture)
                        r'(?=^# [^\n]*|\Z)'                      # Stop at next top-level section header or end of string
                    )

                    def repl(match):
                        # Replace section and preserve new lines before next section
                        # If there is no section after this one, the extra new lines
                        # will be stripped off anyway.
                        return f'{rule_section}\n\n'

                    updated_description = re.sub(pattern, repl, current_description, flags=re.DOTALL|re.MULTILINE).rstrip()
                else:
                    updated_description = f'{current_description.rstrip()}\n\n{rule_section}'

                review_request.update(review_request.version(), description=updated_description)

            if repo_context['approved']:
                # Approve reviewed branch
                if 'approve' in rule['approve_actions']:
                    try:
                        review_request.approve()
                    except:
                        logging.error(f'GRAPE: ERROR: Unable to approve merge request.')

                # Tag reviewed branch
                if 'tag' in rule['approve_actions']:
                    tag_name = f'{rule["name"]}_{review_request.iid()}'
                    tag_ref = source_commit
                    tag_message = rule['label']

                    project_inputs = repo_context['input']

                    for project_input in sorted(project_inputs.keys()):
                        tag_message += f'\n\n{project_input}: {project_inputs[project_input]}'

                    repo.updateTag(tag_name, tag_ref, tag_message)
                    # TODO: Consider logging if the tag already existed and is being updated