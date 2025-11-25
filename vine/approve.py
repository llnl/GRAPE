import logging
from vine import CodeReviewsFactory
from vine import config_parser_global
from vine import grapeGit as git
from vine import review as review_mod
from vine.option import Option
from vine.workspace_dir_handler import WorkspaceDirHandler
from vine.vine_logging import log_wrapper
from vine import utility
import sys

class Approve(Option, WorkspaceDirHandler):
    """
    grape approve
    Manage approval for a pull/merge request.
    Usage: grape-approve [--source=<topicBranch>]
                         [--target=<publicBranch>]
                         [--project=<prj>]
                         [--repo=<repo>]
                         [--user=<userName>]
                         [--codeReviewsURL=<url>]
                         [--verifySSL=<bool>]
                         [--ssh_pat_url=<url>]
                         [--ssh_pat_port=<int>]

    Options:
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
        if "gitlab" not in args["--codeReviewsURL"]:
            logging.info("The grape approve command is currently only implemented for GitLab.")
            return False

        name = args["--user"] or utility.getUserName()
        verify = True if args["--verifySSL"].lower() == "true" else False

        logging.info(f"Logging onto {args['--codeReviewsURL']}")

        codeReviews = CodeReviewsFactory.makeCodeReviews(
            name,
            url=args["--codeReviewsURL"],
            verify=verify,
            port=int(args["--ssh_pat_port"]),
            ssh_path=args["--ssh_pat_url"],
            workspace_dir=self.workspace_dir
        )

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

    def setDefaultConfig(self, config):
        config.ensureSection(self.SECTION_PROJECT)
        config.set(self.SECTION_PROJECT, "codeReviewsURL", "https://your.host.org/gitlab/or/bitbucket")
        config.set(self.SECTION_PROJECT, "verifySSL", "True")
        config.set(self.SECTION_PROJECT, "name", "My unnamed project")
        config.ensureSection(self.SECTION_REPO)
        config.set(self.SECTION_REPO, "ssh_pat_url", "git@gitlab.your.host.org")
        config.set(self.SECTION_REPO, "ssh_pat_port", "7999")
        config.set(self.SECTION_REPO, "name", "My unnamed repo")
