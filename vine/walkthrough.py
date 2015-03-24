import sys,os,tempfile
import option
import grapeConfig
import grapeGit as git
import utility
import re
import threading
import Tkinter as Tk

class Walkthrough(option.Option):
    """ 
    grape w(alkthrough)
    Usage: grape-w [--difftool=<tool>] [--height=<height>] [--width=<width>] [<b1>] [<b2>]
           grape-w [--difftool=<tool>] [--height=<height>] [--width=<width>] [--staged | --workspace] [<b1>]

    Options:
        --difftool=<tool>  Command to use for diff.
                           Valid choices are: kdiff3, kompare, tkdiff,
                              meld, xxdiff, emerge, vimdiff, gvimdiff,
                              ecmerge, diffuse, opendiff, p4merge, and araxis.
                           [default: .grapeconfig.walkthrough.difftool]
        --height=<height>  Height of window in pixels.
                           [default: .grapeconfig.walkthrough.height]
        --width=<width>    Width of window in pixels.
                           [default: .grapeconfig.walkthrough.width]
        --staged           Compare staged changes with cached version.
        --workspace        Compare workspace files with branch.
        <b1>               The first branch to compare.
                           Defaults to the current branch of workspace.
        <b2>               The second branch to compare
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
        config = grapeConfig.grapeConfig()
        difftool = args["--difftool"]
        height = args["--height"]
        width = args["--width"]

        cwd = os.getcwd()
        os.chdir(utility.workspaceDir())

        b1 = args["<b1>"] 
        if not b1: 
            b1 = git.currentBranch()

        if args["--staged"]:
           b2 = b1
           b1 = "--cached"
        elif args["--workspace"]:
           b2 = "--"
        else:
           b2 = args["<b2>"]
           if not b2: 
              try:
                 b2 = config.getPublicBranchFor(b1)
              except:
                 b2 = ""

        diffargs = ""
               
        # TODO: fetch branches (remote tracking?) before diff

        # make sure our remote references are up to date if we're
        # comparing with something in the origin repo
        if 'origin' in b1:
            try: 
                git.fetch("origin", b1)
            except:
                pass

        if 'origin' in b2:
            try: 
                git.fetch("origin", b2)
            except:
                pass

        root = Tk.Tk()
        root.title("GRAPE walkthrough")
        
        diffmanager = DiffManager(master=root, height=height, width=width,
                                  branchA=b1, branchB=b2, difftool=difftool, diffargs=diffargs)
        
        root.mainloop()
        
        os.chdir(cwd)

        try:
           root.destroy()
        except:
           pass
        return True

# Base class for navigating files in a workspace
class ProjectManager:
   def __init__(self, master,
                showInactive=True, showToplevel=True,
                showSubmodules=True, showSubtrees=True, showNestedSubprojects=True,
                height=0, width=0,
                fginit='black', bginit='gray',
                fgvisited='slate gray', bgvisited='light gray',
                fgselected='black', bgselected='goldenrod',
                fgactive='black', bgactive='light goldenrod'):
      self.master = master
      self.grapeconfig = grapeConfig.grapeConfig()
      self.oldprojindex = 0

      # Colors
      self.fginit = fginit
      self.bginit = bginit
      self.fgvisited = fgvisited
      self.bgvisited = bgvisited
      self.fgselected = fgselected
      self.bgselected = bgselected
      self.fgactive = fgactive
      self.bgactive = bgactive

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

      # TODO: Optionally eliminate entries based on status

      # Outer level repo
      if showToplevel:
         status = "?"
         self.projects = [ "" ]
         self.projlist.insert(Tk.END, "%s <Outer Level Project>" % status)
         self.projstatus = [ status ]
         self.projtype = [ "Outer" ]

      # Nested subprojects
      if showNestedSubprojects:
         activeNestedSubprojects = (grapeConfig.GrapeConfigParser.getAllActiveNestedSubprojectPrefixes())
         self.projects.extend(activeNestedSubprojects)
         for proj in activeNestedSubprojects:
            status = "?"
            self.projlist.insert(Tk.END, "%s %s <Nested Subproject>" % (status, proj))
            self.projstatus.append(status)
            self.projtype.append("Active Nested")
         if showInactive:
            inactiveNestedSubprojects = list(set(grapeConfig.grapeConfig().getAllNestedSubprojects()) - set(grapeConfig.GrapeConfigParser.getAllActiveNestedSubprojects()))
            self.projects.extend(inactiveNestedSubprojects)
            for proj in inactiveNestedSubprojects:
               status = "?"
               self.projlist.insert(Tk.END, "%s %s <Inactive Nested Subproject>" % (status, proj))
               self.projstatus.append(status)
               self.projtype.append("Inactive Nested")

      # Submodules
      if showSubmodules:
         activeSubmodules = (git.getActiveSubmodules())
         self.projects.extend(activeSubmodules)
         for proj in activeSubmodules:
            status = "?"
            self.projlist.insert(Tk.END, "%s %s <Submodule>" % (status, proj))
            self.projstatus.append(status)
            self.projtype.append("Submodule")
         if showInactive:
            inactiveSubmodules = list(set(git.getAllSubmodules()) - set(git.getActiveSubmodules()))
            self.projects.extend(inactiveSubmodules)
            for proj in inactiveSubmodules:
               status = "?"
               self.projlist.insert(Tk.END, "%s %s <Inactive Submodule>" % (status, proj))
               self.projstatus.append(status)
               self.projtype.append("Inactive Submodule")

      # Subtrees
      # These should also show up in the outer level repo diff, but this
      # should provide the ability to diff just the subproject.
      if showSubtrees:
         allSubtrees = [ self.grapeconfig.get('subtree-%s' % proj, 'prefix') for proj in self.grapeconfig.get('subtrees', 'names').strip().split() ]
         self.projects.extend(allSubtrees)
         for proj in allSubtrees:
            status = "?"
            self.projlist.insert(Tk.END, "%s %s <Subtree>" % (status, proj))
            self.projstatus.append(status)
            self.projtype.append("Subtree")

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
      index = self.projlist.index(Tk.ACTIVE)
      self.projlist.itemconfig(self.oldprojindex, bg=self.bgvisited, fg=self.fgvisited)
      try:
         self.initFiles(index)
         self.projlist.itemconfig(index, bg=self.bgactive, fg=self.fgactive)
         self.oldprojindex = index
      except:
         pass
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

   # This should be implemented by derived classes
   def initFiles(self, index):
      pass

   # This should be implemented by derived classes
   def execute(self, file):
      pass

class DiffManager(ProjectManager):
   def __init__(self, master, height=0, width=0,
                branchA="", branchB="", difftool="", diffargs=""):
      # Configurable parameters
      if difftool == "":
         self.difftool = "default difftool"
         self.difftoolarg = ""
      else:
         self.difftool = difftool
         self.difftoolarg = "-t %s" % difftool
      self.diffargs = diffargs
      self.branchA = branchA
      self.branchB = branchB
      self.diffbranchA = ""
      self.diffAnnotationA = Tk.StringVar()
      self.diffAnnotationA.set(branchA)
      self.diffbranchB = ""
      self.diffAnnotationB = Tk.StringVar()
      self.diffAnnotationB.set(branchB)

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

      ProjectManager.__init__(self, master, height=height, width=width)

      self.filepanelabel.set("Double click to launch %s" % self.difftool)
      self.filepanelabel.set("Double click to choose a project")

      os.chdir(utility.workspaceDir())
      for index in range(self.numprojects):
         dir = self.projects[index]
         type = self.projtype[index]
         haveDiff = False
         if type == "Outer":
            if self.branchA == "--cached":
               if len(git.diff("--cached --name-only").split()) > 0:
                  haveDiff = True
            elif self.branchB == "--":
               shaA = git.shortSHA(self.branchA)
               shaB = re.sub(".*-g","", git.describe("--long --always"))
               if shaA != shaB:
                  haveDiff = True    
               elif git.status("--porcelain -uno --ignore-submodules=dirty") != "":
                  haveDiff = True    
            else:
               haveDiff = (git.shortSHA(self.branchA) != git.shortSHA(self.branchB))
         elif type.endswith("Submodule"):
            if self.branchA == "--cached":
               pass
            elif self.branchB == "--":
               pass
            else:
               shaA = git.gitcmd("ls-tree --abbrev=7 %s %s" % (self.branchA, dir), "Failed to execute ls-tree").split()[2]
               shaB = git.gitcmd("ls-tree --abbrev=7 %s %s" % (self.branchB, dir), "Failed to execute ls-tree").split()[2]
               haveDiff = (shaA != shaB)

         if haveDiff:
            self.setProjectStatus(index, "*")
         else:
            self.setProjectStatus(index, " ")

   def initFiles(self, index):
      self.filelist.delete(0,Tk.END)
      dir = self.projects[index]
      type = self.projtype[index]

      if type.endswith("Submodule"):
         submapping = self.grapeconfig.getMapping('workspace', 'submodulepublicmappings')
         if not self.branchA.startswith("--"):
            branchParts = self.branchA.split("/",1)
            if len(branchParts) == 1 or branchParts[0] == "origin":
               if branchParts[-1] in submapping.keys():
                  branchParts[-1] = submapping[branchParts[-1]]
            self.diffbranchA = "/".join(branchParts)
         if not self.branchB.startswith("--"):
            branchParts = self.branchB.split("/",1)
            if len(branchParts) == 1 or branchParts[0] == "origin":
               if branchParts[-1] in submapping.keys():
                  branchParts[-1] = submapping[branchParts[-1]]
            self.diffbranchB = "/".join(branchParts)
      else:
         self.diffbranchA = self.branchA
         self.diffbranchB = self.branchB

      if self.branchA == "--cached":
         self.diffAnnotationA.set("%s <cached>" % self.diffbranchB)
         self.diffAnnotationB.set("%s <staged>" % self.diffbranchB)
      elif self.branchB == "--":
         self.diffAnnotationA.set(self.diffbranchA)
         self.diffAnnotationB.set("<workspace>")
      else:
         self.diffAnnotationA.set(self.diffbranchA)
         self.diffAnnotationB.set(self.diffbranchB)

      if type.startswith("Inactive"):
         remotels = git.gitcmd("ls-remote")
         self.filelist.insert(Tk.END, "<Unable to diff>")
         self.filenames.append("")
      else:
         os.chdir(os.path.join(utility.workspaceDir(), dir))
         self.filenames = []
         diffoutput = git.diff("--name-status %s %s %s ." % (self.diffargs, self.diffbranchA, self.diffbranchB)).splitlines()
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
               self.filelist.insert(Tk.END, "%s %s" % (file, statusstring))
               self.filenames.append(file)
         else:
            self.filelist.insert(Tk.END, "<No differences>")
            self.filenames.append("")

   def execute(self, file):
      try:
         difftooloutput = git.gitcmd("difftool %s -y %s %s %s \"%s\"" % (self.difftoolarg, self.diffargs, self.diffbranchA, self.diffbranchB, file), "Failed to launch difftool")
      except git.GrapeGitError as e:
         utility.printMsg("%s (return code %d)\n%s" % (e.msg, e.returnCode, e.gitOutput))
