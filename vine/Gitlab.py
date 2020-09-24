import getpass
import logging
import os
import sys
import time
import keyring
import gitlab
from vine import config_parser_global
from vine import grapeGit as git
from vine import utility
from vine.option import Option


# Grape has the following definitions, most strongly correllated with Bitbucket definitions:
# Project - collection of repositories (roughly analogous to a Gitlab Group)
# Repo - the actual repository (roughly analogous to a Gitlap Project)
class GrapeGitlabAdapter:
    rzgitlabURL = "https://rzlc.llnl.gov/gitlab"

    def __init__(self, username=None, url=rzgitlabURL, verify=True, *, workspace_dir):

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

        if self.auth(self._service, self._userName, password, verify=verify):
            self.url = url
            logging.info("Connected to Bitbucket.")
        else:
            self._gitlab= None
            logging.info("Could not connect to Bitbucket...")

    def auth(self, service, username, password, verify=True):
        # set a password to something bogus to trigger an authentication error
        if (password is None):
            password = "123456_bad_password"
        self._userName = username
        self._service = service
        self._gitlab = gitlab.Gitlab(service, password, api_version=4)
        numAttempts = 0
        success = False
        while numAttempts < 3 and not success:
            try:
                print("trying projects.list()")
                projects = self.projectlist()
                if projects:
                    success = True
                else:
                    printf("empty list from gitlab project.")
                    raise Exception 
            except gitlab.exceptions.GitlabAuthenticationError as e:
                print(e, type(e), f"numAttempts is {numAttempts}")
                if numAttempts == 0:
                    logging.info("session expired...")
                else:
                    logging.info("incorrect username / password...")
                    self._userName = utility.getUserName(self._userName)
                keyring.set_password(service, self._userName,
                                     getpass.getpass("Enter personal access token for " +
                                                     f"{service}: "))
                self._gitlab = gitlab.Gitlab(service,  keyring.get_password(service, self._userName), api_version=4)
                print(self._gitlab)
                numAttempts += 1

        return success

    # Return list of project names
    def projectlist(self):
        return [g.name for g in self._gitlab.groups.list()]

    def project(self, name):
        print(f"in project call with {self._gitlab.groups}, name {name}")
        p = Project(self._gitlab.groups.list(search=name)[0], self._gitlab)
        print("Project found")
        return  p
#
#    def repoFromWorkspaceRepoPath(self, path, isSubmodule=False, isNested=False, topLevelRepo=None, topLevelProject=None):
#        config = config_parser_global.grapeConfig()
#        if isNested:
#            proj = os.path.split(path)[1]
#            nestedProjectURL = config.get(f"nested-{proj}", "url")
#            url = git.parseSubprojectRemoteURL(
#                nestedProjectURL, execution_path=self.workspace_dir)
#            urlTokens = url.split('/')
#            proj = urlTokens[-2]
#            repo_name = urlTokens[-1]
#            # strip off the git extension
#            repo_name = '.'.join(repo_name.split('.')[:-1])
#        elif isSubmodule:
#            fullpath = os.path.abspath(path)
#            wsdir = self.workspace_dir + os.path.sep
#            proj = fullpath.split(wsdir)[1].replace("\\","/")
#            url =  git.config(f"--get submodule.{proj}.url",
#                              execution_path=self.workspace_dir).split('/')
#            proj = url[-2]
#            repo_name = url[-1]
#
#            # strip off the .git extension
#            repo_name = '.'.join(repo_name.split('.')[:-1])
#        else:
#            if topLevelRepo is None:
#                topLevelRepo = config.get(Option.SECTION_REPO, "name")
#            if topLevelProject is None:
#                topLevelProject = config.get(Option.SECTION_PROJECT, "name")
#
#            repo_name = topLevelRepo
#            proj = topLevelProject
#
#        repo = self.project(proj).repo(repo_name)
#        return repo
#

class Project:
    def __init__(self, gitlab_group, gitlab):
        self.group = gitlab_group
        self.gitlab = gitlab
        print(f"created Project with gitlab group {self.group}, {self.group.__dict__['_parent_attrs']}")

    def name(self):
        return self.group.name

    def repolist(self):
        print(f"repolist {self.group.list()}")
        return [r.name for r in self.group.list()]

    def repo(self, name):
        return Repo(self.group.projects.list(search=name))


class Repo:
    def __init__(self, gitlab_project, gitlab ):
        #self.project = gitlab.projects.get(gitlab_group_project.id, lazy=True)
        self.project = gitlab_project
        
    # state can be "all", "merged", "opened", or "closed"
    def pullRequests(self, direction= "IGNORED", at=None, state="open"):
        mrs = self.project.mergerequests.list(state=state.lower())
        return [PullRequest(x, self.project.pull_requests) for x in self.repo.pull_requests.all(direction=direction, state=state, at=at)]
