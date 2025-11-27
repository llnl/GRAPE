import logging
from vine import CodeReviewsFactory
from vine import config_parser_global
from vine import config_parser_user
from vine import grapeGit as git
from vine import multi_repo_cmd_launcher
from vine import review
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

    @property
    def rules(self):
        if self._rules is None:
            self._rules = review.parseReviewRules()

        return self._rules

    @property
    def active_rule_names(self):
        if self._active_rule_names is None:
            self._active_rule_names = [rule_name for rule_name in self.rules if self.rules[rule_name]['active']]

        return self._active_rule_names

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

        # Get and validate review rule
        rule_name = args['--rule']

        if not rule_name:
            rule_name = utility.userInput(f'Please enter a review rule name ({", ".join(self.active_rule_names)}): ')

        if rule_name not in self.rules:
            logging.error(f'GRAPE: ERROR: Review rule "{rule_name}" not found. Active rules: {", ".join(self.active_rule_names)}.')
            exit(1)

        rule = self.rules[rule_name]

        if not rule['active']:
            logging.error(f'GRAPE: ERROR: Review rule "{rule_name}" is inactive. Active rules: {", ".join(self.active_rule_names)}.')
            exit(1)

        # Check if the user is allowed to approve
        eligible_reviewers = rule['eligibleReviewers']
        eligible = False

        for eligible_reviewer in eligible_reviewers:
            if re.fullmatch(eligible_reviewer, user_name):
                eligible = True
                break

        if not eligible:
            logging.error(f'GRAPE: ERROR: User "{user_name}" cannot approve review rule "{rule_name}".')
            exit(1)

        # Get the list of repositories to which the review rule applies
        rule_repositories = rule['repositories']

        # Get the command for generating an approval description
        rule_inputs = rule['inputs']

        # Get config
        config = config_parser_global.grapeConfig()

        # Get repository and containing project/group
        project_name = args["--project"]
        repo_name = args["--repo"]

        # Get and validate source branch
        source_branch = args["--source"]

        if not source_branch:
            source_branch = utility.userInput(f'Please enter the name of the branch being approved: ')

            if not source_branch:
                logging.error(f'GRAPE: ERROR: Source branch is required.')
                exit(1)

        # Get target branch
        target_branch = args["--target"]

        if not target_branch:
            target_branch = config.getPublicBranchFor(source_branch)

        # Get modified repositories

        """
        # Assemble arguments for parallel execution
        listOfRepoBranchArgTuples=[]

        ## Top Repo
        listOfRepoBranchArgTuples.append((repo_name,
                                          source_branch,
                                          [{"codeReviews": codeReviews,
                                            "isSubmodule": False,
                                            "isNested": False,
                                            "args": args,
                                            "target_branch": target_branch,
                                            "project": submodule}]))
        """

        listOfRepoBranchArgTuples = []
        inputs = {}

        # Top level repository
        rule_applies = False

        for rule_repository in rule_repositories:
            if re.fullmatch(rule_repository, repo_name):
                rule_applies = True
                break

        approval_granted = False
        approval_description = ''

        if rule_applies:
            logging.info(f'Applying review rule "{rule_name}" to top level repository "{repo_name}".')
            # TODO: Show the latest commit hash
            approval_granted = utility.userInput(f'I approve the changes on branch "{source_branch}".', default='y')

            if approval_granted:
                for rule_input in rule_inputs:
                    if repo_name not in inputs:
                        inputs[repo_name] = {}

                    inputs[repo_name][rule_input] = utility.userInput(f'{rule_input}: ')

        listOfRepoBranchArgTuples.append((repo_name,
                                          source_branch,
                                          [{'git_service': codeReviews,
                                            'top': True,
                                            'submodule': False,
                                            'subproject': False,
                                            'rule': rule,
                                            'approve': approval_granted,
                                            'inputs': inputs,
                                            'args': args,
                                            'target_branch': target_branch,
                                            'project': repo_name}]))

        # Submodule repositories
        modified_submodules = git.getModifiedSubmodules(self.workspace_dir, target_branch, source_branch, includeAdded=True)
        submodule_branch_mappings = config.getMapping(self.SECTION_WORKSPACE, "submoduleTopicPrefixMappings")
        source_branch_prefix = git.branchPrefix(source_branch)
        submodule_target_branch = submodule_branch_mappings[source_branch_prefix]

        for submodule in modified_submodules:
            # Check if rule applies to submodule
            rule_applies = False

            for rule_repository in rule_repositories:
                if re.fullmatch(rule_repository, submodule):
                    rule_applies = True
                    break

            approval_granted = False
            approval_description = ''

            if rule_applies:
                logging.info(f'Applying review rule "{rule_name}" to submodule "{submodule}".')
                # TODO: Show the latest commit hash
                approval_granted = utility.userInput(f'I approve the changes on branch "{source_branch}".', default='y')

                if approval_granted:
                    for rule_input in rule_inputs:
                        if submodule not in inputs:
                            inputs[submodule] = {}

                        inputs[submodule][rule_input] = utility.userInput(f'{rule_input}: ')

            listOfRepoBranchArgTuples.append((submodule,
                                              source_branch,
                                              [{'git_service': codeReviews,
                                                'top': False,
                                                'submodule': True,
                                                'subproject': False,
                                                'rule': rule,
                                                'approve': approval_granted,
                                                'inputs': inputs,
                                                'args': args,
                                                'target_branch': submodule_target_branch,
                                                'project': submodule}]))

        # Subproject repositories
        modified_subprojects = config_parser_user.getAllModifiedNestedSubprojects(
            f'origin/{target_branch}', f'origin/{source_branch}', workspaceDir=self.workspace_dir)

        # For testing
        modified_subprojects = ['test_subproject_1', 'test_subproject_2']

        for subproject in modified_subprojects:
            # Check if rule applies to subproject
            rule_applies = False

            for rule_repository in rule_repositories:
                if re.fullmatch(rule_repository, subproject):
                    rule_applies = True
                    break

            approval_granted = False
            approval_description = ''

            if rule_applies:
                logging.info(f'Applying review rule "{rule_name}" to subproject "{subproject}".')
                # TODO: Show the latest commit hash
                approval_granted = utility.userInput(f'I approve the changes on branch "{source_branch}".', default='y')

                if approval_granted:
                    for rule_input in rule_inputs:
                        if subproject not in inputs:
                            inputs[subproject] = {}

                        inputs[subproject][rule_input] = utility.userInput(f'{rule_input}: ')

            listOfRepoBranchArgTuples.append((config.get(f'nested-{subproject}', 'prefix'),
                                              source_branch,
                                              [{'git_service': codeReviews,
                                                'top': False,
                                                'submodule': False,
                                                'subproject': True,
                                                'rule': rule,
                                                'approve': approval_granted,
                                                'inputs': inputs,
                                                'args': args,
                                                'target_branch': target_branch,
                                                'project': subproject}]))

        launcher = multi_repo_cmd_launcher.MultiRepoCommandLauncher(approve, listOfRepoBranchArgTuples=listOfRepoBranchArgTuples, workspace_dir=self.workspace_dir)
        launcher.launchFromWorkspaceDir(handleMRE=handleApproveMRE)

    def setDefaultConfig(self, config):
        config.ensureSection(self.SECTION_PROJECT)
        config.set(self.SECTION_PROJECT, "codeReviewsURL", "https://your.host.org/gitlab/or/bitbucket")
        config.set(self.SECTION_PROJECT, "verifySSL", "True")
        config.set(self.SECTION_PROJECT, "name", "My unnamed project")
        config.ensureSection(self.SECTION_REPO)
        config.set(self.SECTION_REPO, "ssh_pat_url", "git@gitlab.your.host.org")
        config.set(self.SECTION_REPO, "ssh_pat_port", "7999")
        config.set(self.SECTION_REPO, "name", "My unnamed repo")

