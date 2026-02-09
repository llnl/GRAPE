import getpass
import logging
import os
import sys
import time
from stashy.stashy import connect as stashy_connect
import stashy.stashy.errors as stashy_errors
from vine import GrapeKeyring
from vine import utility


class Atlassian:
    defaultURL = "https://your.host.org/bitbucket"

    def __init__(self, username=None, url=defaultURL, verify=True, port=-1, ssh_path= "git@ssh.org", *,
                 workspace_dir):

        if username is None:
            self._userName = utility.getUserName()
        else:
            self._userName = username

        self.workspace_dir = workspace_dir

        self._service = url
        password = GrapeKeyring.get_password(self._service, self._userName)

        if self.auth(self._service, self._userName, password, verify=verify):
            self.url = url
            logging.info("Connected to Bitbucket.")
        else:
            self._stash = None
            logging.info("Could not connect to Bitbucket...")

    def auth(self, service, username, password, verify=True):
        self._userName = username
        self._service = service
        self._stash = stashy_connect(service, username, password, verify=verify)
        numAttempts = 0
        success = False
        while numAttempts < 3 and not success:
            try:
                self._stash.projects.list()
                success = True
            except stashy_errors.AuthenticationException:
                if numAttempts == 0:
                    logging.info("session expired...")
                else:
                    logging.info("incorrect username / password...")
                    self._userName = utility.getUserName(self._userName)
                GrapeKeyring.set_password(service, self._userName,
                                          getpass.getpass("Enter password for " +
                                                          f"{service}: "))
                self._stash = stashy_connect(service, self._userName, GrapeKeyring.get_password(service, self._userName),
                                            verify=verify)
                numAttempts += 1

        return success
    
    # Return list of project names
    def projectlist(self):
        projects = self._stash.projects.list()
        return [r["key"] for r in projects]

    def project(self, name):

        for node in self._stash.projects:
            if node["key"].lower() == name.lower():
                r = self._stash.projects[name]
                return Project(r, node)

        return None

    def repo(self, project_name, repo_name):
        """
        Retrieve a Bitbucket repository and wrap it in a grape Repo object.

        Parameters
        ----------
        project_name : str
            The name of the Bitbucket project that owns the repository
            (for example, "llnl").
        repo_name : str
            The repository name within the given project
            (for example, "GRAPE").

        Returns
        -------
        Repo
            A Repo instance that wraps the underlying Bitbucket repository.
        """
        return self.project(project_name).repo(repo_name)

class StashyNode:
    def __init__(self, node, stashynode):
        self.node = node
        self.snode = stashynode

    def show(self):
        self._show(self.node)

    def _show(self, d, level=0):
        keys = d.keys()
        keys.sort()
        for key in keys:
            val = d[key]
            if isinstance(val, (str, unicode, bool, int)):
                logging.info("  "*level, key, "  :  ", val)
            elif isinstance(val, dict):
                logging.info("  "*level, key)
                self._show(val, level + 1)
            elif isinstance(val, list):
                dd = {}
                for i in range(len(val)):
                    dd[f"{key}[{i}]"] = val[i]
                logging.info("  "*level, key)
                self._show(dd, level + 1)
            else:
                logging.info("  "*level, key, type(val), "???")

    def get(self, path):
        response = self.snode._client.get(self.snode.url(path))
        return response.json()

    def put(self, path):
        return self.snode._client.put(self.snode.url(path)).json()

    def post(self, path):
        return self.snode._client.post(self.snode.url(path)).json()


class Project(StashyNode):
    def __init__(self, proj, node):
        StashyNode.__init__(self, node, proj)
        self.project = proj

    def name(self):
        return self.node["name"]

    def repolist(self):
        repos = self.project.repos.list()
        return [r["name"] for r in repos]

    def repo(self, name):

        repos = self.project.repos.list()
        for node in repos:
            if node["name"].lower() == name.lower():
                r = self.project.repos[name]
                return Repo(r, node)

        return None


