import getpass
import logging
import os
import re
import subprocess
import sys
import time
import keyring
import gitlab
from vine import config_parser_global
from vine import grape_errors
from vine import grapeGit as git
from vine import utility
from vine.option import Option


GRAPE_GITLAB_APPROVAL_RULE_NAME = "GRAPE Reviewers"
# Grape has the following definitions, most strongly correllated with Bitbucket definitions:
# Project - collection of repositories (roughly analogous to a Gitlab Group)
# Repo - the actual repository (roughly analogous to a Gitlap Project)
class GrapeGitlabAdapter:
    defaultURL = "https://your.host.org/gitlab"
    defaultPort = 7999
    defaultSSH_Path= "git@gitlab.your.host.org"

    def __init__(self, username=None, url=defaultURL, verify=True, port=defaultPort, ssh_path = defaultSSH_Path, *, workspace_dir):

        if username is None:
            self._userName = utility.getUserName()
        else:
            self._userName = username

        self.workspace_dir = workspace_dir

        # Ensures same keyring used across all OSes
        MAGIC_PRIORITY_NUM = .5
        if keyring.get_keyring().priority != MAGIC_PRIORITY_NUM:
            key_rings = [kr for kr in keyring.backend.get_all_keyring()
                         if kr.priority == MAGIC_PRIORITY_NUM]
            keyring.set_keyring(key_rings.pop())
        self.keyring = keyring.get_keyring()

        self._service = url
        password = keyring.get_password(self._service, self._userName)

        if self.auth(self._service, self._userName, password, port, ssh_path, verify=verify):
            self.url = url
            logging.info("Connected to Gitlab.")
        else:
            self._gitlab= None
            logging.info("Could not connect to Gitlab...")

    def generate_personal_access_token(self, port, ssh_url):
        command = f"ssh -p {port} {ssh_url} personal_access_token grape_review api"
        logging.info(f"Generating token by executing {command}")
        completed_process = subprocess.run(command,
                                           capture_output=True,
                                           shell=True)
        return completed_process.stdout.decode().strip().split()[1].strip()

    def auth(self, service, username, password, port, ssh_path, verify=True):
        # set a password to something bogus to trigger an authentication error
        if (password is None):
            password = "123456_bad_password"
        self._userName = username
        self._service = service
        self._gitlab = gitlab.Gitlab(service, password, api_version=4)
        numAttempts = 0
        success = False
        while numAttempts < 4 and not success:
            try:
                projects = None
                try:
                    projects = self.projectlist()
                except:
                    pass
                if projects:
                    success = True
                else:
                    logging.info("empty list from gitlab project.")
                    raise gitlab.exceptions.GitlabAuthenticationError()
            except gitlab.exceptions.GitlabAuthenticationError as e:
                logging.debug(e)
                logging.debug(type(e))
                logging.debug(f"numAttempts is {numAttempts}")
                if numAttempts == 0:
                    logging.info("session expired...")
                    try:
                        keyring.set_password(service, self._userName,
                                             self.generate_personal_access_token(port, ssh_path))
                    except Exception as e:
                        logging.error("Generating personal access token via ssh failed.")
                        logging.error(e)
                        numAttempts += 1
                        continue
                else:
                    logging.info("incorrect username / password...")
                    self._userName = utility.getUserName(self._userName)
                    keyring.set_password(service, self._userName,
                                         getpass.getpass("Enter personal access token for " +
                                                         f"{service}: "))
                self._gitlab = gitlab.Gitlab(service,  keyring.get_password(service, self._userName), api_version=4, ssl_verify=verify)
                numAttempts += 1

        return success

    # Return list of project names
    def projectlist(self):
        return [g.name for g in self._gitlab.groups.list(all=True)]

    def project(self, name, min_access_level=None):
        matching_ids = [x.id for x in self._gitlab.groups.list(all=True, search=name, min_access_level=min_access_level) if x.path.lower() == name.lower()]
        if matching_ids:
            group_id = matching_ids[0]
        else:
            logging.info(f"Could not find group {name}.")
            raise SystemExit("Abort")
        p = Project(self._gitlab.groups.get(group_id),self._gitlab)
        return  p

    def repoFromWorkspaceRepoPath(self, path, isSubmodule=False, isNested=False, topLevelRepo=None, topLevelProject=None):
        config = config_parser_global.grapeConfig()
        if isNested:
            proj = os.path.split(path)[1]
            nestedProjectURL = config.get(f"nested-{proj}", "url")
            url = git.parseSubprojectRemoteURL(
                nestedProjectURL, execution_path=self.workspace_dir)
            urlTokens = url.split('/')
            proj = urlTokens[-2]
            repo_name = urlTokens[-1]
            # strip off the git extension
            repo_name = '.'.join(repo_name.split('.')[:-1])
        elif isSubmodule:
            fullpath = os.path.abspath(os.path.join(self.workspace_dir,path))
            wsdir = self.workspace_dir + os.path.sep
            proj = fullpath.split(wsdir)[1].replace("\\","/")
            url_map = git.getAllSubmoduleURLMap(execution_path=self.workspace_dir)
            url = url_map[proj].split('/')
            if url[-2] == '..':
               # replace relative path with the top repo project
               topProjectURL = config.get(f"repo", "url").split('/')
               url[-2] = topProjectURL[-2]
            proj = url[-2]
            repo_name = url[-1]

            # strip off the .git extension
            repo_name = '.'.join(repo_name.split('.')[:-1])
        else:
            if topLevelRepo is None:
                topLevelRepo = config.get(Option.SECTION_REPO, "name")
            if topLevelProject is None:
                topLevelProject = config.get(Option.SECTION_PROJECT, "name")

            repo_name = topLevelRepo
            proj = topLevelProject

        repo = self.project(proj).repo(repo_name)
        return repo