def approve(repo, branch, args, *, workspace_dir):
    kwargs = args[0]
    git_service = kwargs['git_service']
    top = kwargs['top']
    submodule = kwargs['submodule']
    subproject = kwargs['subproject']
    rule = kwargs['rule']
    approval = kwargs['approve']
    inputs = kwargs['inputs']
    args = kwargs['args']
    target_branch = kwargs["target_branch"]
    project = kwargs["project"]

    # Build rule section for merge request description
    rule_section = ''

    if inputs:
        rule_section = f'# {rule["label"]}'

        for key in sorted(inputs.keys()):
            rule_section += f'\n\n## {key}'
            project_inputs = inputs[key]

            for project_input in sorted(project_inputs.keys()):
                rule_section += f'\n\n{project_input}: {project_inputs[project_input]}'

    # Update merge request description
    if subproject:
        repo = CodeReviewsFactory.repoFromNestedSubprojectName(git_service, project)
    elif submodule:
        repo = CodeReviewsFactory.repoFromSubmodulePath(git_service, project)
    else:
        repo = CodeReviewsFactory.repoObject(git_service)

    review_request = repo.getOpenPullRequest(branch, target_branch)

    if not review_request:
        # Log warning message
        return

    if 'update_description' in rule['approve_actions']:
        current_description = review_request.description().decode("utf-8").strip()

        # Pattern:
        # - Match "# {section_name}" at line start
        # - Capture everything until next top-level header ("# " at line start) or end of string
        pattern = (
            rf'(?m)^# {re.escape(rule["label"])}\s*\n'    # Top-level section header
            r'(.*?)'                                      # Non-greedy capture
            r'(?=^# [^\n]*|\Z)'                           # Stop at next top-level header or end of string
        )

        def repl(match):
            # Replace section and preserve new lines before next section
            # If there is no section after this one, the extra new lines
            # will be stripped off anyway.
            return f'{rule_section}\n\n'

        updated_description = re.sub(pattern, repl, current_description, flags=re.DOTALL|re.MULTILINE).rstrip()
        review_request.update(review_request.version(), description=updated_description)

    # Approve reviewed branch
    if 'approve' in rule['approve_actions']:
        try:
            review_request.approve()
        except:
            logging.error(f'GRAPE: ERROR: Unable to approve merge request.')

    # Tag reviewed branch
    if 'tag' in rule['approve_actions']:
        tag_name = f'{rule["name"]}_{review_request.iid()}'
        # TODO: Get specific commit
        tag_ref = branch
        tag_message = rule['label']

        if project in inputs:
            project_inputs = inputs[project]

            for project_input in project_inputs:
                tag_message += f'\n\n{project_input}: {project_inputs[project_input]}'

        repo.updateTag(tag_name, tag_ref, tag_message)
        # TODO: Consider logging if the tag already existed and is being updated

    return

def handleApproveMRE(mre):
    for e in mre.exceptions():
        raise e