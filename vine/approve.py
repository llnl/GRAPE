import logging
from vine import CodeReviewsFactory
from vine import config_parser_global
from vine import config_parser_user
from vine import grapeGit as git
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

        ##  Submodule Repos
        submodules = git.getAllSubmodules(self.workspace_dir)

        # update target branch based off of branch prefix
        submodule_branch_mappings = config.getMapping(self.SECTION_WORKSPACE, "submoduleTopicPrefixMappings")
        # determine branch prefix
        source_branch_prefix = git.branchPrefix(source_branch)
        submodule_target_branch = submodule_branch_mappings[prefix]

        for submodule in submodules:
            if not submodule:
                continue

            listOfRepoBranchArgTuples.append((submodule,
                                              source_branch,
                                              [{"codeReviews": codeReviews,
                                                "isSubmodule": True,
                                                "isNested": False,
                                                "args": args,
                                                "target_branch": submodule_target_branch,
                                                "project": submodule}]))
        """

        inputs = {}

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

            print(inputs)
            sys.exit(0)

            listOfRepoBranchArgTuples.append((prefix_path,
                                              branch,
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

        sys.exit(1)

        launcher = multi_repo_cmd_launcher.MultiRepoCommandLauncher(
            approve,
            skipSubmodules=False,
            runInSubprojects=True,
            runInOuter=True,
            workspace_dir=self.workspace_dir,
            globalArgs=args)

        retvals = launcher.launchFromWorkspaceDir(handleMRE=handlePushMRE) 

        # load pull request if it already exists
        wsRepo = codeReviews.project(project_name).repo(repo_name)
        request = getReposPullRequest(wsRepo, source_branch, target_branch, args)

        if not request:
            logging.info(f"No open merge request found for {source_branch} -> {target_branch} in {project_name}/{repo_name}.")
            return False

        try:
            request.approve()
            logging.info(f"Approved merge request: {request.link()}")
            return True
        except Exception as e:
            logging.info(f"Failed to approve merge request: {e}")
            return False

    def approve(repo_name, branch, args, *, workspace_dir):
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
        elif isSubmodule:
            repo = CodeReviewsFactory.repoFromSubmodulePath(git_service, project)
        else:
            repo = CodeReviewsFactory.repoObject(git_service)

        review_request = repo.getOpenPullRequest(branch, target_branch)

        if not review_request:
            # Log warning message
            pass

        if rule_section:
            description = f'{review_request.description()}\n\n{rule_section}'
            review_request.update(review_request.version(), description=description)

        # Approve reviewed branch
        action_approve = 'approve_actions' in rule and 'approve' in rule['approve_actions']:
        
        if action_approve:
            review_request.approve()

        # Tag reviewed branch
        # TODO: Get specific commit
        action_tag = 'approve_actions' in rule and 'tag' in rule['approve_actions']

        if action_tag:
            tag_name = f'{rule['id']}_{review_request.iid()}'
            tag_ref = branch
            tag_message = ''

            if project in inputs:
                project_inputs = inputs[project]

                for project_input in project_inputs:
                    tag_message += f'\n\n{project_input}: {project_inputs[project_input]}'

            repo.updateTag(tag_name, tag_ref, tag_message)
            # TODO: Consider logging if the tag already existed and is being updated

        return

    def setDefaultConfig(self, config):
        config.ensureSection(self.SECTION_PROJECT)
        config.set(self.SECTION_PROJECT, "codeReviewsURL", "https://your.host.org/gitlab/or/bitbucket")
        config.set(self.SECTION_PROJECT, "verifySSL", "True")
        config.set(self.SECTION_PROJECT, "name", "My unnamed project")
        config.ensureSection(self.SECTION_REPO)
        config.set(self.SECTION_REPO, "ssh_pat_url", "git@gitlab.your.host.org")
        config.set(self.SECTION_REPO, "ssh_pat_port", "7999")
        config.set(self.SECTION_REPO, "name", "My unnamed repo")