class Project:
    def __init__(self, gitlab_group, gitlab):
        self.group = gitlab_group
        self.gitlab = gitlab

    def name(self):
        return self.group.name

    def repolist(self):
        return [r.name for r in self.group.projects.list(all=True)]

    def repo(self, name):
        matching_ids = [x.id for x in self.group.projects.list(all=True, search=name) if x.name.lower() == name.lower()]
        if matching_ids:
            project_id = matching_ids[0]
        else:
            logging.info(f"Could not find project {name}.")
            raise SystemExit("Abort")
        return Repo(self.gitlab.projects.get(project_id), self.gitlab)


class Repo:
    def __init__(self, gitlab_project, gitlab ):
        self.project = gitlab_project
        self.gitlab = gitlab
        
    # state can be "all", "merged", "opened", or "closed"
    def pullRequests(self, direction= "IGNORED", at=None, state="opened", target_branch=None, source_branch=None, id=None):
        if id == None:
            # translates from bitbucket to gitlab state types
            state_dict = {"open":"opened", "opened":"opened",
                          "merged": "merged",
                          "declined":"closed", "closed":"closed",
                          "all":"all"
                          }
            state = state_dict[state.lower()]
            return [PullRequest(x, self.gitlab) for x in self.project.mergerequests.list(all=True, state=state, target_branch=target_branch, source_branch=source_branch) ]
        else:
            return [PullRequest(self.project.mergerequests.list(iids=[id])[0], self.gitlab)]

    def getOpenPullRequest(self, source, target):
        requests = self.pullRequests(state="opened", target_branch=target, source_branch=source)
        return requests[0] if requests else None

    def getMergedPullRequests(self, source, target):
        return self.pullRequests(state="merged", target_branch=target, source_branch=source)

    def createPullRequest(self, title, branch, target_branch, description=None, reviewers=None):
         # GitLab can create merge requests with no commits, but we don't want those,
         # in the case that the branch is behind the target branch.
         # Check that the branch actually has new commits compared to the target.
         diff_result = self.project.repository_compare(target_branch, branch, straight=True, per_page=1)
         if diff_result and not diff_result["commits"]:
            logging.info(f"Not creating merge request for {self.project.name}: {target_branch}..{branch} has no commits.")
            return None
         mr = PullRequest(self.project.mergerequests.create({"source_branch": branch,
                                            "target_branch": target_branch,
                                            "remove_source_branch": False,
                                            "title": title}),
                          self.gitlab)
         mr.update(title, description=description, reviewers={GRAPE_GITLAB_APPROVAL_RULE_NAME:(reviewers, len(reviewers))})

         return mr

    def setProtectedBranch(self, name, push_access_level, merge_access_level, allow_force_push):
        replaced = False
        # Remove the old protected branch if it already exists
        if self.project.protectedbranches.list(all=True, search=name):
           self.project.protectedbranches.delete(name)
           replaced = True
        self.project.protectedbranches.create({"name": name,
                                               "push_access_level": push_access_level,
                                               "merge_access_level": merge_access_level,
                                               "allow_force_push": allow_force_push})
        return replaced

    @staticmethod
    def printScheduledPipeline(pipeline):
        active = "Active" if pipeline.active else "Inactive"
        print(f"{pipeline.description} ({active})")
        print(f"  id: {pipeline.id}  ref: {pipeline.ref}")
        print(f"  owner: {pipeline.owner['username']} ({pipeline.owner['name']})")
        print(f"  cron: {pipeline.cron}  timezone: {pipeline.cron_timezone}")
        print()

    def getScheduledPipeline(self, pid):
        scheduled_pipelines = self.project.pipelineschedules.list(all=True)
        for pipeline in scheduled_pipelines:
            if pipeline.id == int(pid):
               return pipeline
        return None

    def listScheduledPipelines(self):
        scheduled_pipelines = self.project.pipelineschedules.list(all=True)
        print()
        for pipeline in scheduled_pipelines:
            self.printScheduledPipeline(pipeline)

    def addScheduledPipeline(self, ref, desc, cron, timezone, active):
        args = { "ref": ref, "description": desc, "cron": cron }
        if timezone:
            args["cron_timezone"] = timezone
        if active is not None:
            args["active"] = active
        try:
           pipeline = self.project.pipelineschedules.create(args)
           logging.info("*** Created new pipeline ***")
           self.printScheduledPipeline(pipeline)
        except Exception as e:
            logging.info(f"Failed to create pipeline with {args}.\n{e}")

    def deleteScheduledPipeline(self, pid):
        pipeline = self.getScheduledPipeline(pid)
        logging.info("*** Deleting ***")
        self.printScheduledPipeline(pipeline)
        try:
           self.project.pipelineschedules.delete(pid)
           logging.info("*** Done ***")
        except Exception as e:
           logging.info(f"Failed to delete pipeline {pid} owned by {pipeline.owner['username']}.\n{e}")

    def takeScheduledPipeline(self, pid):
        pipeline = self.getScheduledPipeline(pid)
        logging.info("*** Taking ownership of pipeline ***")
        self.printScheduledPipeline(pipeline)
        try:
           pipeline.take_ownership()
           logging.info("*** Done ***")
        except Exception as e:
           logging.info(f"Failed to take ownership of pipeline {pid} owned by {pipeline.owner['username']}.\n{e}")

    def updateScheduledPipeline(self, pid, ref, desc, cron, timezone, active):
        pipeline = self.getScheduledPipeline(pid)
        if not pipeline:
           logging.info(f"No scheduled pipeline with pid {pipelineid} found! Use grape gitlab-admin --scheduledPipelines=list to list pipelines")
        else:
           logging.info("*** Original ***")
           self.printScheduledPipeline(pipeline)
           orig = [pipeline.ref, pipeline.description, pipeline.cron, pipeline.cron, pipeline.cron_timezone, pipeline.active]
           if ref:
               pipeline.ref = ref
           if desc:
               pipeline.description = desc
           if cron:
               pipeline.cron = cron
           if timezone:
               pipeline.cron_timezone = timezone
           if active is not None:
               pipeline.active = active
           try:
               pipeline.save()
               pipeline._get_updated_data()
               if orig == [pipeline.ref, pipeline.description, pipeline.cron, pipeline.cron, pipeline.cron_timezone, pipeline.active]:
                  logging.info("*** No change ***")
               else:
                  logging.info("*** Updated ***")
                  self.printScheduledPipeline(pipeline)
           except Exception as e:
               logging.info(f"Failed to update pipeline {pid} owned by {pipeline.owner['username']}.\n{e}")

    # Get the pipeline ID corresponding to the last successful job on each merge request
    def listLastSuccessfulPipelines(self, job_name):
        open_merge_requests = self.project.mergerequests.list(all=True, state='opened')
        rows = []
        for mr in open_merge_requests:
           merge_request_iid = mr.iid
           # The pipelines are listed (by default) by creation date in descending order (newest first)
           branch_pipelines = self.project.pipelines.list(all=True, ref=f"refs/merge-requests/{merge_request_iid}/merge")
           for pi in branch_pipelines:
               found = False
               for job in pi.jobs.list(all=True, scope="success"):
                  if job.name == job_name:
                     rows.append(f"{pi.id}\t{pi.ref}")
                     found = True
                     break
               if found:
                  # Only consider the successful job on the newest pipeline
                  break
        if rows:
           print(f"Last successful runs of {job_name}:")
           print("PID\tREF") 
           for row in rows:
               print(row)
        else:
           print(f"No successful runs of {job_name}")

    def listRunningJobs(self, name, op):
        for pi in self.project.pipelines.list(all=True, scope='running'):
            for job in pi.jobs.list(all=True):
               if job.status in ['waiting_for_resource', 'preparing', 'pending', 'running'] and job.user['username'] == name:
                  print(f"#{job.id} {job.status} {job.name} {job.ref} {job.runner['description'] if job.runner else ''} {job.started_at if job.started_at else ''}")
                  if op == 'log':
                     pjob = self.project.jobs.get(job.id)
                     print(pjob.trace().decode())

    # Run named job on specified pipeline
    def runJob(self, job_name, pid, allow_rerun):
        branch_pipelines = self.project.pipelines.list(all=True)
        foundPipe = False
        foundJob = False
        for pi in branch_pipelines:
            if pi.id == int(pid):
               foundPipe = True
               for pipeline_job in pi.jobs.list(all=True):
                  if pipeline_job.name == job_name:
                     foundJob = True
                     print(f"Found job {job_name} on pipeline for {pi.ref}")
                     job = self.project.jobs.get(pipeline_job.id, lazy=True)
                     if allow_rerun or pipeline_job.status != 'success':
                        print(f"Previous status: {pipeline_job.status}")
                        try:
                           print(f"Running {job_name}...")
                           job.play()
                           print("Done")
                        except Exception as e:
                           logging.info(f"Failed to run job {job_name} on pipeline {pid}\n{e}")
                     else:
                        print("Job already succeeded, not running")
                     break
        if not foundPipe:
            logging.info(f"Failed to find pipeline {pid}")
        elif not foundJob:
            logging.info(f"Failed to find job {job_name} on pipeline {pid}")

    def getSuccessfulJob(self, job_name, current_sha, target_sha, current_branch, target_branch):
        # manual jobs will have the branch name as a reference
        successful_job = None
        job_name = job_name.strip()
        branch_pipelines = self.project.pipelines.list(all=True, ref=current_branch)
        logging.debug(f"BRANCH PIPELINES {branch_pipelines}")
        # if there is a pipeline matching the current branch...
        for pi in branch_pipelines:
            logging.debug(pi.__dict__)
            # ... that has a successful job
            for job in pi.jobs.list(all=True, scope="success"):
               logging.debug(f"SUCCESSFUL branch pipeline : {pi.ref}, {pi.iid}, {pi.sha}\n\n")
               logging.debug(f"checking {job.name} against {job_name}")
               # ... matching the job name the user asked for
               if job.name == job_name:
                   logging.debug(f"checking {job.commit['id']} against {current_sha}")
                   # ... that ran aginst the current commit on this branch
                   if job.commit["id"] == current_sha:
                       # then the job passed!
                       logging.debug(f"creating successful_job")
                       successful_job = Job(self.project, job.id, self.gitlab)
                       break

        # merge request jobs will have a reference based off the merge request iid
        merge_request = self.getOpenPullRequest(current_branch, target_branch)
        logging.debug(f"open merge request {merge_request}")
        if merge_request and successful_job == None:
            merge_request_iid = merge_request.iid()
            merge_pipelines = self.project.pipelines.list(all=True, ref=f"refs/merge-requests/{merge_request_iid}/merge")
            logging.debug(f"MERGE_PIPELINES {merge_pipelines}")
            #if there is a pipeline in a repo configured to run merge requests under proposed merges...
            for pi in merge_pipelines:
                # ... that contains a successful job...
                for job in pi.jobs.list(all=True, scope="success"):
                   logging.debug(f"SUCCESSFUL job in merge_pipeline : {pi.ref}, {pi.iid}, {pi.sha}\n\n")
                   logging.debug(f"checking {job.name} against {job_name}")
                   # ... whose name matches the one the user cares about...
                   if job.name == job_name:
                       logging.debug(f"{job.commit}")
                       # ... and was actually tested agains the merge of this commit and the target commit...
                       parents = job.commit["parent_ids"]
                       logging.debug(f"checking {parents} against {current_sha} and {target_sha}")
                       if current_sha in parents and target_sha in parents:
                           # ...then the job passed!
                           logging.debug(f"creating successful_job")
                           successful_job = Job(self.project, job.id, self.gitlab)
                           break
            if successful_job == None:
                #if there is a pipeline in a repo configured to run merge requests on head..."
                head_pipelines = self.project.pipelines.list(all=True, ref=f"refs/merge-requests/{merge_request_iid}/head")
                for pi in head_pipelines:
                    # ... that contains a successful job...
                    for job in pi.jobs.list(all=True, scope="success"):
                       logging.debug(f"SUCCESSFUL job in head_pipeline : {pi.ref}, {pi.iid}, {pi.sha}\n\n")
                       logging.debug(f"checking {job.name} against {job_name}")
                       # ... whose name matches the one the user cares about...
                       if job.name == job_name:
                           logging.debug(f"{job.commit}")
                           # ... and was actually tested agains the merge of this commit and the target commit...
                           sha = job.commit["id"]
                           logging.debug(f"checking {sha} against {current_sha}")
                           if current_sha ==  sha:
                               # ...then the job passed!
                               logging.debug(f"creating successful_job")
                               successful_job = Job(self.project, job.id, self.gitlab)
                               break


        else:
            logging.debug(f"MR not found")

        return successful_job

    def artifact(self, ref_name, artifact_path, job):
        return self.project.artifact(ref_name,artifact_path, job)

