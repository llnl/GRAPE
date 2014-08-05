import os
import utility
import grapeGit as git


def parseSubtreeRemote(subtreeRemote): 
    path = subtreeRemote.strip().split('/')
    if "ssh:" == path[0] or "https:" == path[0]:  
        return subtreeRemote
    if ".." != path[0]:
        return subtreeRemote

    # extension = path[-1].strip()[-4:]
    # if extension != ".git":
    #     print("Invalid subtree path - expected .git extension for relative URL, saw %s" % extension)
    #     return None
    # the subtreeRemote is a relative path
    originURL = git.config("--get remote.origin.url", quiet=True).strip().split('/')
    
    n = 1
    #print path, originURL
    while path[-n] != "..": 
        originURL[-n] = path[-n]
        n += 1

    return '/'.join(originURL)