class Repo(StashyNode):
    def __init__(self, rpo, node):
        StashyNode.__init__(self, node, rpo)
        self.repo = rpo

    def getBranchHeadCommitHash(self, name):
        logging.error("GRAPE: ERROR: getBranchHeadCommitHash not implemented for Atlassian")
        exit(1)

    def getFile(self, path, revision):
        logging.error("GRAPE: ERROR: getFile not implemented for Atlassian")
        exit(1)

    def pullRequests(self, direction= "OUTGOING", at=None, state="OPEN", id=None):
        return [PullRequest(x, self.repo.pull_requests) for x in self.repo.pull_requests.all(direction=direction, state=state, at=at)]

    def getOpenPullRequest(self, source, target):
        ret = None
        requests = self.pullRequests()
        for request in requests:
            if request.toRef() == target and request.fromRef() == source:
                ret = request
                break
        return ret

    def getMergedPullRequests(self, source, target):
        ret = []
        requests = self.pullRequests(state="MERGED")
        for r in requests:
            if r.toRef() == target and r.fromRef() == source:
                ret.append(r)
        return ret

    def createPullRequest(self, title, branch, target_branch, description=None, reviewers=None, non_approvers=None, wip=None, labels=[]):
        """reviewers"""
        if labels:
           logging.warning("GRAPE: WARNING: labels are not implemented for Bitbucket Pull Requests")

        flattened_reviewers = set()

        for review_rule_name in reviewers:
            reviewer_group = reviewers[review_rule_name]
            users = reviewer_group['reviewers']

            for user in users:
                flattened_reviewers.add(user)

        flattened_reviewers = list(flattened_reviewers)

        stashyRequest = self.repo.pull_requests.create(title,branch,target_branch,description=description,reviewers=flattened_reviewers)

        return PullRequest(stashyRequest,self.repo.pull_requests)

    def getTag(self, name):
        logging.error("GRAPE: ERROR: getTag not implemented for Atlassian")
        exit(1)

    def createTag(self, name, ref, message):
        logging.error("GRAPE: ERROR: createTag not implemented for Atlassian")
        exit(1)

    def deleteTag(self, name):
        logging.error("GRAPE: ERROR: deleteTag not implemented for Atlassian")
        exit(1)

    def updateTag(self, name, ref, message):
        logging.error("GRAPE: ERROR: updateTag not implemented for Atlassian")
        exit(1)

    def getDiffs(self, fromRevision, toRevision):
        logging.error("GRAPE: ERROR: getDiffs not implemented for Atlassian")
        exit(1)

    def getSuccessfulJob(self, name, current_sha, target_sha, current_branch, target_branch):
        logging.info("GRAPE does not support CI integration with Atlassian tools.")
        return None


class Job:
    """
    A Job object should never be instantiated for Bitbucket.
    """
    def __init__(self):
        pass
    def artifact(self, path):
        return b''



class PullRequest(StashyNode):
    """
    node is the dictionary with the state of the Pull Request.
    stashy_pull_requests is the stashy object needed to update the pull request.
    """
    def __init__(self, node, stashy_pull_requests):
        StashyNode.__init__(self, node, stashy_pull_requests[str(node["id"])])
        self._stashy_pull_requests = stashy_pull_requests
        self._stashy_pull_request = stashy_pull_requests[str(self.node["id"])]

    def author(self):
        return self.node["author"]["user"]["name"]

    def authorName(self):
        return self.node["author"]["user"]["displayName"]

    def authorEmail(self):
        return self.node["author"]["user"]["email"]

    def description(self):
        try:
            # Drop non-ascii characters
            return self.node["description"].encode('ascii', 'ignore').decode('ascii')
        except KeyError:
            return ""

    def date(self):
        msec = self.node["createdDate"]
        sec = msec / 1000
        return time.ctime(sec)

    def reviewers(self):
        """
        Returns [(username,bool(approved),displayname)...]
        """
        #Bitbucket REST API for reviewer definition snippet:
        # "reviewers": [
        #     {
        #         "user": {
        #             "name": "charlie"
        #         }
        #     }
        #   ]
        # Which I interpret to mean the following:
        ret = []
        for reviewer in self.node["reviewers"]:
            name = reviewer["user"]["name"]
            approved = reviewer["approved"]
            displayName = reviewer["user"]["displayName"]
            if displayName == "":
                displayName = name
            ret.append((name, approved, displayName))
        return ret

    def labels(self):
        # Not implemented
        return []

    def state(self):
        return self.node["state"]

    def title(self):
        return self.node["title"]

    def fromRef(self):
        return self.node["fromRef"]["displayId"]

    def toRef(self):
        return self.node["toRef"]["displayId"]

    def fromSHA(self):
        logging.error("GRAPE: ERROR: fromSHA not implemented for Atlassian")
        exit(1)

    def commits(self):
        logging.error("GRAPE: ERROR: commits not implemented for Atlassian")
        exit(1)

    def approve(self):
        logging.error("GRAPE: ERROR: approve not implemented for Atlassian")
        exit(1)

    def iid(self):
        logging.error("GRAPE: ERROR: iid not implemented for Atlassian")
        exit(1)

    def diffs(self):
        logging.error("GRAPE: ERROR: diffs not implemented for Atlassian")
        exit(1)

    def approved(self):
        reviewers = self.reviewers()
        ret = True if len(reviewers) else False
        for reviewer in reviewers:
            approved = reviewer[1]
            ret = ret and approved
        return ret

    def link(self):
        return self.node["links"]["self"][0]["href"]

    def version(self):
        return self.node["version"]

    # reviewers is a list of usernames
    def update(self, ver, title=None, description=None, reviewers=None, non_approvers=None, wip=None, add_labels=[], remove_labels=[]):
        #Bitbucket REST API for reviewer definition snippet:
        # "reviewers": [
        #     {
        #         "user": {
        #             "name": "charlie"
        #         }
        #     }
        #   ]
        # Older versions of stashy needed this translation, the current one does it for us so we don't need to anymore.
        # leaving this commented version around in case the magic that appeared in stashy disappears in the future.
        #reviewerList = []
        #if reviewers is not None:
        #    for r in reviewers:
        #        reviewerList.append(dict(user=dict(name=r)))
        flattened_reviewers = set()

        for review_rule_name in reviewers:
            reviewer_group = reviewers[review_rule_name]
            users = reviewer_group['reviewers']

            for user in users:
                flattened_reviewers.add(user)

        flattened_reviewers = list(flattened_reviewers)

        if add_labels or remove_labels:
           logging.warning("GRAPE: WARNING: labels are not implemented for Bitbucket Pull Requests")
        if non_approvers:
           logging.warning("GRAPE: WARNING: non_approvers not implemented Bitbucket Pull Requests")
        if wip is not None:
           logging.warning("GRAPE: WARNING: wip not implemented Bitbucket Pull Requests")

        stashy_request = self._stashy_pull_requests[str(self.node["id"])]
        return PullRequest(stashy_request.update(ver,title=title,description=description,reviewers=flattened_reviewers), self._stashy_pull_requests)

    def regeneratePipeline(self):
        pass

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
        canMerge = self._stashy_pull_request.can_merge()
        if canMerge is True:
            response = self._stashy_pull_request.merge(version=self.node["version"])
            return response["state"] == "MERGED"
        return False