class Job:
    def __init__(self, gitlab_project, gitlab_job_id, gitlab):
        self.job = gitlab_project.jobs.get(gitlab_job_id)
        self.gitlab = gitlab
    def artifact(self, path):
        return self.job.artifact(path)
    
        
        

class PullRequest:
    """
    node is the dictionary with the state of the Pull Request.
    stashy_pull_requests is the stashy object needed to update the pull request.
    """
    def __init__(self, gitlab_mergerequest, gitlab):
        self.mergerequest = gitlab_mergerequest
        self.gitlab = gitlab

    def author(self):
        return self.mergerequest.author["username"]

    def authorName(self):
        return self.mergerequest.author["name"]

    def authorName(self):
        return self.mergerequest.author["name"]

    def authorEmail(self):
        authorID = self.mergerequest.author["id"]
        # This will only return a non-empty value if the public email has been set
        return self.gitlab.users.get(authorID).public_email

    def description(self):
        if self.mergerequest.description != None:
            return self.mergerequest.description.encode('ascii', 'ignore')
        else:
            return "".encode('ascii', 'ignore')

    def date(self):
        return self.mergerequest.created_at

    def reviewers(self):
        """
        Returns [(username,bool(approved),displayname)...]
        """

        ret = {}

        for approver in self.mergerequest.reviewers:
            ret[approver["username"]] = (approver["username"], False, approver["name"])

        approvals = self.mergerequest.approvals.get()
        for reviewer in approvals.approved_by:
            name = reviewer["user"]["username"]
            if name in ret:
                ret[name] = (ret[name][0],True,ret[name][2])

        return list(ret.values())

    def state(self):
        return self.mergerequest.state

    def title(self):
        return self.mergerequest.title

    def fromRef(self):
        return self.mergerequest.source_branch

    def toRef(self):
        return self.mergerequest.target_branch

    def approved(self):
        approvals = self.mergerequest.approvals.get()
        return approvals.approvals_required > 0 and approvals.approvals_left == 0

    def link(self):
        return self.mergerequest.web_url

    def version(self):
        # gitlab does not seem to have the same concept of a version exposed to the REST API
        return 123

    def iid(self):
        return self.mergerequest.iid

    # reviewers is a dict, keyed by approval rule name, valued by lists of usernames
    def update(self, ver, title=None, description=None, reviewers=None):
        if title:
            self.mergerequest.title = title
        if description:
            self.mergerequest.description = description
        if reviewers:
            for approval_rule_name in reviewers:
                (users,numRequired) = reviewers[approval_rule_name]
                if users:
                    reviewer_ids = []
                    for r in users:
                        matching_reviewers = self.gitlab.users.list(all=True, username=r)
                        if matching_reviewers:
                           gitlab_reviewer = matching_reviewers[0]
                        else:
                           logging.info(f"Could not find reviewer {r}.")
                           raise SystemExit("Abort")
                        reviewer_ids.append(gitlab_reviewer.id)
                    self.mergerequest.approvals.set_approvers(numRequired,approver_ids=reviewer_ids, approval_rule_name=approval_rule_name)
                    self.mergerequest.reviewer_ids = reviewer_ids

        if self.mergerequest.description:
            self.mergerequest.description =  re.sub("([^\n])\n([^\n])","\\1\n\n\\2",self.mergerequest.description)
        self.mergerequest.save()
        return self

    def __eq__(self, other):
        return (self.toRef() == other.toRef()) and (self.fromRef() == other.fromRef())

    def __str__(self):
        all_reviewers = ', '.join(r[0] + " (%s)" % ("Approved" if r[1] else "Not yet approved") for r in self.reviewers())
        return f"Title: {self.title()}\n" + \
               f"From: {self.fromRef()}\n" + \
               f"To: {self.toRef()}\n" + \
               f"Reviewers: {all_reviewers}\n" + \
               f"Description: {self.description().decode('utf-8')}\n"

    def merge(self, merge_commit_message, should_remove_source_branch, merge_when_pipeline_succeeds):
        try:
            self.mergerequest.merge(merge_commit_message=merge_commit_message, should_remove_source_branch=False,
                                    merge_when_pipeline_succeeds=merge_when_pipeline_succeeds)
            return True
        except gitlab.exceptions.GitlabMRClosedError as e:
            logging.info(f"GitlabMRClosedError triggered! {e.__dict__}") 
            raise e


def testMe():
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
#                    logging.info(f"  MERGE success {pull.merge()}")
            logging.info("GETTING OPEN PULL REQUEST")
            pull = repo.getOpenPullRequest("feature/probinso/gitlab_support","develop")
            logging.info(f"  TITLE:     {pull.title()}")
            logging.info(f"  REVIEWERS: {pull.reviewers()}")
            logging.info(f"  APPROVED:  {pull.approved()}")

        except:
            pass


if __name__ == "__main__":
    testMe()

