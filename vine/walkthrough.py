import sys,os,tempfile
import option
import grapeConfig
import grapeGit as git
import utility
import re
import threading

try:
   import Tkinter as Tk
   TkinterImportError = None
except ImportError as e:
   TkinterImportError = e
   

class Walkthrough(option.Option):
    """ 
    grape w(alkthrough)
    Usage: grape-w [--difftool=<tool>] [--height=<height>] [--width=<width>] [--showUnchanged] [--noFetch]
                   [--mergeDiff | --rawDiff ]
                   [--noInactive] [--noTopLevel] [--noSubmodules] [--noSubtrees] [--noNestedSubprojects]
                   [<b1>] [--staged | --workspace | <b2>]

    Options:
        --difftool=<tool>           Command to use for diff.
                                    Valid choices are: kdiff3, kompare, tkdiff,
                                       meld, xxdiff, emerge, gvimdiff,
                                       ecmerge, diffuse, opendiff, p4merge, and araxis.
                                    If unspecified, default git difftool will be used.
        --height=<height>           Height of window in pixels.
                                    [default: .grapeconfig.walkthrough.height]
        --width=<width>             Width of window in pixels.
                                    [default: .grapeconfig.walkthrough.width]
        --staged                    Compare staged changes with branch <b1>.
        --workspace                 Compare workspace files with branch <b1>.
        --mergeDiff                 Perform diff of branches from common ancestor (diff <b1>...<b2>) (default).
        --rawDiff                   Perform raw diff of branch files (diff <b1> <b2>).
        --showUnchanged             Show unchanged subprojects.
        --noFetch                   Do not fetch.
        --noInactive                Do not show inactive subprojects.
        --noTopLevel                Do not show outer level project.
        --noSubmodules              Do not show submodules.
        --noSubtrees                Do not show nested subtrees.
        --noNestedSubprojects       Do not show nested subprojects.
        <b1>                        The first branch to compare.
                                    Defaults to the current branch of workspace.
        <b2>                        The second branch to compare.
                                    Defaults to the public branch for <b1>.

    """
    def setDefaultConfig(self, config):
        config.ensureSection("walkthrough")
        config.set('walkthrough', 'height', '400')
        config.set('walkthrough', 'width', '800')
        config.set('walkthrough', 'difftool', 'xxdiff')

    def __init__(self):
        super(Walkthrough, self).__init__()
        self._key = "w"
        self._section = "Code Reviews"

    def description(self):
        return "Walk through diffs between branches"

    def execute(self,args):
        if TkinterImportError:
           utility.printMsg("grape w requires Tkinter.\n  The following error was raised during the import:\n\n%s\n" % TkinterImportError)
           return True
        config = grapeConfig.grapeConfig()
        difftool = args["--difftool"]
        height = args["--height"]
        width = args["--width"]
        doMergeDiff = True
        if args["--rawDiff"]:
           doMergeDiff = False
        elif args["--mergeDiff"]:
           # This is already the default
           doMergeDiff = True

        cwd = os.getcwd()
        os.chdir(utility.workspaceDir())

        b1 = args["<b1>"] 
        if not b1: 
           b1 = git.currentBranch()

        b2 = args["<b2>"]

        if args["--staged"]:
           b2 = b1
           b1 = "--cached"
           doMergeDiff = False
        elif args["--workspace"]:
           b2 = "--"
           doMergeDiff = False
        else:
           if not b2: 
              try:
                 # put the public branch first so merge diff shows
                 # changes on the current branch.
                 b2 = b1
                 b1 = config.getPublicBranchFor(b2)
              except:
                 b2 = ""
                 doMergeDiff = False

        diffargs = ""
               
        root = Tk.Tk()
        root.title("GRAPE walkthrough")
        
        diffmanager = DiffManager(master=root, height=height, width=width,
                                  branchA=b1, branchB=b2,
                                  difftool=difftool, diffargs=diffargs, doMergeDiff=doMergeDiff,
                                  showUnchanged=args["--showUnchanged"],
                                  showInactive=not args["--noInactive"], showToplevel=not args["--noTopLevel"],
                                  showSubmodules=not args["--noSubmodules"], showSubtrees=not args["--noSubtrees"],
                                  showNestedSubprojects=not args["--noNestedSubprojects"],
                                  noFetch=args["--noFetch"])
        
        root.mainloop()
        
        os.chdir(cwd)

        try:
           root.destroy()
        except:
           pass
        return True

