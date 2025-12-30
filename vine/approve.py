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
        user_name = self._get_user_name(args)
        git_host = self._authenticate_to_git_host(user_name, args)
        top_repo_context = self._get_top_repo_context(git_host, args)
        rule = self._get_review_rule(top_repo_context, user_name, args)
        approve_input = self._get_approve_input(git_host, top_repo_context, rule)
        self._apply_approve_actions(rule, approve_input)

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
            workspace_dir=self.workspace_dir
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
            - repo_facade
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
            'repo_facade': repo,
            'source_branch': source_branch,
            'source_commit': source_commit,
            'target_branch': target_branch,
            'target_commit': target_commit,
            'grape_config': config
        }

    @staticmethod
    def _get_review_rule(top_repo_context, user_name, args):
        rules = review.parseReviewRules(top_repo_context['grape_config'])
        active_rule_names = [rule_name for rule_name in rules if rules[rule_name]['active']]

        rule_name = args['--rule']

        if not rule_name:
            rule_name = utility.userInput(f'Please enter a review rule name ({", ".join(active_rule_names)}): ')

        if rule_name not in active_rule_names:
            logging.error(f'GRAPE: ERROR: Review rule "{rule_name}" is invalid. Active rules: {", ".join(active_rule_names)}.')
            exit(1)

        rule = rules[rule_name]
        self._validate_approver(rule, user_name)
        return rule

    @staticmethod
    def _validate_approver(rule, user_name):
        """
        Validate that the given user is eligible to approve the provided review rule.

        This checks the supplied `user_name` against each regex pattern in
        `rule["eligibleReviewers"]`. If any pattern matches (via `re.fullmatch`),
        the user is considered eligible and the method returns normally.

        Parameters
        ----------
        rule : dict
            Review rule definition containing:
            - "eligibleReviewers": list[str] of regex patterns for eligible approvers
            - "name": str rule name (used for error messages)
        user_name : str
            User name to validate.

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
    def _rule_applies(repo_name, rule):
        for repo_pattern in rule['repositories']:
            if re.fullmatch(repo_pattern, repo_name):
                return True

        return False

    @staticmethod
    def _get_modified_repos(git_host, top_repo_context):
        # Gather all modified repositories (top level, submodules, and subprojects)
        modified_repos = {}

        if top_source_commit != top_target_commit:
            modified_repos[repo_name] = top_repo

        self._get_modified_submodules(config, top_repo, git_host, modified_repos)
        self._get_modified_subprojects(config, top_repo, git_host, modified_repos)

        return modified_repos

    @staticmethod
    def _get_modified_subprojects(config, top_repo, git_host, modified_repos):
        top_project_name = top_repo['project_name']
        source_branch = top_repo['source_branch']
        target_branch = top_repo['target_branch']

        subprojects = config.getAllNestedSubprojects()

        for subproject in subprojects:
            # TODO: Check url matches the top level git service
            url = config.get(f"nested-{subproject}","url")
            components = url.split('/')
            base_name = components[-1]
            repo_name = base_name.split('.')[0] # Remove .git if present
            project_name = components[-2]

            if project_name == '..':
                project_name = top_project_name

            repo_facade = git_host.project(project_name).repo(repo_name)
            source_commit = repo_facade.getBranchHeadCommitHash(source_branch)

            if not source_commit:
                # Source branch does not exist, which means there are no changes
                continue

            target_commit = repo_facade.getBranchHeadCommitHash(target_branch)

            if not target_commit:
                logging.error(f'GRAPE: ERROR: Target branch "{target_branch}" does not exist in subproject "{subproject}".')
                exit(1)

            if source_commit == target_commit:
                # No changes
                continue

            review_request = repo_facade.getOpenPullRequest(source_branch, target_branch)

            if not review_request:
                logging.warning(f'GRAPE: WARNING: Subproject "{subproject}" missing open pull request for "{source_branch}" targeting "{target_branch}". Skipping...')
                continue

            modified_repos[repo_name] = {
                'repo_name': repo_name,
                'project_name': project_name,
                'repo_facade': repo_facade,
                'review_request': review_request,
                'source_branch': source_branch,
                'source_commit': source_commit,
                'target_branch': target_branch
            }

    @staticmethod
    def _get_modified_submodules(config, top_repo, git_host, modified_repos):
        top_project_name = top_repo['project_name']
        top_repo_facade = top_repo['repo_facade']
        top_source_branch = top_repo['source_branch']
        top_target_branch = top_repo['target_branch']

        gitmodules = top_repo_facade.getFile(".gitmodules", source_branch)

        if gitmodules:
            submodules_metadata = submodules.parse_gitmodules(gitmodules.splitlines())
            submodule_branch_mappings = config.getMapping(self.SECTION_WORKSPACE, "submoduleTopicPrefixMappings")
            submodule_source_branch = top_source_branch
            source_branch_prefix = git.branchPrefix(submodule_source_branch)
            submodule_target_branch = submodule_branch_mappings[source_branch_prefix]

            for submodule_name in submodules_metadata:
                submodule_metadata = submodules_metadata[submodule_name]
                # TODO: Check url matches the top level git service
                url = submodule_metadata['url']
                components = url.split('/')
                submodule_repo_name = components[-1].split('.')[0] # Remove .git
                submodule_project_name = components[-2]

                if submodule_project_name == '..':
                    submodule_project_name = project_name

                submodule_repo = git_host.project(submodule_project_name).repo(submodule_repo_name)
                submodule_source_commit = submodule_repo.getBranchHeadCommitHash(submodule_source_branch)

                if not submodule_source_commit:
                    # Source branch does not exist, which means there are no changes
                    continue

                submodule_target_commit = submodule_repo.getBranchHeadCommitHash(submodule_target_branch)

                if not submodule_target_commit:
                    logging.error(f"GRAPE: ERROR: Target branch '{submodule_target_branch}' does not exist in '{submodule_project_name}/{submodule_repo_name}'")
                    exit(1)

                if submodule_source_commit == submodule_target_commit:
                    # No changes
                    continue

                review_request = submodule_repo.getOpenPullRequest(submodule_source_branch, submodule_branch)

                if not review_request:
                    logging.warning(f'GRAPE: WARNING: Submodule "{submodule_name}" missing open pull request for "{submodule_source_branch}" targeting "{submodule_target_branch}". Skipping...')
                    continue

                modified_repos[submodule_repo_name] = {
                    'repo_name': submodule_repo_name,
                    'project_name': submodule_project_name,
                    'repo_facade': submodule_repo,
                    'review_request': review_request,
                    'source_branch': source_branch,
                    'source_commit': submodule_source_commit,
                    'target_branch': submodule_target_branch
                }

    def _get_approve_input(git_host, top_repo_context, rule):
        modified_repos = self._get_modified_repos(git_host, top_repo_context)
        any_approvals = False

        for name in modified_repos:
            # Set default approval and input state
            repo_context = modified_repos[name]
            repo_context['approved'] = False
            repo_context['input'] = {}

            # Check if rule applies
            if not self._rule_applies(name, rule):
                continue

            # Ask for approval
            logging.info(f'Applying review rule "{rule['name']}" to project "{name}"...')
            source_branch = repo_context['source_branch']
            source_commit = repo_context['source_commit']
            approval_granted = utility.userInput(f'I approve the changes on branch "{source_branch}" ({source_commit}).', default='y').lower() == 'y'

            if not approval_granted:
                continue

            any_approvals = True

            # Ask for input
            approval_input = repo_context['input']

            for rule_input in rule['input']:
                # TODO: Add case for username/user display name
                if rule_input == 'commit':
                    approval_input[rule_input] = source_commit
                else:
                    approval_input[rule_input] = utility.userInput(f'{rule_input}: ')

        if not any_approvals:
            logging.info(f'No merge/pull requests approved. Exiting...')
            exit(0)

        return modified_repos

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
            repo = repo_context['repo_facade']
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