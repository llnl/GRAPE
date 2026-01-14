import getpass
import logging
import os
import re
import subprocess
import sys
import time
import keyring
try:
    grape_dir = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
    sys.path.insert(0, os.path.join(grape_dir, 'python-gitlab'))
    import gitlab
except ModuleNotFoundError:
    # Don't error out here because this is imported even if GitLab is not used
    pass
from vine import config_parser_global
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
    defaultCurl = "/usr/bin/curl"
    # default token expiration
    defaultExpiration = 29

    def __init__(self, username=None, url=defaultURL, verify=True, port=defaultPort, ssh_path = defaultSSH_Path, curl = defaultCurl, group = None, *, workspace_dir):

        if username is None:
            self._userName = utility.getUserName(service="Gitlab")
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
        self._curl = curl
        password = keyring.get_password(self._service, self._userName)

        if group is None:
            # If the group is not specified, get it from the .grapeconfig
            group = config_parser_global.grapeConfig().get(Option.SECTION_PROJECT, "name")

        if self.auth(self._service, self._userName, password, port, ssh_path, group, verify=verify):
            self.url = url
            logging.info("Connected to Gitlab.")
        else:
            self._gitlab= None
            logging.info("Could not connect to Gitlab...")

    def generate_personal_access_token(self, port, ssh_url, expires = defaultExpiration):
        command = f"ssh -p {port} {ssh_url} personal_access_token grape_review api {expires}"
        logging.info(f"Generating token by executing {command}")
        completed_process = subprocess.run(command,
                                           capture_output=True,
                                           shell=True)
        return completed_process.stdout.decode().strip().split()[1].strip()

    def auth(self, service, username, password, port, ssh_path, group, verify=True):
        if not verify:
            import warnings
            import urllib3
            warnings.filterwarnings('ignore', category=urllib3.exceptions.InsecureRequestWarning)

        # set a password to something bogus to trigger an authentication error
        if (password is None):
            password = "123456_bad_password"
        self._userName = username
        self._service = service
        if 'GRAPE_GITLAB_ACCESS_TOKEN' in os.environ:
            self._gitlab = gitlab.Gitlab(service, private_token=os.environ['GRAPE_GITLAB_ACCESS_TOKEN'], api_version=4)
        else:
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
                    # There may be projects (groups) that are visible to all users, so check for our project (group).
                    if group.lower() in [x.lower() for x in projects]:
                        success = True
                    else:
                        logging.info(f"{group} not accessible. Available groups: {projects}")
                        raise gitlab.exceptions.GitlabAuthenticationError()
                else:
                    logging.info("empty list of gitlab groups.")
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

    def graphQL_query(self, query, dryRun=False):
        token = keyring.get_password(self._service, self._userName)
        graphqlurl = f'{self._service}/api/graphql'
        # enable inbound allowlist and add top level repo to list
        data = '\'{ "query": "' + query.replace('"', '\\"') + '" } \''
        # strip newlines from query
        data = re.sub(' +', ' ', data.replace("\n"," "))
        command = f'{self._curl} {graphqlurl} --header "Authorization: Bearer {token}" --header "Content-Type: application/json" --request POST --data-binary ' + data
        if not dryRun:
            completed_process = subprocess.run(command, capture_output=True, shell=True)
            output = completed_process.stdout.decode().strip()
            return output
        else:
            return command

    # Return list of project names (paths)
    def projectlist(self):
        return [g.path for g in self._gitlab.groups.list(all=True)]

    def project(self, name, min_access_level=None):
        matching_ids = [x.id for x in self._gitlab.groups.list(all=True, search=name, min_access_level=min_access_level) if x.path.lower() == name.lower()]
        if matching_ids:
            group_id = matching_ids[0]
        else:
            logging.info(f"Could not find group {name}.")
            raise SystemExit("Abort")
        p = Project(self._gitlab.groups.get(group_id),self._gitlab)
        return  p

