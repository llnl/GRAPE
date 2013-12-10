import sys
import os
filedir = os.path.dirname(os.path.abspath(__file__))
grapedir = os.path.join(filedir,"..")
if not grapedir in sys.path:
    sys.path.append( grapedir )
import stashy
import keyring
import getpass
import time
import utility

class Atlassian:
    rzstashURL = "https://rzlc.llnl.gov/stash"

    def __init__(self, username = None):

        if username is None:
            self.userName = utility.getUserName()
        else:
            self.userName = username

        self.keyring = keyring.get_keyring()
        service = Atlassian.rzstashURL
        password = keyring.get_password(service,self.userName)

        if self.auth(service,self.userName, password):
            print("Connected to RZStash...")
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
                if (numAttempts == 0):
                    print("session expired...")

                else:
                    print("incorrect username / password...")
                    self.userName = utility.GetUserName(self.userName)
                keyring.set_password(service,self.userName,getpass.getpass("Enter password for %s: " % service))
                self.stash = stashy.connect(service,self.userName,keyring.get_password(service,self.userName))
                numAttempts += 1

        return success

    def projectlist(self):
        projects = self.stash.projects.list()
        return [r["key"] for r in projects]
    
    def project(self, name):

        for node in self.stash.projects:
            if node["key"] == name:
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
            if node["name"] == name:
                r = self.project.repos[name]
                return Repo(r, node)
            
        return None



class Repo(StashyNode):
    def __init__(self, repo, node):
        StashyNode.__init__(self, node)
        self.repo = repo

    def pullrequests(self):
        return [PullRequest(x) for x in self.repo.pull_requests]


class PullRequest(StashyNode):
    def __init__(self, node):
        StashyNode.__init__(self, node)

    def author(self):
        return self.node["author"]["user"]["name"]
    
    def description(self):
        return self.node["description"]

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
        return self.node["fromRef"]["id"]
        
    def toRef(self):
        return self.node["toRef"]["id"]
        
        

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



