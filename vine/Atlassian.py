import sys
import os
filedir = os.path.dirname(os.path.realpath(__file__))
grapedir = os.path.join(filedir, "..")
if not grapedir in sys.path:
    sys.path.append(grapedir)
import stashy.stashy as stashy
import keyring.keyring as keyring
import getpass
import time
import utility


class Atlassian:
    rzstashURL = "https://rzlc.llnl.gov/stash"

    def __init__(self, username=None, url=rzstashURL, verify=True):

        if username is None:
            self._userName = utility.getUserName()
        else:
            self._userName = username

        self.keyring = keyring.get_keyring()
        self._service = url
        password = keyring.get_password(self._service, self._userName)

        if self.auth(self._service, self._userName, password, verify=verify):
            self.url = url
            print("Connected to Stash.")
        else:
            self._stash = None
            print("Could not connect to Stash...")

    def auth(self, service, username, password, verify=True):
        self._userName = username
        self._service = service
        self._stash = stashy.connect(service, username, password, verify=verify)
        numAttempts = 0
        success = False
        while numAttempts < 3 and not success:
            try:
                self._stash.projects.list()
                success = True
            except stashy.errors.AuthenticationException:
                if numAttempts == 0:
                    print("session expired...")
                else:
                    print("incorrect username / password...")
                    self._userName = utility.getUserName(self._userName)
                keyring.set_password(service, self._userName, getpass.getpass("Enter password for %s: " % service))
                self._stash = stashy.connect(service, self._userName, keyring.get_password(service, self._userName),
                                            verify=verify)
                numAttempts += 1

        return success

    def projectlist(self):
        projects = self._stash.projects.list()
        return [r["key"] for r in projects]
    
    def project(self, name):

        for node in self._stash.projects:
            if node["key"].lower() == name.lower():
                r = self._stash.projects[name]
                return Project(r, node)
            
        return None


class StashyNode:
    def __init__(self, node):
        self.node = node

    def show(self):
        self._show(self.node)

    def _show(self, d, level=0):
        keys = d.keys()
        keys.sort()
        for key in keys:
            val = d[key]
            if type(val) in (str, unicode, bool, int):
                print "  "*level, key, "  :  ", val
            elif type(val) == dict:
                print "  "*level, key
                self._show(val, level + 1)
            elif type(val) == list:
                dd = {}
                for i in range(len(val)):
                    dd["%s[%d]" % (key, i)] = val[i]
                print "  "*level, key
                self._show(dd, level + 1)
            else:
                print "  "*level, key, type(val), "???"


class Project(StashyNode):
    def __init__(self, proj, node):
        StashyNode.__init__(self, node)
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
        StashyNode.__init__(self, node)
        self.repo = rpo

    def pullRequests(self, direction= "OUTGOING", at=None, state="OPEN"):
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

    def createPullRequest(self, title, branch, target_branch, description=None, reviewers=None):
        """reviewers"""
        stashyRequest = self.repo.pull_requests.create(title,branch,target_branch,description=description,reviewers=reviewers)
        
        return PullRequest(stashyRequest,self.repo.pull_requests)

class PullRequest(StashyNode):
    """
    node is the dictionary with the state of the Pull Request. 
    stashy_pull_requests is the stashy object needed to update the pull request.    
    """
    def __init__(self, node, stashy_pull_requests):
        StashyNode.__init__(self, node)
        self._stashy_pull_requests = stashy_pull_requests

    def author(self):
        return self.node["author"]["user"]["name"]
    
    def description(self):
        try:
            return self.node["description"].encode('ascii', 'ignore')
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
        #Stash REST API for reviewer definition snippet:
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

    def state(self):
        return self.node["state"]
    
    def title(self):
        return self.node["title"]
    
    def fromRef(self):
        return self.node["fromRef"]["displayId"]
        
    def toRef(self):
        return self.node["toRef"]["displayId"]

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
    
    # reviewers is a list of username-approved(bool) pairs
    def update(self, ver, title=None, description=None, reviewers=None): 
        #Stash REST API for reviewer definition snippet:
        # "reviewers": [
        #     {
        #         "user": {
        #             "name": "charlie"
        #         }
        #     }
        #   ]       
        reviewerList = []
        if reviewers is not None:
            for r in reviewers:
                reviewerList.append(dict(user=dict(name=r)))
                
        stashy_request = self._stashy_pull_requests[str(self.node["id"])]
        return PullRequest(stashy_request.update(ver,title=title,description=description,reviewers=reviewerList), self._stashy_pull_requests)
        

    def __eq__(self, other):
        return (self.toRef() == other.toRef()) and (self.fromRef() == other.fromRef())

    def __str__(self):
        return "Title: %s\n" % self.title() + "From: %s\n" % self.fromRef() + "To: %s\n" % self.toRef() + \
            "Reviewers: %s\n" % ', '.join(r[0]+" (%s)" % ("Approved" if r[1] else "Not yet approved") for r in self.reviewers()) + "Description: %s\n" % self.description()


if __name__ == "__main__":
    atlassian = Atlassian()
    plist = atlassian.projectlist()
    print plist
    for p in plist:
        print "\nPROJECT:", p
        project = atlassian.project(p)
        reponames = project.repolist()
        for reponame in reponames:
            print " REPONAME", reponame
            try:
               repo = project.repo(reponame)
               for pull in repo.pullRequests():

                   print "  TITLE:     ", pull.title()
                   print "  STATE:     ", pull.state()
                   print "  AUTHOR:    ", pull.author()
                   print "  DATE:      ", pull.date()
                   print "  REVIEWERS: ", pull.reviewers()
                   print "  FROM:      ", pull.fromRef()
                   print "  TO:        ", pull.toRef()
                   print "  DESC:      ", pull.description()

                   print 
            except stashy.errors.NotFoundException:
               print "  repo not found"


class TestStashResponse(dict):

    def __getitem__(self, item):
        try:
            return super(TestStashResponse, self).__getitem__(item)
        except KeyError:
            print ("TESTSTASH: resource %s does not exist" %item)
            self.status_code = 999
            raise stashy.errors.GenericException(self)

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
        self.url = "https://testStash.grapeTesting.org/stash/"
        self.projects = TestStashResponse(proj1=TestProject("proj1", self.url), proj2=TestProject("proj2", self.url))
        pass

    def project(self,name):
        return self.projects[name]



class TestAtlassian:
    """
    A version of an Atlassian Stash server that is meant to emulate the responses of Stash for testing purposes.

    """
    def __init__(self, username = None):

        if username is None:
            self.userName = utility.getUserName()
        else:
            self.userName = username
        self.stash = TestStash()
        print("Connected to Stash")
        
    def project(self, name):
        return self.stash.project(name)