class Project:
    def __init__(self, gitlab_group, gitlab):
        self.group = gitlab_group
        self.gitlab = gitlab

    def name(self):
        return self.group.name

    def repolist(self):
        return [r.name for r in self.group.projects.list(all=True)]

    def repo(self, name, min_access_level=None):
        matching_ids = [x.id for x in self.group.projects.list(all=True, search=name, min_access_level=min_access_level) if x.name.lower() == name.lower()]
        if matching_ids:
            project_id = matching_ids[0]
        else:
            logging.info(f"Could not find project {name}.")
            raise SystemExit("Abort")
        return Repo(self.gitlab.projects.get(project_id), self.gitlab)

    def groupid(self, groupname):
        # groups API doesn't include exact match, so we have to iterate over the search
        for group in self.gitlab.groups.list(all=True, search=groupname):
            if group.name == groupname:
                return group.id
        return 0

    def userid(self, username):
        users = self.gitlab.users.list(all=True, username=username)
        if users:
            return users[0].id
        return 0

class Repo:
    def __init__(self, gitlab_project, gitlab ):
        self.project = gitlab_project
        self.gitlab = gitlab

    def getBranchHeadCommitHash(self, name):
        """
        Get the commit SHA (hash) at the head of a branch.

        Args:
            name (str): Branch name.

        Returns:
            str | None: The head commit SHA if the branch exists; otherwise None if
            the branch is not found.

        Raises:
            gitlab.exceptions.GitlabGetError: If an error other than 404 occurs.
        """
        try:
            return self.project.branches.get(name).commit["id"]
        except gitlab.exceptions.GitlabGetError as e:
            if e.response_code == 404:
                return None
            else:
                raise

    def getFile(self, path, revision):
        """
        Retrieve a file's contents from the repository at a specific revision.

        Args:
            path (str): Repository-relative file path.
            revision (str): Git reference (e.g., branch name, tag, or commit SHA).

        Returns:
            str: UTF-8 decoded file contents if found

        Raises:
            gitlab.exceptions.GitlabAuthenticationError: If authentication is not correct
            gitlab.exceptions.GitlabGetError: If the file could not be retrieved
        """
        return self.project.files.raw(path, revision).decode('utf-8')

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

    def createPullRequest(self, title, branch, target_branch, description=None, reviewers=None, non_approvers=None, wip=None, labels=[]):
         # GitLab can create merge requests with no commits, but we don't want those,
         # in the case that the branch is behind the target branch.
         # Check that the branch actually has new commits compared to the target.
         try:
            diff_result = self.project.repository_compare(target_branch, branch, straight=True, per_page=1)
            if diff_result and not diff_result["commits"]:
               logging.info(f"Not creating merge request for {self.project.name}: {target_branch}..{branch} has no commits.")
               return None
         except gitlab.exceptions.GitlabGetError:
            # If the diff is too big, this comparison can throw an exception.
            # In this case, just create the merge request.
            pass

         mr = PullRequest(self.project.mergerequests.create({"source_branch": branch,
                                            "target_branch": target_branch,
                                            "remove_source_branch": False,
                                            "title": PullRequest.get_title_for_wip_state(title, wip)}),
                          self.gitlab)
         mr.update(title,
                   description=description,
                   reviewers=reviewers,
                   non_approvers=non_approvers,
                   wip=wip,
                   add_labels=labels)

         return mr

    def getTag(self, name):
        """
        Retrieve a git tag from the repository by its name.

        Args:
            name (str): The name of the tag to retrieve.

        Returns:
            ProjectTag | None: ProjectTag object if the tag exists; otherwise None

        Notes:
            Throws exception if the tag cannot be retrieved (e.g. unauthorized).
            Does not throw if the tag does not exist.
        """
        try:
            return self.project.tags.get(name)
        except gitlab.exceptions.GitlabGetError as e:
            if e.response_code == 404 and e.error_message == '404 Tag Not Found':
                return None
            else:
                raise

    def createTag(self, name, ref, message):
        """
        Create a git tag in the repository.

        Args:
            name (str): The name of the tag to create.
            ref (str): The commit SHA or branch the tag should point to.
            message (str): The tag message.

        Notes:
            Throws exception if the tag cannot be created.
        """
        self.project.tags.create({'tag_name': name,
                                  'ref': ref,
                                  'message': message})

    def deleteTag(self, name):
        """
        Delete a git tag from the repository by its name.

        Args:
            name (str): The name of the tag to delete.

        Returns:
            None

        Notes:
            Throws exception if the tag cannot be deleted (e.g. unauthorized).
            Does not throw if the tag does not exist.
        """
        try:
            self.project.tags.delete(name)
        except gitlab.exceptions.GitlabDeleteError as e:
            if e.response_code == 404 and e.error_message == '404 Tag Not Found':
                return
            else:
                raise

    def updateTag(self, name, ref, message):
        """
        Updates a git tag in the repository.

        Args:
            name (str): The name of the tag to update.
            ref (str): The commit SHA or branch the tag should point to.
            message (str): The tag message.

        Notes:
            There is no API for updating a tag, so it must be deleted
            (if present) and then recreated with the new ref and message.
            Throws exception if the existing tag cannot be deleted or
            the new tag cannot be created.
        """
        self.deleteTag(name)
        self.createTag(name, ref, message)

    def getDiffs(self, fromRevision, toRevision):
        """
        Compare two revisions in the repository and return their diff/compare data.

        Args:
            fromRevision (str): The base git reference (e.g., branch, tag, or commit SHA).
            toRevision (str): The head git reference (e.g., branch, tag, or commit SHA).

        Returns:
            dict: The GitLab compare API response, including commit and diff information.

        Raises:
            gitlab.exceptions.GitlabGetError: If the comparison cannot be retrieved.
        """
        return self.project.repository_compare(fromRevision, toRevision)

    # If restrict_id is positive, it is the group id to restrict the branch to;
    # if it is negative, it is the negative of the user id to restrict the branch to;
    # otherwise, the push_access_level and merge_access_level are used.
    def setProtectedBranch(self, name, push_access_level, merge_access_level, restrict_id, allow_force_push):
        replaced = False
        # Remove the old protected branch if it already exists
        if self.project.protectedbranches.list(all=True, search=name):
           self.project.protectedbranches.delete(name)
           replaced = True
        createArgs = {"name": name, "allow_force_push": allow_force_push}
        if restrict_id > 0:
           # protect by group
           if push_access_level != 0:
              createArgs["allowed_to_push"] = [{"group_id": restrict_id}]
           else:
              createArgs["push_access_level"] = 0
           if merge_access_level != 0:
              createArgs["allowed_to_merge"] = [{"group_id": restrict_id}]
           else:
              createArgs["merge_access_level"] = 0
        elif restrict_id < 0:
           # protect by user
           if push_access_level != 0:
              createArgs["allowed_to_push"] = [{"user_id": -restrict_id}]
           else:
              createArgs["push_access_level"] = 0
           if merge_access_level != 0:
              createArgs["allowed_to_merge"] = [{"user_id": -restrict_id}]
           else:
              createArgs["merge_access_level"] = 0
        else:
           # protect by access level
           createArgs["push_access_level"] = push_access_level
           createArgs["merge_access_level"] = merge_access_level
        self.project.protectedbranches.create(createArgs)
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

    def addToMergeTrain(self, merge_request, sha):
        """
        Add the given pull request to the GitLab merge train for this project.

        This method sends a POST request to the GitLab API to enqueue the
        specified merge request into the project's merge train.

        Parameters
        ----------
        merge_request : Any
            An object representing the merge request. It must provide an `iid()`
            method that returns the internal ID of the merge request in GitLab.
        sha : str
            The SHA must match the HEAD of the merge request branch, otherwise
            the merge fails.

        Side Effects
        ------------
        Sends an HTTP POST request to the GitLab API endpoint:
        `/projects/{project_id}/merge_trains/merge_requests/{iid}`

        The request body includes:
            {
                "sha": "<provided sha>"
            }

        The call is expected to be made via `self.gitlab.http_post`.

        Raises
        ------
        Any exception that `self.gitlab.http_post` may raise in case of
        network errors, authentication failures, or non-successful responses.

        Notes
        -----
        Adapted from https://github.com/python-gitlab/python-gitlab/pull/2552.
        """
        path = f"/projects/{self.project.id}/merge_trains/merge_requests/{merge_request.iid()}"

        data = {
            "sha": sha
        }

        self.gitlab.http_post(path, post_data=data)




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

    def authorEmail(self):
        authorID = self.mergerequest.author["id"]
        # This will only return a non-empty value if the public email has been set
        return self.gitlab.users.get(authorID).public_email

    def description(self):
        description = self.mergerequest.description or ""
        # Drop non-ascii characters
        return description.encode('ascii', 'ignore').decode('ascii')

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

    def labels(self):
        return self.mergerequest.labels

    def state(self):
        return self.mergerequest.state

    def title(self):
        return self.mergerequest.title

    def fromRef(self):
        return self.mergerequest.source_branch

    def toRef(self):
        return self.mergerequest.target_branch

    def fromSHA(self):
        return self.mergerequest.sha

    def approve(self):
        """
        Approve this merge request.

        Returns:
            The GitLab API response from the approve action.

        Notes:
            Throws exception if the approval cannot be completed (e.g. insufficient permissions).
        """
        return self.mergerequest.approve()

    def approved(self):
        approvals = self.mergerequest.approvals.get()
        return approvals.approvals_required > 0 and approvals.approvals_left == 0

    def link(self):
        url = self.mergerequest.web_url

        if not isinstance(url, str):
            url = url.decode("utf-8")

        return url


    def version(self):
        # gitlab does not seem to have the same concept of a version exposed to the REST API
        return 123

    def iid(self):
        return self.mergerequest.iid

    def diffs(self):
        """
        Retrieve the merge request's changes, including file diffs and related metadata.

        Returns:
            dict: GitLab API response from the merge request changes endpoint.

        Raises:
            gitlab.exceptions.GitlabGetError: If the changes cannot be retrieved.

        Note:
            The changes API is deprecated in favor of the diffs API, but the diffs API
            does not yet provide the needed information (or perhaps we need to update
            the python-gitlab library).
        """
        return self.mergerequest.changes()

    @staticmethod
    def get_title_for_wip_state(title, wip):
        if not hasattr(PullRequest.get_title_for_wip_state, "regexp"):
            PullRequest.get_title_for_wip_state.regexp = re.compile(r'^(wip:|draft:)\s*', re.IGNORECASE)

        new_title = title

        if wip is not None:
            if wip:
                if not PullRequest.get_title_for_wip_state.regexp.match(title):
                    new_title = "Draft: " + title
            else:
                new_title = PullRequest.get_title_for_wip_state.regexp.sub('', title)

        return new_title

    # reviewers is a dict, keyed by approval rule name, valued by lists of usernames
    def update(self, ver, title=None, description=None, reviewers=None, non_approvers=None, wip=None, add_labels=[], remove_labels=[]):
        if title is None:
            title = self.mergerequest.title

        self.mergerequest.title = self.get_title_for_wip_state(title, wip)

        if description:
            self.mergerequest.description = description

        if reviewers:
            all_reviewer_ids = set()

            for review_rule_name in reviewers:
                reviewer_group = reviewers[review_rule_name]
                approval_rule_name = reviewer_group['label']
                users = reviewer_group['reviewers']
                num_required = len(users)

                approval_rules = self.mergerequest.approval_rules.list()

                # Find the approval rule by name
                matching_rule = None

                for rule in approval_rules:
                    if rule.name == approval_rule_name:
                        matching_rule = rule
                        break

                # Merge request approvals created by others can only be changed by maintainer and above,
                # so only update them if they are changed and just warn if they cannot be updated.

                if users:
                    reviewer_ids = []

                    for r in users:
                        matching_reviewers = self.gitlab.users.list(all=True, username=r)
                        if matching_reviewers:
                           gitlab_reviewer = matching_reviewers[0]
                        else:
                           logging.info(f"Could not find reviewer {r}.")
                           raise SystemExit("Abort")
                        if non_approvers and r in non_approvers:
                            logging.info(f"Reviewer {r} is a non-approver, not adding to {approval_rule_name}.")
                            num_required -= 1
                            all_reviewer_ids.add(gitlab_reviewer.id)
                        else:
                            reviewer_ids.append(gitlab_reviewer.id)

                    update = True
                    if matching_rule is not None:
                        eligible_approver_ids = set()
                        for approver in matching_rule.eligible_approvers:
                            eligible_approver_ids.add(approver["id"]) 
                        if eligible_approver_ids == set(reviewer_ids) and matching_rule.approvals_required == num_required:
                            logging.info(f'Approval rule "{approval_rule_name}" unchanged.')
                            update = False 
                    if update:
                        try:
                            self.mergerequest.approvals.set_approvers(num_required,approver_ids=reviewer_ids, approval_rule_name=approval_rule_name)
                        except gitlab.exceptions.GitlabUpdateError as e:
                            logging.warning(f'GRAPE: WARNING: Failed to update approval rule "{approval_rule_name}": {e}')

                    for reviewer_id in reviewer_ids:
                        all_reviewer_ids.add(reviewer_id)
                else:
                    if matching_rule is not None:
                        try:
                            # Delete the approval rule
                            self.mergerequest.approval_rules.delete(matching_rule.id)
                            logging.info(f'Deleted approval rule "{approval_rule_name}".')
                        except gitlab.exceptions.GitlabDeleteError as e:
                            logging.warning(f'GRAPE: WARNING: Failed to delete approval rule "{approval_rule_name}": {e}')

            self.mergerequest.reviewer_ids = list(all_reviewer_ids)

        if self.mergerequest.description:
            self.mergerequest.description =  re.sub("([^\n])\n([^\n])","\\1\n\n\\2",self.mergerequest.description)

        labels = set(self.mergerequest.labels)
        for label in add_labels:
            labels.add(label)
        for label in remove_labels:
            try:
               labels.remove(label)
            except KeyError:
               pass
        self.mergerequest.labels = list(labels)

        # Disable removal of source branch on merge (if this merge request was created by hand).
        # This should only affect merging by clicking the merge button (grape manually disables the removal when
        # when merging the merge request). The merge button should be disabled by disabling CI and requiring pipelines
        # to succeed, but disabling it here provides another layer of protection (removing the branch early can
        # adversely affect tagging and notification steps in multi-repo projects).
        self.mergerequest.remove_source_branch = False
        self.mergerequest.save()
        return self

    def regeneratePipeline(self, raiseOnFailure=True):
        # Create a new pipeline to reflect any changes in labels
        try:
            self.mergerequest.pipelines.create()
        except gitlab.exceptions.GitlabCreateError:
            time.sleep(5)
            logging.info("Trying again after initial 405 error...")
            try:
                self.mergerequest.pipelines.create()
            except gitlab.exceptions.GitlabCreateError as e:
                if raiseOnFailure:
                    raise(e)

    def __eq__(self, other):
        return (self.toRef() == other.toRef()) and (self.fromRef() == other.fromRef())

    def __str__(self):
        all_reviewers = ', '.join(r[0] + " (%s)" % ("Approved" if r[1] else "Not yet approved") for r in self.reviewers())
        return f"Title: {self.title()}\n" + \
               f"From: {self.fromRef()}\n" + \
               f"To: {self.toRef()}\n" + \
               f"Reviewers: {all_reviewers}\n" + \
               f"Description: {self.description()}\n"

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

