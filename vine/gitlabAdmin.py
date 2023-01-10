import configparser
import logging
import os
from vine import config_parser_base
from vine import config_parser_global
from vine import config_parser_workspace
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
                              [--createRepo=<name> [--owner=<user>]]
                              [--setProtectedBranches]
                              [--setKeepMRApprovals]
                              [--disableLFS]
                              [--disableSubprojectCI]
                              [--requirePipelineSuccess]
                              [--allRepoSettings]
                              [--scheduledPipelines=[list|add|delete|take|update]
                               [--desc=<description>] [--ref=<ref>] [--cron=<cron>] [--timezone=<timezone>] [--active=<bool>] ]
                              [--runJob=<jobName> | --startJob=<jobName>]
                              [--pid=<id>]
                              [--checkJob=<jobName>]
                              [--runningJobs=[list|log]]
                              [--user=<userName>]
                              [--codeReviewsURL=<url>]
                              [--verifySSL=<bool>]
                              [--project=<prj>]
                              [--repo=<repo>]
                              [--branch=<branch>]
                              [--ssh_pat_url=<url>]
                              [--ssh_pat_port=<int>]

    Options:
        --dry                       Do not actually perform administration tasks, just perform a dry run.
        --verbose                   Print information about unaffected repos.
        --createRepo=<name>         Create new empty repo in project with given name. All relevant repo settings will be
                                    set for the new repo (per --allRepoSettings) except protected branches will not be set.
        --owner=<user>              Add user as owner of newly created repo.
        --setProtectedBranches      Protect public branches from force pushes (and remove all other protections).
        --setKeepMRApprovals        Keep merge request approvals after push.
        --disableLFS                Disable LFS in main project and all subprojects.
        --disableSubprojectCI       Disable CI in all subprojects.
        --requirePipelineSuccess    Require pipeline success for merge button.
        --allRepoSettings           Set all administrative repo settings. This includes:
                                       setProtectedBranches
                                       setKeepMRApprovals
                                       disableLFS
                                       disableSubprojectCI
                                       requirePipelineSuccess
        --scheduledPipelines=<op>   Manage scheduled pipelines. <op> is one of
                                       list   : List scheduled pipelines
                                       add    : Add a new scheduled pipeline
                                       delete : Delete an existing scheduled pipeline that you own
                                       update : Update an existing scheduled pipeline that you own
                                       take   : Take ownership of an existing scheduled pipeline
                                    Note: scheduled pipeline variables do not appear to be exposed properly through the REST API
                                    (https://gitlab.com/gitlab-org/gitlab/-/issues/250850).
        --runJob=<jobName>          Run job with given name.
                                    Pipeline identifier must be specified using --pid.
        --startJob=<jobName>        Run job with given name. Will not run job if already succeeded.
                                    Pipeline identifier must be specified using --pid.
        --checkJob=<jobName>        Check most recently finished jobs with given name. Returns list of pipeline identifiers
                                    corresponding to --pid.
        --runningJobs=<op>          Show running jobs that you own.  <op> is one of
                                       list   : List running jobs
                                       log    : Show logs for running jobs
        --pid=<id>                  Identifier for pipeline. Required, and only allowed for
                                    --scheduledPipelines when <op> is 'delete','take', or 'update' or --runPipelineJob.
        --desc=<description>        New description for scheduled pipeline. Only allowed when <op> is 'add' or 'update'.
        --cron=<cron>               New cron entry for scheduled pipeline. Only allowed when <op> is 'add' or 'update'.
        --timezone=<timezone>       New cron timezone for scheduled pipeline. Only allowed when <op> is 'add' or 'update'.
                                    e.g. 'America/Los_Angeles', 'Etc/UTC'
        --ref=<ref>                 Branch reference for scheduled pipeline. Only allowed when <op> is 'add' or 'update'.
                                    e.g. 'develop', 'refs/heads/bugfix/mybranch'
        --active=<bool>             Whether the scheduled pipeline should be active. Only allowed when <op> is 'add' or 'update'.
        --user=<userName>           Your Gitlab user name.
        --codeReviewsURL=<url>      The code review platform url, e.g. https://your.host.org/gitlab.
                                    [default: .grapeconfig.project.codeReviewsURL]
        --verifySSL=<bool>          Set to False to ignore SSL certificate verification issues.
                                    [default: .grapeconfig.project.verifySSL]
        --project=<prj>             The project key part of the codeReviews url, e.g. the "GRP" in
                                    https://your.host.org/gitlab/projects/GRP/repos/grape/browse.
        --repo=<repo>               The top level repo key part of the codeReviews url, e.g. the "grape" in
                                    https://your.host.org/gitlab/projects/GRP/repos/grape/browse.
        --branch=<branch>           Branch in top level repo for checking .grapeconfig.
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
    def getGrapeReposAndPublicBranches(self, project, topreponame, initialbranch, verbose):
        grapeRepos = {}

        toprepo = project.repo(topreponame, min_access_level=40)
        grapeConfig = toprepo.project.files.raw(file_path=".grapeconfig", ref=initialbranch).decode('utf-8')
        config = config_parser_base.GrapeConfigParserBase(configString=grapeConfig)

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
        if "gitlab" not in args["--codeReviewsURL"]:
            logging.info("gitlab-admin should only be used with GitLab.")
            return False

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
        topreponame = args["--repo"]
        initialbranch = args["--branch"]

        # Get defaults from current workspace
        grape_config = config_parser_global.grapeConfig()
        if not projectname:
           projectname = utility.userInput("Project (group) name:", default=grape_config.get("project", "name"))
        if not topreponame:
           topreponame = utility.userInput("Outer level repo (project) name:", default=grape_config.get("repo", "name"))
        if not initialbranch:
           initialpublic = config_parser_workspace.GrapeConfigParserWorkspace(self.workspace_dir).getPublicBranchFor(git.currentBranch(execution_path=self.workspace_dir))
           initialbranch = utility.userInput("Branch for outer level repo .grapeconfig:", default=initialpublic)

        try:
           project = grape_gitlab.project(projectname)
        except:
           logging.info(f"Failed to access project {projectname}!")
           return False

        try:
           topRepo = project.repo(topreponame)
        except:
           logging.info(f"Failed to access repo {topreponame}!")
           return False
           
        task_completed = False

        if args["--createRepo"]:
            try:
               # Only allow admin tasks to be performed if access level is maintainer or above
               project = grape_gitlab.project(projectname, min_access_level=40)
            except:
               logging.info(f"You do not have admin privileges for project {projectname}!")
               return False

            newRepoName = args["--createRepo"]

            # Create the repository with appropriate defaults
            newRepo = grape_gitlab._gitlab.projects.create({ 'name': newRepoName,
                                                             'namespace_id': project.group.id,
                                                             'initialized_with_readme': False,
                                                             'only_allow_merge_if_pipeline_succeeds': True,
                                                             # We still need to use the deprecated API for creation
                                                             'jobs_enabled': False,
                                                             #'builds_access_level': 'disabled',
                                                             'lfs_enabled': False})
            logging.info(f"Created repository {newRepoName}.")

            # Disable reset of approvals on push
            approvals = newRepo.approvals.get()
            approvals.reset_approvals_on_push = False
            approvals.save()

            if args["--owner"]:
               matching_users = grape_gitlab._gitlab.users.list(all=True, username=args["--owner"])
               if matching_users:
                  user_id = matching_users[0].id
                  newRepo.members.create({'user_id': user_id, 'access_level': 50})
               else:
                  logging.info(f"Owner username {args['--owner']} not found.")

            logging.info(f"Please run `grape gitlab-admin --setProtectedBranches' after public branches are pushed.")
            task_completed = True

        setProtectedBranches = args["--setProtectedBranches"] or args["--allRepoSettings"]
        setKeepMRApprovals = args["--setKeepMRApprovals"] or args["--allRepoSettings"]
        disableLFS = args["--disableLFS"] or args["--allRepoSettings"]
        disableSubprojectCI = args["--disableSubprojectCI"] or args["--allRepoSettings"]
        requirePipelineSuccess = args["--requirePipelineSuccess"] or args["--allRepoSettings"]
      
        if setProtectedBranches or setKeepMRApprovals or disableLFS or disableSubprojectCI or requirePipelineSuccess:
           project = grape_gitlab.project(projectname)
           grapeRepos = self.getGrapeReposAndPublicBranches(project=project, topreponame=topreponame, initialbranch=topbranch, verbose=args["--verbose"])

           for reponame,public in grapeRepos.items():
               logging.info(f"Repository {reponame}")
               try:
                  repo = project.repo(reponame, min_access_level=40)
               except:
                  logging.info("Skipped. Perhaps you are not an owner or maintainer")

               if setProtectedBranches:
                  for branch in public:
                     # If this is the top level repository and merge trains are enabled,
                     # disable all pushes if merge trains are enabled for the branch.
                     disablePush = False
                     if reponame == topreponame and repo.project.merge_trains_enabled:
                         parser = configparser.ConfigParser()
                         grapeConfig = repo.project.files.raw(file_path=".grapeconfig", ref=branch).decode('utf-8')
                         parser.read_string(grapeConfig)
                         try:
                             if parser.get('publish','mergetrain'):
                                 disablePush = True
                         except:
                             pass
                     if disablePush:
                         # Set to allow developers+maintainers to merge, but not to push or force push
                         replaced = repo.setProtectedBranch(branch, 0, 30, False)
                         logging.info(f"\tDisabling push for {branch}")
                     else:
                         # Set to allow developers+maintainers to merge and push, but not to force push
                         replaced = repo.setProtectedBranch(branch, 30, 30, False)
                     if replaced:
                        logging.info(f"\tUpdating protected branch {branch}")
                     else:
                        logging.info(f"\tProtecting branch {branch}")
                  task_completed = True

               if setKeepMRApprovals:
                  logging.info("\tSetting Keep MR Approvals...")
                  approvals = repo.project.approvals.get()
                  if approvals.reset_approvals_on_push:
                     if args["--dry"]:
                        logging.info("\t[Dry run]: Keep MR Approvals not set")
                     else:
                        approvals.reset_approvals_on_push = False
                        approvals.save()
                  else:
                     logging.info("\tPreviously disabled")
                  task_completed = True

               if disableLFS:
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

               if disableSubprojectCI:
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

               if requirePipelineSuccess:
                  logging.info("\tRequiring pipeline success for merge...")
                  if not repo.project.only_allow_merge_if_pipeline_succeeds:
                     if args["--dry"]:
                        logging.info("\t[Dry run]: Not requiring pipeline success")
                     else:
                        repo.project.only_allow_merge_if_pipeline_succeeds = True
                        repo.project.save()
                  else:
                     logging.info("\tPreviously required")
                  task_completed = True

        if args["--scheduledPipelines"]:
           argsOk = True
           if args["--scheduledPipelines"] == 'list':
              if args["--pid"]:
                 logging.info(f"--pid is not allowed for --scheduledPipelines={args['--scheduledPipelines']}")
                 argsOk = False 
           else:
              if not args["--scheduledPipelines"] == 'add' and not args["--pid"]:
                 logging.info(f"--pid is required for --scheduledPipelines={args['--scheduledPipelines']}")
                 argsOk = False 
              if args["--scheduledPipelines"] == 'delete' or args["--scheduledPipelines"] == 'take':
                 if args["--ref"]:
                    logging.info(f"--ref is not allowed for --scheduledPipelines={args['--scheduledPipelines']}")
                    argsOk = False 
                 if args["--desc"]:
                    logging.info(f"--desc is not allowed for --scheduledPipelines={args['--scheduledPipelines']}")
                    argsOk = False 
                 if args["--cron"]:
                    logging.info(f"--cron is not allowed for --scheduledPipelines={args['--scheduledPipelines']}")
                    argsOk = False 
                 if args["--timezone"]:
                    logging.info(f"--timezone is not allowed for --scheduledPipelines={args['--scheduledPipelines']}")
                    argsOk = False 
                 if args["--active"]:
                    logging.info(f"--active is not allowed for --scheduledPipelines={args['--scheduledPipelines']}")
                    argsOk = False 
              elif args["--scheduledPipelines"] == 'add':
                 if not args["--ref"]:
                    logging.info(f"--ref is required for --scheduledPipelines={args['--scheduledPipelines']}")
                    argsOk = False 
                 if not args["--desc"]:
                    logging.info(f"--desc is required for --scheduledPipelines={args['--scheduledPipelines']}")
                    argsOk = False 
                 if not args["--cron"]:
                    logging.info(f"--cron is required for --scheduledPipelines={args['--scheduledPipelines']}")
                    argsOk = False 

           if argsOk:
              if args["--scheduledPipelines"] == 'add':
                 topRepo.addScheduledPipeline(args["--ref"], args["--desc"], args["--cron"], args["--timezone"], args["--active"])
              elif args["--scheduledPipelines"] == 'delete':
                 topRepo.deleteScheduledPipeline(args["--pid"])
              elif args["--scheduledPipelines"] == 'list':
                 topRepo.listScheduledPipelines()
              elif args["--scheduledPipelines"] == 'take':
                 topRepo.takeScheduledPipeline(args["--pid"])
              elif args["--scheduledPipelines"] == 'update':
                 topRepo.updateScheduledPipeline(args["--pid"], args["--ref"], args["--desc"], args["--cron"], args["--timezone"], args["--active"])
           
           task_completed = True

        if args["--checkJob"]:
           topRepo.listLastSuccessfulPipelines(args["--checkJob"])
           task_completed = True

        if args["--runningJobs"]:
           topRepo.listRunningJobs(name, args["--runningJobs"])
           task_completed = True

        if args["--runJob"] or args["--startJob"]:
           if not args["--pid"]: 
              logging.info("--pid is required for --runJob/--startJob")
           else:
              topRepo.runJob(args["--runJob"] if args["--runJob"] else args["--startJob"], args["--pid"], args["--runJob"])
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
        config.set(self.SECTION_REPO, "name", "My unnamed repo")
