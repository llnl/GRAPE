import logging
import os
from vine import config_parser_global
from vine import Gitlab
from vine import grapeGit as git
from vine import utility
from vine.option import Option
from vine.workspace_dir_handler import WorkspaceDirHandler
from vine.vine_logging import log_wrapper

class GitlabAdmin(Option, WorkspaceDirHandler):
    """
    grape gitlab-admin 
    Perform gitlab administration tasks.
    Usage: grape-gitlab-admin [--dry]
                              [--verbose]
                              [--setProtectedBranches]
                              [--disableLFS]
                              [--disableSubprojectCI]
                              [--user=<userName>]
                              [--codeReviewsURL=<url>]
                              [--verifySSL=<bool>]
                              [--project=<prj>]
                              [--ssh_pat_url=<url>]
                              [--ssh_pat_port=<int>]

    Options:
        --dry                       Do not actually perform administration tasks, just perform a dry run.
        --verbose                   Print information about unaffected repos
        --setProtectedBranches      Protect public branches from force pushes (and remove all other protections)
        --disableLFS                Disable LFS in main project and all subprojects.
        --disableSubprojectCI       Disable CI in all subprojects.
        --user=<userName>           Your Gitlab user name.
        --codeReviewsURL=<url>      The code review platform url, e.g. https://your.host.org/gitlab.
                                    [default: .grapeconfig.project.codeReviewsURL]
        --verifySSL=<bool>          Set to False to ignore SSL certificate verification issues.
                                    [default: .grapeconfig.project.verifySSL]
        --project=<prj>             The project key part of the codeReviews url, e.g. the "GRP" in
                                    https://your.host.org/gitlab/projects/GRP/repos/grape/browse.
                                    [default: .grapeconfig.project.name]
        --ssh_pat_url=<url>         SSH URL for generating Personal Access Tokens to authenticate into a Code Review service's
                                    REST API.
                                    [default: .grapeconfig.repo.ssh_pat_url]
        --ssh_pat_port=<int>        Port number to issue ssh command over to generate a Personal Access Token for authentication
                                    into a Code Review service's REST API.
                                    [default: .grapeconfig.repo.ssh_pat_port]

    """
    def __init__(self):
        super(GitlabAdmin, self).__init__()
        self._key = "gitlab-admin"
        self._section = "Other"

    def description(self):
        return "Gitlab administration."

    # Returns a dictionary of repo => list of public branch names
    # for each repo in the project that is in the grape project
    def getGrapeReposAndPublicBranches(self, project, verbose):
        grapeRepos = {}

        config = config_parser_global.grapeConfig()

        # List of repos in gitlab project
        reponames = project.repolist()
        projectname = project.name()

        # Figure out the public branches
        publicbranches = config.getPublicBranchList()
        branchMapping = config.getMapping("workspace", "submodulepublicmappings")
        submodule_publicbranches = []
        for branch in publicbranches:
           submodule_publicbranches.append(branchMapping[branch])

        # Determine which repos are registered with grape
        outer = os.path.splitext(os.path.basename(config["repo"]["url"]))[0]
        try:
           found = [item.lower() for item in reponames].index(outer.lower())
           del reponames[found]
           grapeRepos[outer] = publicbranches
        except ValueError:
           if verbose:
              logging.info(f"Outer level repo {outer} is not in gitlab project {projectname}")

        grapeRepos = {outer : publicbranches}
        for name in config.getAllNestedSubprojects():
           url = config[f"nested-{name}"]["url"]
           grapeReponame = os.path.splitext(os.path.basename(url))[0]
           try:
              found = [item.lower() for item in reponames].index(grapeReponame.lower())
              del reponames[found]
              grapeRepos[grapeReponame] = publicbranches
           except ValueError:
              if verbose:
                 logging.info(f"Nested subproject {grapeReponame} is not in gitlab project {projectname}")
              
        for path,url in git.getAllSubmoduleURLMap(execution_path=self.workspace_dir).items():
           grapeReponame = os.path.splitext(os.path.basename(url))[0]
           try:
              found = [item.lower() for item in reponames].index(grapeReponame.lower())
              del reponames[found]
              grapeRepos[grapeReponame] = submodule_publicbranches
           except ValueError:
              if verbose:
                 logging.info(f"Submodule {grapeReponame} is not in gitlab project {projectname}")

        if verbose:
            logging.info(f"The following repos in gitlab project {projectname} are not registered with grape:\n{reponames}")

        return grapeRepos
         
    @log_wrapper
    def execute(self, args):
        config = config_parser_global.grapeConfig()
        name = args["--user"]
        if not name:
            name = utility.getUserName()
        verify = True if args["--verifySSL"].lower() == "true" else False

        grape_gitlab = Gitlab.GrapeGitlabAdapter(name, url=args["--codeReviewsURL"],
                                                 verify=verify,
                                                 port=int(args["--ssh_pat_port"]),
                                                 ssh_path = args["--ssh_pat_url"],
                                                 workspace_dir=self.workspace_dir
                                                )
        projectname = args["--project"]
        try:
           # Only allow admin tasks to be performed if access level is maintainer or above
           project = grape_gitlab.project(projectname, min_access_level=40)
        except:
           logging.info(f"Project {projectname} does not exist or you do not have admin privileges!")
           return False
           
        task_completed = False

        grapeRepos = self.getGrapeReposAndPublicBranches(project=project, verbose=args["--verbose"])

        for reponame,public in grapeRepos.items():
            repo = project.repo(reponame)
            logging.info(f"Repository {reponame}")

            if args["--setProtectedBranches"]:
               for branch in public:
                  # Set to allow developers+maintainers to merge and push, but not to force push
                  replaced = repo.setProtectedBranch(branch, 30, 30, False)
                  if replaced:
                     logging.info(f"\tUpdating protected branch {branch}")
                  else:
                     logging.info(f"\tProtecting branch {branch}")
               task_completed = True

            if args["--disableLFS"]:
               logging.info("\tDisabling LFS...")
               if repo.project.lfs_enabled:
                  if args["--dry"]:
                     logging.info("\t[Dry run]: LFS not disabled")
                  else:
                     repo.project.lfs_enabled = False
                     repo.project.save()
               else:
                  logging.info("\tPreviously disabled")
               task_completed = True

            if args["--disableSubprojectCI"]:
               topRepo = project.repo(config.get(Option.SECTION_REPO, "name"))
               if repo.project.name != topRepo.project.name:
                  if repo.project.builds_access_level != "disabled":
                     logging.info("\tDisabling CI...")
                     if args["--dry"]:
                        logging.info("\t[Dry run]: CI not disabled")
                     else:
                        repo.project.builds_access_level = "disabled"
                        repo.project.save()
                  else:
                     logging.info("\tPreviously disabled")
               task_completed = True

        if not task_completed:
           logging.info("No gitlab-admin task specified!")
           return False
        
        return True

    def setDefaultConfig(self, config):
        config.ensureSection(self.SECTION_PROJECT)
        config.set(self.SECTION_PROJECT, "codeReviewsURL", "https://your.host.org/gitlab/or/bitbucket")
        config.set(self.SECTION_PROJECT, "verifySSL", "True")
        config.set(self.SECTION_PROJECT, "name", "My unnamed project")
        config.set(self.SECTION_REPO, "ssh_pat_url", "git@gitlab.your.host.org")
        config.set(self.SECTION_REPO, "ssh_pat_port", "7999")
