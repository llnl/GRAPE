import os
from vine import config_parser_global
from vine import grapeGit as git
from vine.option import Option

from vine import Atlassian
from vine import Gitlab

def makeCodeReviews(*args, **kwargs):
    if "bitbucket" in kwargs["url"] or "stash" in kwargs["url"]:
        return Atlassian.Atlassian(*args,**kwargs)
    elif "gitlab" in kwargs["url"]:
        return Gitlab.GrapeGitlabAdapter(*args,**kwargs)

# Return repo object given the nested subproject name (as used in grapeconfig [nestedProjects.names])
def repoFromNestedSubprojectName(codeReviewsObject, subproj_name):
    config = config_parser_global.grapeConfig()
    nestedProjectURL = config.get(f"nested-{subproj_name}", "url")
    url = git.parseSubprojectRemoteURL(
        nestedProjectURL, execution_path=codeReviewsObject.workspace_dir)
    urlTokens = url.split('/')
    proj = urlTokens[-2]
    repo_name = urlTokens[-1]
    # strip off the git extension
    repo_name = '.'.join(repo_name.split('.')[:-1])
    return codeReviewsObject.repo(proj, repo_name)

# Return repo object given the submodule path (relative to the top-level repository)
def repoFromSubmodulePath(codeReviewsObject, submodule_path):
    config = config_parser_global.grapeConfig()
    fullpath = os.path.abspath(os.path.join(codeReviewsObject.workspace_dir,submodule_path))
    wsdir = codeReviewsObject.workspace_dir + os.path.sep
    proj = fullpath.split(wsdir)[1].replace("\\","/")
    url_map = git.getAllSubmoduleURLMap(execution_path=codeReviewsObject.workspace_dir)
    url = url_map[proj].split('/')
    if url[-2] == '..':
        # replace relative path with the top repo project
        topProjectURL = config.get(f"repo", "url").split('/')
        url[-2] = topProjectURL[-2]
    proj = url[-2]
    repo_name = url[-1]

    # strip off the .git extension
    repo_name = '.'.join(repo_name.split('.')[:-1])
    return codeReviewsObject.repo(proj, repo_name)

# Return repo object from repo (Gitlab project) and project (Gitlab group) name.
# Defaults to top-level repository.
def repoObject(codeReviewsObject, repoName=None, projectName=None):
    config = config_parser_global.grapeConfig()
    if repoName is None:
        repoName = config.get(Option.SECTION_REPO, "name")
    if projectName is None:
        projectName = config.get(Option.SECTION_PROJECT, "name")
    repo = codeReviewsObject.repo(projectName, repoName)
    return repo

