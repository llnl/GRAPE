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
        print(f"Generating token by executing {command}")
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
                logging.debug(e, type(e), f"numAttempts is {numAttempts}")
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
        return [g.name for g in self._gitlab.groups.list()]

    def project(self, name):
        group_id = [x.id for x in self._gitlab.groups.list(search=name) if x.path.lower() == name.lower()][0]
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
            fullpath = os.path.abspath(path)
            wsdir = self.workspace_dir + os.path.sep
            proj = fullpath.split(wsdir)[1].replace("\\","/")
            url =  git.config(f"--get submodule.{proj}.url",
                              execution_path=self.workspace_dir).split('/')
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
        return [r.name for r in self.group.projects.list()]

    def repo(self, name):
        project_id = [x.id for x in self.group.projects.list(search=name) if x.name == name][0]
        return Repo(self.gitlab.projects.get(project_id), self.gitlab)


class Repo:
    def __init__(self, gitlab_project, gitlab ):
        self.project = gitlab_project
        self.gitlab = gitlab
        
    # state can be "all", "merged", "opened", or "closed"
    def pullRequests(self, direction= "IGNORED", at=None, state="opened", target_branch=None, source_branch=None):
        # translates from bitbucket to gitlab state types
        state_dict = {"open":"opened", "opened":"opened",
                      "merged": "merged",
                      "declined":"closed", "closed":"closed",
                      "all":"all"
                      }
        state = state_dict[state.lower()]
        return [PullRequest(x, self.gitlab) for x in self.project.mergerequests.list(state=state, target_branch=target_branch, source_branch=source_branch) ]

    def getOpenPullRequest(self, source, target):
        requests = self.pullRequests(state="opened", target_branch=target, source_branch=source)
        return requests[0] if requests else None

    def getMergedPullRequests(self, source, target):
        return self.pullRequests(state="merged", target_branch=target, source_branch=source)

    def createPullRequest(self, title, branch, target_branch, description=None, reviewers=None):
         print(f"IN CREATE WITH reviewers {reviewers}")
         mr = PullRequest(self.project.mergerequests.create({"source_branch": branch,
                                            "target_branch": target_branch,
                                            "title": title}),
                          self.gitlab)
         mr.update(title, description=description, reviewers=reviewers)

         return mr


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
        approval_rule = None
        approval_rules = self.mergerequest.approval_rules.list()
        for ar in approval_rules:
            if ar.name == GRAPE_GITLAB_APPROVAL_RULE_NAME:
                approval_rule = ar
                break

        if approval_rule is None:
            return []
        ret = {}
        for approver in ar.eligible_approvers:
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

    # reviewers is a list of usernames
    def update(self, ver, title=None, description=None, reviewers=None):
        if title:
            self.mergerequest.title = title
        if description:
            self.mergerequest.description = description
        if reviewers:
            reviewer_ids = []
            for r in reviewers:
                gitlab_reviewer = self.gitlab.users.list(username=r)[0]
                reviewer_ids.append(gitlab_reviewer.id)
            self.mergerequest.approvals.set_approvers(len(reviewers),approver_ids=reviewer_ids, approval_rule_name=GRAPE_GITLAB_APPROVAL_RULE_NAME)
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
               f"Description: {self.description()}\n"

    def merge(self):
        try:
            self.mergerequest.merge()
            return True
        except gitlab.exceptions.GitlabMRClosedError:
            return False


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