def testMe():
    atlassian = Atlassian(workspace_dir=os.getcwd())
    plist = atlassian.projectlist()
    logging.info(plist)
    for p in plist:
        logging.info(f"\nPROJECT:{p}")
        project = atlassian.project(p)
        reponames = project.repolist()
        for reponame in reponames:
            logging.info(f" REPONAME{reponame}")
            try:
                repo = project.repo(reponame)
                for pull in repo.pullRequests()[0:1]:
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


class TestStashResponse(dict):

    def __getitem__(self, item):
        try:
            return super(TestStashResponse, self).__getitem__(item)
        except KeyError:
            logging.error(f"TESTBITBUCKET: resource {item} does not exist")
            self.status_code = 999
            raise stashy_errors.GenericException(self)

    def json(self):
        return self


class TestPullRequest(TestStashResponse):
    def __init__(self, title, fromRef, toRef, parent, id="0", description=None, reviewers=[]):
        self.url = parent + id + "/"
        links = dict(self=[dict(href=self.url)])
        toRef = dict(id=id, title=title, fromRef=fromRef, reviewers=reviewers)
        super(TestPullRequest, self).__init__(title=title, fromRef=fromRef, toRef=toRef, id=id,
                                              description=description,
                                              reviewers=reviewers, links=links)

    def toRef(self):
        return self["toRef"]

    def title(self):
        return self["title"]

    def fromRef(self):
        return self["fromRef"]

    def id(self):
        return self["id"]

    def reviewers(self):
        return self["reviewers"]

    def link(self):
        return self["links"]["self"][0]["href"]

    def description(self):
        if self["description"] is not None:
            return self["description"]
        else:
            return ""

class TestPullRequests(TestStashResponse):

    def __init__(self, parent):
        self.url = parent + "pullrequests/"
        self.create("testRequest1", "topic", "develop")

    def all(self, direction="INCOMING", at=None, state="OPEN"):
        for request in self.values():
            yield request

    def create(self, title, fromRef, toRef, description=None, reviewers=[]):
        newId = str(len(self))
        self[newId] = TestPullRequest(title, fromRef, toRef, self.url, id=newId, description=description,
                                      reviewers=reviewers)
        return self[newId]




class TestRepo(TestStashResponse):
    def __init__(self, name, parent):
        self.url = parent + "repos/" + name
        self.name = name
        self.pull_requests = TestPullRequests(self.url)

    def pullRequests(self, direction="OUTGOING", at=None, state="OPEN"):
        return self.pull_requests.all(direction,at,state)

    def createPullRequest(self, title,branch,target_branch, description=None,reviewers=None):

        return self.pull_requests.create(title, branch, target_branch,
                                        description=description,
                                        reviewers=reviewers)



class TestProject(TestStashResponse):
    def __init__(self, name, parent):
        self.url = parent+"projects/"+name+"/"
        self.repos = TestStashResponse(repo1=TestRepo("repo1", self.url))
    def repo(self, name):
        return self.repos[name]


class TestStash(TestStashResponse):

    def __init__(self):
        self.url = "https://testBitbucket.grapeTesting.org/bitbucket/"
        self.projects = TestStashResponse(proj1=TestProject("proj1", self.url), proj2=TestProject("proj2", self.url))
        pass

    def project(self,name):
        return self.projects[name]



class TestAtlassian:
    """
    A version of an Atlassian Bitbucket server that is meant to emulate the responses of Bitbucket for testing purposes.

    """
    def __init__(self, username = None):

        if username is None:
            self.userName = utility.getUserName()
        else:
            self.userName = username
        self.stash = TestStash()
        self.url = "https://your.org/test/bitbucket"
        logging.info("Connected to Bitbucket")

    def project(self, name):
        return self.stash.project(name)