# Base class for navigating files in a workspace
class ProjectManager:
   def __init__(self, master, **kwargs):
      height = kwargs.get('height', 0)
      width  = kwargs.get('width', 0)

      self.master = master
      self.grapeconfig = grapeConfig.grapeConfig()
      self.oldprojindex = 0
      self.showInactive          = kwargs.get('showInactive', True)
      self.showToplevel          = kwargs.get('showToplevel', True)
      self.showSubmodules        = kwargs.get('showSubmodules', True)
      self.showSubtrees          = kwargs.get('showSubtrees', True)
      self.showNestedSubprojects = kwargs.get('showNestedSubprojects', True)

      # Colors
      self.fginit     = kwargs.get('fginit', 'black')
      self.bginit     = kwargs.get('bginit', 'gray')
      self.fgvisited  = kwargs.get('fgvisited', 'slate gray')
      self.bgvisited  = kwargs.get('bgvisited', 'light gray')
      self.fgselected = kwargs.get('fgselected', 'black')
      self.bgselected = kwargs.get('bgselected', 'goldenrod')
      self.fgactive   = kwargs.get('fgactive', 'black')
      self.bgactive   = kwargs.get('bgactive', 'light goldenrod')

      # Panel labels
      # These variables should be set by derived classes
      self.filepanelabel = Tk.StringVar()
      self.projpanelabel = Tk.StringVar()

      # Main resizable window
      self.main = Tk.PanedWindow(master, height=height, width=width, sashwidth=4)
      # Create file navigation pane widgets
      self.filepanel = Tk.Frame()
      self.filelabel = Tk.Label(self.filepanel, textvariable=self.filepanelabel)
      self.filescroll = Tk.Scrollbar(self.filepanel, width=10)
      self.filelist = Tk.Listbox(self.filepanel, background=self.bginit, foreground=self.fginit, selectbackground=self.bgselected, selectforeground=self.fgselected, yscrollcommand=self.filescroll.set, selectmode=Tk.SINGLE)
      self.filescroll.config(command=self.filelist.yview)
      self.filelist.bind("<Double-Button-1>", lambda e: self.spawnDiff())

      # Place file navigation pane widgets
      self.filelabel.pack(side=Tk.TOP, fill=Tk.X)
      self.filescroll.pack(side=Tk.RIGHT, fill=Tk.Y)
      self.filelist.pack(side=Tk.LEFT, fill=Tk.BOTH, expand=1)
      self.filepanel.pack(fill=Tk.BOTH, expand=1)
      
      # Create subproject navigation widgets
      self.projpanel = Tk.Frame()
      self.projlabel = Tk.Label(self.projpanel, textvariable=self.projpanelabel)
      self.projscroll = Tk.Scrollbar(self.projpanel, width=10)
      self.projlist = Tk.Listbox(self.projpanel, background=self.bginit, foreground=self.fginit, selectbackground=self.bgselected, selectforeground=self.fgselected, yscrollcommand=self.projscroll.set, selectmode=Tk.SINGLE)
      self.projscroll.config(command=self.projlist.yview)
      self.projlist.bind("<Double-Button-1>", lambda e: self.chooseProject())

      # Place subproject navigation widgets
      self.projscroll.pack(side=Tk.LEFT, fill=Tk.Y)
      self.projlabel.pack(side=Tk.TOP, fill=Tk.X)
      self.projlist.pack(side=Tk.LEFT, fill=Tk.BOTH, expand=1)
      self.projpanel.pack(fill=Tk.BOTH, expand=1)

      # Populate subproject navigation list 
      utility.printMsg("Populating projects list...")

      self.projects = []
      self.projstatus = []
      self.projtype = []

      # Outer level repo
      if self.showToplevel:
         status = "?"
         self.projects.append("")
         self.projlist.insert(Tk.END, "%s <Outer Level Project>" % status)
         self.projstatus.append(status)
         self.projtype.append("Outer")

      # Nested subprojects
      self.subprojects = []
      if self.showNestedSubprojects:
         activeNestedSubprojects = (grapeConfig.GrapeConfigParser.getAllActiveNestedSubprojectPrefixes())
         self.projects.extend(activeNestedSubprojects)
         self.subprojects.extend(activeNestedSubprojects)
         for proj in activeNestedSubprojects:
            status = "?"
            self.projlist.insert(Tk.END, "%s %s <Nested Subproject>" % (status, proj))
            self.projstatus.append(status)
            self.projtype.append("Active Nested")
         if self.showInactive:
            inactiveNestedSubprojects = list(set(grapeConfig.grapeConfig().getAllNestedSubprojects()) - set(grapeConfig.GrapeConfigParser.getAllActiveNestedSubprojects()))
            self.projects.extend(inactiveNestedSubprojects)
            self.subprojects.extend(inactiveNestedSubprojects)
            for proj in inactiveNestedSubprojects:
               status = "?"
               self.projlist.insert(Tk.END, "%s %s <Inactive Nested Subproject>" % (status, proj))
               self.projstatus.append(status)
               self.projtype.append("Inactive Nested")

      # Submodules
      self.submodules = []
      if self.showSubmodules:
         activeSubmodules = (git.getActiveSubmodules())
         self.projects.extend(activeSubmodules)
         self.submodules.extend(activeSubmodules)
         for proj in activeSubmodules:
            status = "?"
            self.projlist.insert(Tk.END, "%s %s <Submodule>" % (status, proj))
            self.projstatus.append(status)
            self.projtype.append("Submodule")
         if self.showInactive:
            inactiveSubmodules = list(set(git.getAllSubmodules()) - set(git.getActiveSubmodules()))
            self.projects.extend(inactiveSubmodules)
            self.submodules.extend(inactiveSubmodules)
            for proj in inactiveSubmodules:
               status = "?"
               self.projlist.insert(Tk.END, "%s %s <Inactive Submodule>" % (status, proj))
               self.projstatus.append(status)
               self.projtype.append("Inactive Submodule")

      # Subtrees
      self.subtrees = []
      if self.showSubtrees:
         self.subtrees = [ self.grapeconfig.get('subtree-%s' % proj, 'prefix') for proj in self.grapeconfig.get('subtrees', 'names').strip().split() ]
         self.projects.extend(self.subtrees)
         for proj in self.subtrees:
            status = "?"
            self.projlist.insert(Tk.END, "%s %s <Subtree>" % (status, proj))
            self.projstatus.append(status)
            self.projtype.append("Subtree")

      utility.printMsg("Done.")

      # Resize the project pane based on its contents
      self.projlistwidth = 0
      self.numprojects = 0
      for proj in self.projlist.get(0, Tk.END):
         if len(proj) > self.projlistwidth:
            self.projlistwidth = len(proj)
         self.numprojects += 1
      self.projlist.config(width=self.projlistwidth)

      # Place the panes in the main window 
      self.main.add(self.projpanel)
      self.main.add(self.filepanel)
      self.main.pack(fill=Tk.BOTH, expand=1, side=Tk.BOTTOM)

   def chooseProject(self):
      oldlabel = self.projpanelabel.get()
      self.projpanelabel.set("Working...")
      self.master.update()
      index = self.projlist.index(Tk.ACTIVE)
      self.projlist.itemconfig(self.oldprojindex, bg=self.bgvisited, fg=self.fgvisited)
      try:
         self.initFiles(index)
         self.projlist.itemconfig(index, bg=self.bgactive, fg=self.fgactive)
         self.oldprojindex = index
      except:
         pass
      self.projpanelabel.set(oldlabel)
      self.master.update()

   def spawnDiff(self):
      index = self.filelist.index(Tk.ANCHOR)
      try:
         file = self.filenames[index]
         if file != "":
            t = threading.Thread(target=self.execute, kwargs={'file':file})
            t.start()
            self.filelist.itemconfig(index, bg=self.bgvisited, fg=self.fgvisited)
      except:
         pass

   def setProjectStatus(self, index, status):
      oldString = self.projlist.get(index)
      newString = status + oldString[1:]
      self.projstatus[index] = status
      self.projlist.delete(index)
      self.projlist.insert(index, newString)

   def removeProjectEntry(self, index):
      del self.projects[index]
      self.projlist.delete(index)
      del self.projstatus[index]
      del self.projtype[index]

   # This should be implemented by derived classes
   def initFiles(self, index):
      pass

   # This should be implemented by derived classes
   def execute(self, file):
      pass

