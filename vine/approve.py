import logging
from vine import CodeReviewsFactory
from vine import config_parser_global
from vine import grapeGit as git
from vine import review as review_mod
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
            self._rules = review_mod.parseReviewRules()

        return self._rules

    @property
    def active_rule_names(self):
        if self._active_rule_names is None:
            self._active_rule_names = [rule_name for rule_name in self.rules if self.rules[rule_name]['active']]

        return self._active_rule_names

    @log_wrapper
    def execute(self, args):
        # Authenticate to git hosting service
        user_name = args["--user"] or utility.getUserName()
        verify = True if args["--verifySSL"].lower() == "true" else False
        logging.info(f"Logging onto {args['--codeReviewsURL']}")

        codeReviews = CodeReviewsFactory.makeCodeReviews(
            user_name,
            url=args["--codeReviewsURL"],
            verify=verify,
            port=int(args["--ssh_pat_port"]),
            ssh_path=args["--ssh_pat_url"],
            workspace_dir=self.workspace_dir
        )

        # Get and validate review rule
        rule_name = args['--rule']

        if not rule_name:
            rule_name = utility.userInput(f'Please enter a review rule name ({", ".join(self.active_rule_names)}): ')

        if rule_name not in self.rules:
            logging.error(f'GRAPE: ERROR: Review rule "{rule_name}" is invalid ({", ".join(self.active_rule_names)}).')
            exit(1)

        rule = self.rules[rule_name]

        if not rule['active']:
            logging.error(f'GRAPE: ERROR: Review rule "{rule_name}" is inactive ({", ".join(self.active_rule_names)}).')
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

        # Get list of repositories to which the review rule applies
        review_rule_repositories = rule['repositories']

        config = config_parser_global.grapeConfig()

        project_name = args["--project"]
        repo_name = args["--repo"]
        source_branch = args["--source"]
        target_branch = args["--target"]

        if not target_branch and source_branch:
            target_branch = config.getPublicBranchFor(source_branch)

        print(f"project_name: {project_name}")
        print(f"repo_name: {repo_name}")
        print(f"source_branch: {source_branch}")
        print(f"target_branch: {target_branch}")
        sys.exit(1)

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

        ## NESTED SUBPROJECT REPOS
        subprojects = config_parser_user.getAllNestedSubprojects(workspaceDir=self.workspace_dir)
        subproject_prefixes = [config.get(f"nested-{name}", "prefix") for name in subprojects]

        for subproject, prefix in zip(subrojects, subproject_prefixes):
            prefix_path = os.path.join(self.workspace_dir, prefix)
            listOfRepoBranchArgTuples.append((prefix_path,
                                              branch,
                                              [{"codeReviews":codeReviews,
                                                "isSubmodule": False,
                                                "isNested": True,
                                                "args": args,
                                                "target_branch": target_branch,
                                                "project": subproject}]))

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
        git_service = kwargs["codeReviews"]
        isSubmodule = kwargs["isSubmodule"]
        isNested = kwargs["isNested"]
        review_args = kwargs["args"]
        target_branch = kwargs["target_branch"]
        project = kwargs["project"]

        if isNested:
            repo = CodeReviewsFactory.repoFromNestedSubprojectName(git_service, project)
        elif isSubmodule:
            repo = CodeReviewsFactory.repoFromSubmodulePath(git_service, project)
        else:
            repo = CodeReviewsFactory.repoObject(git_service)

        newRequest = postPullRequest(codeReview_repo, title, branch, target_branch, descr, reviewers, reviewer_list, non_approver_list, review_args, repo)
        if newRequest:
            return newRequest.link()
        else:
            return ""

    def setDefaultConfig(self, config):
        config.ensureSection(self.SECTION_PROJECT)
        config.set(self.SECTION_PROJECT, "codeReviewsURL", "https://your.host.org/gitlab/or/bitbucket")
        config.set(self.SECTION_PROJECT, "verifySSL", "True")
        config.set(self.SECTION_PROJECT, "name", "My unnamed project")
        config.ensureSection(self.SECTION_REPO)
        config.set(self.SECTION_REPO, "ssh_pat_url", "git@gitlab.your.host.org")
        config.set(self.SECTION_REPO, "ssh_pat_port", "7999")
        config.set(self.SECTION_REPO, "name", "My unnamed repo")

    def parseReviewRules():
        """
        Parses the global GRAPE config file and returns a dictionary of review rules.

        :return: A dictionary where each key is a review rule name and the value is a dictionary representing the rule
        """
        reviewRules = {}

        # Names reserved by grape
        reservedReviewRuleNames = ['grape']
        reservedReviewRuleLabels = [Gitlab.GRAPE_GITLAB_APPROVAL_RULE_NAME]

        # Count the number of active review rules
        numActiveRules = 0

        # Extract the rule names from the [review] section
        config = config_parser_global.grapeConfig()

        reviewSectionName = "review"

        if config.has_section(reviewSectionName):
            if config.has_option(reviewSectionName, "rules"):
                reviewRuleNames = config.get(reviewSectionName, "rules").split()

                for reviewRuleName in reviewRuleNames:
                    if reviewRuleName in reservedReviewRuleNames:
                        logging.error(f'GRAPE: ERROR: The review rule name "{reviewRuleName}" is reserved by GRAPE.')
                        exit(1)

                    sectionName = f"{reviewSectionName}-{reviewRuleName}"

                    if not config.has_section(sectionName):
                        logging.error(f'GRAPE: ERROR: Global config section "{sectionName}" is missing.')
                        exit(1)

                    # Default to active
                    active = True

                    if config.has_option(sectionName, "active"):
                        active = config.getboolean(sectionName, "active")

                    if active:
                        numActiveRules += 1

                    # Provide a reasonable default for the rule label
                    label = f"GRAPE: {reviewRuleName} review"

                    if config.has_option(sectionName, "label"):
                        label = config.get(sectionName, "label")

                    if label in reservedReviewRuleLabels:
                        logging.error(f'GRAPE: ERROR: The review rule label "{label}" is reserved by GRAPE.')
                        exit(1)

                    # Default to one reviewer
                    minNumReviewers = 1

                    if config.has_option(sectionName, "minnumreviewers"):
                        minNumReviewers = config.getint(sectionName, "minnumreviewers")

                    # Default to all reviewers
                    eligibleReviewers = [".+"]

                    if config.has_option(sectionName, "eligiblereviewers"):
                        eligibleReviewers = config.get(sectionName, "eligiblereviewers").split()

                    # Default to all repositories
                    repositories = [".+"]

                    if config.has_option(sectionName, "repositories"):
                        repositories = config.get(sectionName, "repositories").split()

                    # Add the rule
                    reviewRules[reviewRuleName] = {
                        "active": active,
                        "label": label,
                        "minNumReviewers": minNumReviewers,
                        "eligibleReviewers": eligibleReviewers,
                        "repositories": repositories
                    }

        # Add the GRAPE review rule. It will be active only if the user has
        # not specified any rules.
        if not reviewRules:
            grapeReviewRuleActive = True
            numActiveRules += 1
        else:
            grapeReviewRuleActive = False

        reviewRules.update(getGrapeReviewRule(grapeReviewRuleActive))

        if numActiveRules == 0:
            logging.error(f'GRAPE: ERROR: At least one review rule must be active.')
            exit(1)

        return reviewRules