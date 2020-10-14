from vine import Atlassian
from vine import Gitlab

def makeCodeReviews(*args, **kwargs):
    if "bitbucket" in kwargs["url"] or "stash" in kwargs["url"]:
        return Atlassian.Atlassian(*args,**kwargs)
    elif "gitlab" in kwargs["url"]:
        return Gitlab.GrapeGitlabAdapter(*args,**kwargs)