class DiffManager(ProjectManager):
   def __init__(self, master, **kwargs):
      validDiffTools = [ 'kdiff3', 'kompare', 'tkdiff', 'meld', 'xxdiff', 'emerge', 'gvimdiff', 'ecmerge', 'diffuse', 'opendiff', 'p4merge', 'araxis' ]

      # Configurable parameters
      difftool = kwargs.get('difftool', None)
      if difftool == None: 
         try:
            difftool = git.config("--get diff.tool")
         except:
            pass

         if difftool == "vimdiff":
            utility.printMsg("Using gvimdiff instead of vimdiff.")
            difftool = "gvimdiff"

      if difftool not in validDiffTools:
         utility.printMsg("Using default difftool.")
         self.difftool = "default difftool"
         self.difftoolarg = ""
      else:
         self.difftool = difftool
         self.difftoolarg = "-t %s" % difftool

      self.diffargs = kwargs.get('diffargs', "")
      self.noFetch = kwargs.get('noFetch', False)
      self.branchA = self.getBranch(kwargs.get('branchA', ""))
      self.branchB = self.getBranch(kwargs.get('branchB', ""))
      self.diffbranchA = ""
      self.diffAnnotationA = Tk.StringVar()
      self.diffAnnotationA.set(self.branchA)
      self.diffbranchB = ""
      self.diffAnnotationB = Tk.StringVar()
      self.diffAnnotationB.set(self.branchB)
      self.showUnchanged = kwargs.get('showUnchanged', False)
      self.doMergeDiff = kwargs.get('doMergeDiff', True)

      # Branch specification pane
      self.branchpane = Tk.Frame(master)
      self.branchlabelA= Tk.Label(self.branchpane, text="Branch A:")
      self.branchnameA= Tk.Label(self.branchpane, textvariable=self.diffAnnotationA)
      self.branchlabelB= Tk.Label(self.branchpane, text="Branch B:")
      self.branchnameB= Tk.Label(self.branchpane, textvariable=self.diffAnnotationB)
      self.branchlabelA.pack(side=Tk.LEFT, fill=Tk.Y)
      self.branchnameA.pack(side=Tk.LEFT, fill=Tk.Y)
      self.branchlabelB.pack(side=Tk.LEFT, fill=Tk.Y)
      self.branchnameB.pack(side=Tk.LEFT, fill=Tk.Y)
      self.branchpane.pack(side=Tk.TOP)

      ProjectManager.__init__(self, master, **kwargs)

      # If we are diffing against the workspace, get the status of the workspace
      # and save the set of changed files in the outer project (including submodules).
      changedFiles = None
      
      if self.showToplevel or len(self.submodules) > 0:
         utility.printMsg("Gathering status in outer level project...")
         changedFiles = git.diff("--name-only %s" % self.diffBranchSpec(self.branchA, self.branchB)).split()
         utility.printMsg("Done.")

      # Get the url mapping for all submodules
      if len(self.submodules) > 0:
         submoduleURLMap = git.getAllSubmoduleURLMap()

      utility.printMsg("Examining projects...")

      os.chdir(utility.workspaceDir())
      # Loop over list backwards so we can delete entries
      for index in reversed(range(self.numprojects)):
         dir = self.projects[index]
         type = self.projtype[index]
         haveDiff = False
         if type == "Outer":
            # Outer is always last in the reverse iteration,
            # so all submodule entries should have already been removed.
            haveDiff = len(changedFiles) > 0
         elif type.endswith("Submodule"):
            if not type.startswith("Inactive") or self.showInactive:
               if dir in changedFiles:
                  haveDiff = True
                  changedFiles.remove(dir)
         elif type.endswith("Nested"):
            if type.startswith("Inactive"):
               # It might not be worth the time to check for differences in inactive subprojects
               #TODO
               pass
            else:
               os.chdir(os.path.join(utility.workspaceDir(), dir))
               utility.printMsg("Gathering status in %s..." % dir)
               try:
                  haveDiff = len(git.diff("--name-only %s" % self.diffBranchSpec(self.branchA, self.branchB)).split()) > 0
               except git.GrapeGitError as e:
                  if "unknown revision or path not in the working tree" in e.gitOutput:
                     utility.printMsg("Could not diff %s.  Branch may not exist in %s." % (self.diffBranchSpec(self.branchA, self.branchB), dir))
                  else:
                     raise
                  haveDiff = False
               utility.printMsg("Done.")
               os.chdir(utility.workspaceDir())
            pass
         elif type.endswith("Subtree"):
            nestedFiles = git.diff("--name-only %s %s" % (self.diffBranchSpec(self.branchA, self.branchB), dir)).split()
            if len(nestedFiles) > 0:
               haveDiff = True
               for changedFile in changedFiles:
                  if changedFile.startswith(dir+os.path.sep):
                     changedFiles.remove(changedFile)

         if haveDiff:
            self.setProjectStatus(index, "*")
         elif self.showUnchanged:
            self.setProjectStatus(index, " ")
         else:
            self.removeProjectEntry(index)

      utility.printMsg("Done.")

      self.filepanelabel.set("Double click to launch %s" % self.difftool)
      if len(self.projects) > 0:
         self.projpanelabel.set("Double click to choose a project")
      else:
         self.projpanelabel.set("No differences")

   def diffBranchSpec(self, branchA, branchB):
      if self.doMergeDiff:
         return "%s...%s" % (branchA, branchB)
      else:
         return "%s %s" % (branchA, branchB)
   def getBranch(self, branch):
      if not branch.startswith("--"):
         try:
            git.shortSHA(branch)
         except:
            if not branch.startswith("origin/"):
               branch = "origin/"+branch
         # TODO figure out what to do with SHA's in user input
         # TODO always fetch the origin before diffing?
         # TODO figure out ahead behind (git rev-list --left-right --count develop...develop)
         if not self.noFetch and branch.startswith("origin/"):
            git.fetch("origin", branch.partition("/")[2])
      return branch

   def getSubBranch(self, branch):
      submapping = self.grapeconfig.getMapping('workspace', 'submodulepublicmappings')
      if not branch.startswith("--"):
         branchParts = branch.split("/",1)
         if len(branchParts) == 1 or branchParts[0] == "origin":
            if branchParts[-1] in submapping.keys():
               branchParts[-1] = submapping[branchParts[-1]]
         return "/".join(branchParts)
      else:
         return branch

   def initFiles(self, index):
      self.filelist.delete(0,Tk.END)
      dir = self.projects[index]
      type = self.projtype[index]

      self.diffbranchA = self.branchA
      self.diffbranchB = self.branchB

      if type.endswith("Submodule"):
         self.diffbranchA = self.getSubBranch(self.branchA) 
         self.diffbranchB = self.getSubBranch(self.branchB) 

      if type.startswith("Inactive"):
         remotels = git.gitcmd("ls-remote")
         self.filelist.insert(Tk.END, "<Unable to diff>")
         self.filenames.append("")
      else:
         # TODO handle non-existent branches on subprojects
         os.chdir(os.path.join(utility.workspaceDir(), dir))

         self.diffbranchA = self.getBranch(self.diffbranchA)
         self.diffbranchB = self.getBranch(self.diffbranchB)
         self.filenames = []
         diffoutput = git.diff("--name-status --find-renames --find-copies %s %s ." % (self.diffargs, self.diffBranchSpec(self.diffbranchA, self.diffbranchB))).splitlines()
         statusdict = { "A":"<Only in B>",
                        "C":"<File copied>",
                        "D":"<Only in A>", 
                        "M":"",
                        "R":"<File renamed>",
                        "T":"<File type changed>", 
                        "U":"<File unmerged>", 
                        "X":"<Unknown status>" }
            
         if len(diffoutput) > 0:
            for line in diffoutput:
               [status, file] = line.split(None, 1) 
               statusstring = statusdict[status[0]]
               if status[0] == 'R' or status[0] == 'C':
                  files = file.split(None,1)
                  if status[1:] == '100':
                     filename = ""
                  else:
                     statusstring += "*"
                  filename = files
                  filedisplay = " -> ".join(files)
               else:
                  filedisplay = file
                  filename = file
               if type == "Outer":
                  if filename in self.submodules:
                     continue
                  inSubtree = False
                  for subtree in self.subtrees:
                     if filename.startswith(subtree+os.path.sep):
                        inSubtree = True
                        break
                  if inSubtree:
                     continue
                   
               self.filelist.insert(Tk.END, "%s %s" % (filedisplay, statusstring))
               self.filenames.append(filename)
         if len(self.filelist) == 0:
            self.filelist.insert(Tk.END, "<No differences>")
            self.filenames.append("")

      if self.branchA == "--cached":
         self.diffAnnotationA.set("%s <cached>" % self.diffbranchB)
         self.diffAnnotationB.set("<staged>")
      elif self.branchB == "--":
         self.diffAnnotationA.set(self.diffbranchA)
         self.diffAnnotationB.set("<workspace>")
      else:
         self.diffAnnotationA.set(self.diffbranchA)
         self.diffAnnotationB.set(self.diffbranchB)


   def execute(self, file):
      try:
         cmd = "difftool --find-renames --find-copies  %s -y %s %s -- " % (self.difftoolarg, self.diffargs, self.diffBranchSpec(self.diffbranchA, self.diffbranchB))
         if isinstance(file,list):
            cmd += "\"%s\" \"%s\"" % (file[0], file[1])
         else:
            cmd += "\"%s\"" % file
         difftooloutput = git.gitcmd(cmd, "Failed to launch difftool")
      except git.GrapeGitError as e:
         utility.printMsg("%s (return code %d)\n%s" % (e.msg, e.returnCode, e.gitOutput))
