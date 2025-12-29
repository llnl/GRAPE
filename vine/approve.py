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
        self._rules = None
        self._active_rule_names = None

    def description(self):
        return "Approve a merge/pull request."

    @log_wrapper
    def execute(self, args):
        # Authenticate to git hosting service
        user_name = args['--user'] or utility.getUserName()
        url = args['--codeReviewsURL']
        verify = True if args['--verifySSL'].lower() == 'true' else False
        logging.info(f'Logging onto {url}')

        codeReviews = CodeReviewsFactory.makeCodeReviews(
            user_name,
            url=url,
            verify=verify,
            port=int(args['--ssh_pat_port']),
            ssh_path=args['--ssh_pat_url'],
            workspace_dir=self.workspace_dir
        )

        # Get repository and containing project/group
        project_name = args["--project"]
        repo_name = args["--repo"]
        top_repo = codeReviews.project(project_name).repo(repo_name)

        # Get and validate source branch
        source_branch = self._get_source_branch(args)
        top_source_hash = top_repo.getBranchHeadCommitHash(source_branch)

        if not top_source_hash:
            logging.error(f"GRAPE: ERROR: Source branch '{source_branch}' does not exist in '{project_name}/{repo_name}'")
            exit(1)

        # Get config
        grapeconfig = top_repo.getFile('.grapeconfig', source_branch)

        if not grapeconfig:
            logging.error(f"GRAPE: ERROR: File '.grapeconfig' does not exist in '{project_name}/{repo_name}'")
            exit(1)

        config = config_parser_base.GrapeConfigParserBase(workspaceDir=None, configString=grapeconfig)

        # Get and validate target branch
        target_branch = args["--target"]

        if not target_branch:
            target_branch = config.getPublicBranchFor(source_branch)

        top_target_hash = top_repo.getBranchHeadCommitHash(target_branch)

        if not top_target_hash:
            logging.error(f"GRAPE: ERROR: Target branch '{target_branch}' does not exist in '{project_name}/{repo_name}'")
            exit(1)

        # Get review rules
        rules = review.parseReviewRules(config)
        active_rule_names = [rule_name for rule_name in rules if rules[rule_name]['active']]

        # Get and validate review rule
        rule_name = args['--rule']

        if not rule_name:
            rule_name = utility.userInput(f'Please enter a review rule name ({", ".join(active_rule_names)}): ')

        if rule_name not in active_rule_names:
            logging.error(f'GRAPE: ERROR: Review rule "{rule_name}" is invalid. Active rules: {", ".join(active_rule_names)}.')
            exit(1)

        rule = rules[rule_name]

        # Check if the user is allowed to approve
        if not _is_eligible_reviewer(user_name, rule):
            logging.error(f'GRAPE: ERROR: User "{user_name}" cannot approve review rule "{rule_name}".')
            exit(1)

        # Get the list of repositories to which the review rule applies
        rule_repositories = rule['repositories']

        # Get the list of inputs for this review rule.
        # The inputs are used to build a description if the approval actions
        # include tagging and/or updating the merge/pull request description.
        rule_inputs = rule['inputs']

        # Gather all modified repositories (top level, submodules, and subprojects)
        modified_repositories = {}

        # Check if top level is modified
        if top_source_hash != top_target_hash:
            modified_repositories[repo_name] = {
                'project_name': project_name,
                'source_branch': source_branch,
                'source_commit': top_source_hash,
                'target_branch': target_branch,
                'target_commit': top_target_hash,
                'api_facade': top_repo
            }

        # Check if subprojects are modified
        subproject_names = config.getAllNestedSubprojects()

        for subproject_name in subproject_names:
            url = config.get(f"nested-{subproject_name}","url")

            # TODO: Check url matches the top level git service
            components = url.split('/')
            subproject_repo_name = components[-1].split('.')[0] # Remove .git
            subproject_project_name = components[-2]

            if subproject_project_name == '..':
                subproject_project_name = project_name

            subproject_repo = codeReviews.project(subproject_project_name).repo(subproject_repo_name)
            subproject_source_hash = subproject_repo.getBranchHeadCommitHash(source_branch)

            if not subproject_source_hash:
                # Source branch does not exist, which means there are no changes
                continue

            subproject_target_hash = subproject_repo.getBranchHeadCommitHash(target_branch)

            if not subproject_target_hash:
                logging.error(f"GRAPE: ERROR: Target branch '{target_branch}' does not exist in '{subproject_project_name}/{subproject_repo_name}'")
                exit(1)

            if subproject_source_hash != subproject_target_hash:
                modified_repositories[subproject_repo_name] = {
                    'project_name': subproject_project_name,
                    'source_branch': source_branch,
                    'source_commit': subproject_source_hash,
                    'target_branch': target_branch,
                    'target_commit': subproject_target_hash,
                    'api_facade': subproject_repo
                }

        # Check if submodules are modified
        gitmodules = top_repo.getFile(".gitmodules", source_branch)

        if gitmodules:
            submodules_metadata = submodules.parse_gitmodules(gitmodules.splitlines())
            submodule_branch_mappings = config.getMapping(self.SECTION_WORKSPACE, "submoduleTopicPrefixMappings")
            source_branch_prefix = git.branchPrefix(source_branch)
            submodule_target_branch = submodule_branch_mappings[source_branch_prefix]

            for submodule_name in submodules_metadata:
                submodule_metadata = submodules_metadata[submodule_name]
                url = submodule_metadata['url']

                # TODO: Check url matches the top level git service
                components = url.split('/')
                submodule_repo_name = components[-1].split('.')[0] # Remove .git
                submodule_project_name = components[-2]

                if submodule_project_name == '..':
                    submodule_project_name = project_name

                submodule_repo = codeReviews.project(submodule_project_name).repo(submodule_repo_name)
                submodule_source_hash = submodule_repo.getBranchHeadCommitHash(source_branch)

                if not submodule_source_hash:
                    # Source branch does not exist, which means there are no changes
                    continue

                submodule_target_hash = subproject_repo.getBranchHeadCommitHash(submodule_target_branch)

                if not submodule_target_hash:
                    logging.error(f"GRAPE: ERROR: Target branch '{submodule_target_branch}' does not exist in '{submodule_project_name}/{submodule_repo_name}'")
                    exit(1)

                if submodule_source_hash != submodule_target_hash:
                    modified_repositories[submodule_repo_name] = {
                        'project_name': submodule_project_name,
                        'source_branch': source_branch,
                        'source_commit': submodule_source_hash,
                        'target_branch': submodule_target_branch,
                        'target_commit': submodule_target_hash,
                        'api_facade': submodule_repo
                    }
            
        # Check if rule applies to modified repositories and ask for approval and input
        approvals = {}

        for modified_repo_name in modified_repositories:
            # Check if the rule applies to this repository
            rule_applies = False

            for rule_repository in rule_repositories:
                if re.fullmatch(rule_repository, modified_repo_name):
                    rule_applies = True
                    break

            if not rule_applies:
                continue

            # Get modified repo info
            modified_repo = modified_repositories[modified_repo_name]

            # Check if there is an open Merge/Pull request
            modified_repo_api_facade = modified_repo['api_facade']
            source_branch = modified_repo['source_branch']
            review_request = modified_repo_api_facade.getOpenPullRequest(source_branch, modified_repo['target_branch'])

            if not review_request:
                # TODO: log a message
                continue

            # Ask for approval
            logging.info(f'Applying review rule "{rule_name}" to subproject "{modified_repo_name}".')
            source_commit = modified_repo['source_commit']
            approval_granted = utility.userInput(f'I have reviewed and approve the changes on branch "{source_branch}" (commit {source_commit}).', default='y')

            if not approval_granted:
                continue

            # Ask for input
            approvals[modified_repo_name] = {
                'commit': source_commit,
                'inputs': {}
            }

            approval_input = approvals[modified_repo_name]['inputs']

            for rule_input in rule_inputs:
                # TODO: Add case for username/user display name
                if rule_input == 'commit':
                    approval_input[rule_input] = source_commit
                else:
                    approval_input[rule_input] = utility.userInput(f'{rule_input}: ')

        if not approvals:
            # TODO: log message about nothing being approved
            exit(0)

        # Build rule section for merge request description
        rule_section = ''

        if 'update_description' in rule['approve_actions']:
            rule_section = f'# {rule["label"]}'

            for key in sorted(approvals.keys()):
                rule_section += f'\n\n## {key}'
                approval = approvals[key]
                project_inputs = approval['inputs']

                for project_input in sorted(project_inputs.keys()):
                    rule_section += f'\n\n{project_input}: {project_inputs[project_input]}'

        # Now apply approvals. All modified repositories are included because they may need to have their merge request description updated
        for modified_repo_name in modified_repositories:
            modified_repo = modified_repositories[modified_repo_name]
            repo = modified_repo['api_facade']
            source_branch = modified_repo['source_branch']
            source_commit = modified_repo['source_commit']
            target_branch = modified_repo['target_branch']

            # Update merge request description
            review_request = repo.getOpenPullRequest(source_branch, target_branch)

            if not review_request:
                logging.warning(f"No open pull request found for branch {source_branch} targeting {target_branch}")
                continue

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

            if modified_repo_name in approvals:
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

                    project_inputs = approvals[modified_repo_name]['inputs']

                    for project_input in project_inputs:
                        tag_message += f'\n\n{project_input}: {project_inputs[project_input]}'

                    repo.updateTag(tag_name, tag_ref, tag_message)
                    # TODO: Consider logging if the tag already existed and is being updated


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
    def _get_source_branch(args):
        source_branch = args["--source"]

        if not source_branch:
            source_branch = utility.userInput(f'Please enter the name of the branch being approved: ')

            if not source_branch:
                logging.error(f'GRAPE: ERROR: Source branch is required.')
                exit(1)

        return source_branch

    @staticmethod
    def _is_eligible_reviewer(user_name, rule):
        for eligible_reviewer in rule['eligibleReviewers']:
            if re.fullmatch(eligible_reviewer, user_name):
                return True

        return False