#
#    def getOpenPullRequest(self, source, target):
#        ret = None
#        requests = self.pullRequests()
#        for request in requests:
#            if request.toRef() == target and request.fromRef() == source:
#                ret = request
#                break
#        return ret
#
#    def getMergedPullRequests(self, source, target):
#        ret = []
#        requests = self.pullRequests(state="MERGED")
#        for r in requests:
#            if r.toRef() == target and r.fromRef() == source:
#                ret.append(r)
#        return ret
#
#    def createPullRequest(self, title, branch, target_branch, description=None, reviewers=None):
#        """reviewers"""
#        stashyRequest = self.repo.pull_requests.create(title,branch,target_branch,description=description,reviewers=reviewers)
#
#        return PullRequest(stashyRequest,self.repo.pull_requests)
#
#
#
#
#
#class PullRequest(StashyNode):
#    """
#    node is the dictionary with the state of the Pull Request.
#    stashy_pull_requests is the stashy object needed to update the pull request.
#    """
#    def __init__(self, node, stashy_pull_requests):
#        StashyNode.__init__(self, node, stashy_pull_requests[str(node["id"])])
#        self._stashy_pull_requests = stashy_pull_requests
#        self._stashy_pull_request = stashy_pull_requests[str(self.node["id"])]
#
#    def author(self):
#        return self.node["author"]["user"]["name"]
#
#    def authorName(self):
#        return self.node["author"]["user"]["displayName"]
#
#    def description(self):
#        try:
#            return self.node["description"].encode('ascii', 'ignore')
#        except KeyError:
#            return ""
#
#    def date(self):
#        msec = self.node["createdDate"]
#        sec = msec / 1000
#        return time.ctime(sec)
#
#    def reviewers(self):
#        """
#        Returns [(username,bool(approved),displayname)...]
#        """
#        #Bitbucket REST API for reviewer definition snippet:
#        # "reviewers": [
#        #     {
#        #         "user": {
#        #             "name": "charlie"
#        #         }
#        #     }
#        #   ]
#        # Which I interpret to mean the following:
#        ret = []
#        for reviewer in self.node["reviewers"]:
#            name = reviewer["user"]["name"]
#            approved = reviewer["approved"]
#            displayName = reviewer["user"]["displayName"]
#            if displayName == "":
#                displayName = name
#            ret.append((name, approved, displayName))
#        return ret
#
#    def state(self):
#        return self.node["state"]
#
#    def title(self):
#        return self.node["title"]
#
#    def fromRef(self):
#        return self.node["fromRef"]["displayId"]
#
#    def toRef(self):
#        return self.node["toRef"]["displayId"]
#
#    def approved(self):
#        reviewers = self.reviewers()
#        ret = True if len(reviewers) else False
#        for reviewer in reviewers:
#            approved = reviewer[1]
#            ret = ret and approved
#        return ret
#
#    def link(self):
#        return self.node["links"]["self"][0]["href"]
#
#    def version(self):
#        return self.node["version"]
#
#    # reviewers is a list of username-approved(bool) pairs
#    def update(self, ver, title=None, description=None, reviewers=None):
#        #Bitbucket REST API for reviewer definition snippet:
#        # "reviewers": [
#        #     {
#        #         "user": {
#        #             "name": "charlie"
#        #         }
#        #     }
#        #   ]
#        # Older versions of stashy needed this translation, the current one does it for us so we don't need to anymore.
#        # leaving this commented version around in case the magic that appeared in stashy disappears in the future.
#        #reviewerList = []
#        #if reviewers is not None:
#        #    for r in reviewers:
#        #        reviewerList.append(dict(user=dict(name=r)))
#
#        stashy_request = self._stashy_pull_requests[str(self.node["id"])]
#        return PullRequest(stashy_request.update(ver,title=title,description=description,reviewers=reviewers), self._stashy_pull_requests)
#
#
#    def __eq__(self, other):
#        return (self.toRef() == other.toRef()) and (self.fromRef() == other.fromRef())
#
#    def __str__(self):
#        all_reviewers = ', '.join(r[0] + " (%s)" % ("Approved" if r[1] else "Not yet approved") for r in self.reviewers())
#        return f"Title: {self.title()}\n" + \
#               f"From: {self.fromRef()}\n" + \
#               f"To: {self.toRef()}\n" + \
#               f"Reviewers: {all_reviewers}\n" + \
#               f"Description: {self.description()}\n"
#
#    def merge(self):
#        canMerge = self._stashy_pull_request.can_merge()
#        if canMerge is True:
#            response = self._stashy_pull_request.merge(version=self.node["version"])
#            return response["state"] == "MERGED"
#        return False


def testMe():
    grape_gitlab = GrapeGitlabAdapter(workspace_dir=os.getcwd())
    plist = grape_gitlab.projectlist()
    logging.info(plist)
    for p in plist:
        logging.info(f"\nPROJECT:{p}")
        project = grape_gitlab.project(p)
        reponames = project.repolist()
        for reponame in reponames:
            logging.info(f" REPONAME{reponame}")
            try:
                repo = project.repo(reponame)
                for pull in repo.pullRequests():
                    logging.info(f"  TITLE:     {pull.title()}")
                    logging.info(f"  STATE:     {pull.state()}")
                    logging.info(f"  AUTHOR:    {pull.author()}")
                    logging.info(f"  DATE:      {pull.date()}")
                    logging.info(f"  REVIEWERS: {pull.reviewers()}")
                    logging.info(f"  FROM:      {pull.fromRef()}")
                    logging.info(f"  TO:        {pull.toRef()}")
                    logging.info(f"  DESC:      {pull.description()}\n")
            except stashy_errors.NotFoundException:
                logging.info("  repo not found")


if __name__ == "__main__":
    testMe()

