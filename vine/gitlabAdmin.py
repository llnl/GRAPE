from vine.option import Option
from vine.vine_logging import log_wrapper
from vine import Gitlab

class GitlabAdmin(Option):
    """
    grape gitlab-admin 
    Perform gitlab administration tasks.

    Usage: grape-gitlab-admin [--removeProtectedBranches]
    Options:
        --removeProtectedBranches   Remove protected branches in all subprojects.

    """
    def __init__(self):
        super(GitlabAdmin, self).__init__()
        self._key = "gitlab-admin"
        self._section = "Other"

    def description(self):
        return "Gitlab administration."

    @log_wrapper
    def execute(self, args):
        grape_gitlab = GrapeGitlabAdapter(workspace_dir=os.getcwd())
        logging.info(f"\nPROJECT:{p}")
        project = grape_gitlab.project("GRP")
        reponames = project.repolist()
        for reponame in reponames:
            logging.info(f" REPONAME{reponame}")
            try:
                repo = project.repo(reponame)
                for pull in repo.pullRequests(state="open"):
                    logging.info(f"  TITLE:     {pull.title()}")
                    logging.info(f"  STATE:     {pull.state()}")
                    logging.info(f"  AUTHOR:    {pull.author()}")
                    logging.info(f"  AUTHORNAME:{pull.authorName()}")
                    logging.info(f"  DATE:      {pull.date()}")
                    logging.info(f"  REVIEWERS: {pull.reviewers()}")
                    logging.info(f"  FROM:      {pull.fromRef()}")
                    logging.info(f"  TO:        {pull.toRef()}")
                    logging.info(f"  DESC:      {pull.description()}")
                    logging.info(f"  APPROVED:  {pull.approved()}")
                    logging.info(f"  LINK:      {pull.link()}\n")
                logging.info("GETTING OPEN PULL REQUEST")
                pull = repo.getOpenPullRequest("feature/probinso/gitlab_support","develop")
                logging.info(f"  TITLE:     {pull.title()}")
                logging.info(f"  REVIEWERS: {pull.reviewers()}")
                logging.info(f"  APPROVED:  {pull.approved()}")

            except:
                pass
        return True

    def setDefaultConfig(self, config):
        config.ensureSection(self.SECTION_PROJECT)
        config.set(self.SECTION_PROJECT, "codeReviewsURL", "https://your.host.org/gitlab/or/bitbucket")
        config.set(self.SECTION_PROJECT, "verifySSL", "True")
        config.set(self.SECTION_PROJECT, "name", "My unnamed project")
        config.set(self.SECTION_REPO, "ssh_pat_url", "git@gitlab.your.host.org")
        config.set(self.SECTION_REPO, "ssh_pat_port", "7999")
