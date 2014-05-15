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

    def __init__(self, username=None, url=rzstashURL):

        if username is None:
            self.userName = utility.getUserName()
        else:
            self.userName = username

        self.keyring = keyring.get_keyring()
        service = url
        password = keyring.get_password(service, self.userName)

        if self.auth(service, self.userName, password):
            print("Connected to RZStash...")
            self.url = url
        else:
            self.stash = None
            print("Could not connect to RZStash...")

    

    def auth(self,service,username,password):
        self.userName = username
        self.service = service
        self.stash = stashy.connect(service,username,password)
        numAttempts = 0
        success = False
        while (numAttempts < 3 and not success):
            try:
                project = self.stash.projects.list()
                success = True
            except stashy.errors.AuthenticationException:
                if numAttempts == 0:
                    print("session expired...")

                else:
                    print("incorrect username / password...")
                    self.userName = utility.getUserName(self.userName)
                keyring.set_password(service,self.userName,getpass.getpass("Enter password for %s: " % service))
                self.stash = stashy.connect(service,self.userName,keyring.get_password(service,self.userName))
                numAttempts += 1

        return success

    def projectlist(self):
        projects = self.stash.projects.list()
        return [r["key"] for r in projects]
    
    def project(self, name):

        for node in self.stash.projects:
            if node["key"].lower() == name.lower():
                r = self.stash.projects[name]
                return Project(r, node)
            
        return None




class StashyNode:
    def __init__(self, node):
        self.node = node

    def show(self):
        self._show(self.node)

    def _show(self, d, level = 0):
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
    def __init__(self, project, node):
        StashyNode.__init__(self, node)
        self.project = project

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
    def __init__(self, repo, node):
        StashyNode.__init__(self, node)
        self.repo = repo

    def pullrequests(self, state="OPEN"):
        return [PullRequest(x) for x in self.repo.pull_requests.all(state=state)]

    def getOpenPullRequest(self, source, target):
        ret = None
        requests = self.pullrequests()
        for request in requests:
            if request.toRef() == target and request.fromRef() == source:
                ret = request
                break
        return ret

    def getMergedPullRequests(self, source, target):
        ret = []
        requests = self.pullrequests(state="MERGED")
        for r in requests:
            if r.toRef() == target and r.fromRef() == source:
                ret.append(r)
        return ret




class PullRequest(StashyNode):
    def __init__(self, node):
        StashyNode.__init__(self, node)

    def author(self):
        return self.node["author"]["user"]["name"]
    
    def description(self):
        try:
            return self.node["description"]
        except KeyError:
            return ""

    def date(self):
        msec = self.node["createdDate"]
        sec = msec / 1000
        return time.ctime(sec)

    def reviewers(self):
        ret = []
        for reviewer in self.node["reviewers"]:
            name = reviewer["user"]["name"]
            approved = reviewer["approved"] 
            ret.append( (name, approved) )
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

    def __eq__(self, other):
        return (self.toRef() == other.toRef()) and (self.fromRef() == other.fromRef())

    def __str__(self):
        return "Title: %s\n" % self.title() + "From: %s\n" % self.fromRef() + "To: %s\n" % self.toRef() + \
            "Reviewers: %s\n" % self.reviewers()


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
            repo = project.repo(reponame)
            for pull in repo.pullrequests():

                print "  TITLE:    ", pull.title()
                print "  STATE:    ", pull.state()
                print "  AUTHOR:   ", pull.author()
                print "  DATE  :   ", pull.date()
                print "  REVIWERS: ", pull.reviewers()
                print "  FROM:     ", pull.fromRef()
                print "  TO:       ", pull.toRef()
                print "  DESC  :   ", pull.description()

                print 

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
                                              reviewers=reviewers, links=links)


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



class TestProject(TestStashResponse):
    def __init__(self, name, parent):
        self.url = parent+"projects/"+name+"/"
        self.repos = TestStashResponse(repo1=TestRepo("repo1", self.url))


class TestStash(TestStashResponse):

    def __init__(self):
        self.url = "https://testStash.grapeTesting.org/stash/"
        self.projects = TestStashResponse(proj1=TestProject("proj1", self.url), proj2=TestProject("proj2", self.url))
        pass




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
        print("Connected to RZStash")
