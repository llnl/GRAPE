import sys,os,tempfile
import option
import grapeGit as git
import utility
import threading
import Tkinter as Tk

class Walkthrough(option.Option):
    """ 
    grape w(alkthrough)
    Usage: grape-w [--use-diff | --use-difftool] [<b1>] [<b2> ] [--] [ <filetree-ish> ]

    Optional Arguments:
        --use-diff      Use 'git diff' for diff command
        --use-difftool  Use 'git difftool' for diff command
        <b1>            The first tree to compare
        <b2>            The second tree to compare
        <filetree-ish>  The files to compare.  

    """
    def __init__(self):
        super(Walkthrough, self).__init__()
        self._key = "w"
        self._section = "Code Reviews"

    def description(self):
        return "Walk through diffs between branches"

    def execute(self,args):
        diffargs = ""
        for key in args.keys():
           if key == "--use-diff":
               pass
           elif key == "--use-difftool":
               pass
           elif args[key]:
               diffargs += " %s" % args[key]

        b1 =  args["<b1>"] 
        if not b1: 
            b1 = utility.userInput("Enter name of branch to compare","HEAD")
        b2 = args["<b2>"] if args["<b2>"] else ""
               
        files = args["<filetree-ish>"]
        if (not files): 
            files = ""

        # make sure our remote references are up to date if we're comparing with something in the origin repo
        if 'origin' in b1 or 'origin' in b2: 
            try: 
                git.fetch()
            except:
                pass

        root = Tk.Tk()
        
        diffmanager = DiffManager(root, diffargs)
        
        root.mainloop()
        
        try:
           root.destroy()
        except:
           pass
        return True

    def setDefaultConfig(self, config):
        pass


bg0 = 'gray'
bg0_ = 'light goldenrod'
bg1 = 'dim gray'
bg1_ = 'slate gray'

class diffButton(Tk.Button):
   def __init__(self, master, diffargs, text):
      Tk.Button.__init__(self, master, text=text, command=self.onClick)
      self.active = True
      self.config(background=bg0)
      self.config(activebackground=bg0_)
      [self.status, self.file] = text.split() 
      self.diffargs = diffargs
   def onClick(self):
      self.config(background=bg1)
      self.config(activebackground=bg1_)
      self.active=False
      t = threading.Thread(target=self.difftool)
      t.start()
      self.pack()
   def difftool(self):
         difftooloutput = git.gitcmd("difftool -y %s %s" % (self.diffargs, self.file), "Failed to launch difftool", quiet=True)

class DiffManager:
   def __init__(self, master, diffargs):
      self.main = Tk.PanedWindow(master)
      self.main.pack(fill=Tk.BOTH, expand=1)
      self.top = Tk.Frame(self.main)
      self.navigate = Tk.PanedWindow(self.main, orient=Tk.VERTICAL)
      self.main.add(self.navigate)
      self.filelist = Tk.Frame(self.main)
      self.main.add(self.filelist)
      self.selector = Tk.Label(self.main, text="top pane")
      self.navigate.add(self.selector)
      self.projects = Tk.Label(self.main, text="bottom pane")
      self.navigate.add(self.projects)
      
      diffoutput = git.diff("--name-status %s" % diffargs, quiet=True).splitlines()
      
      self.buttons = []
      self.width = 0

      if len(diffoutput) > 0:
         for line in diffoutput:
            button = diffButton(self.filelist, diffargs, text=line)
            linewidth = 2*len(line) 
            if linewidth > self.width:
              self.width = linewidth
            self.buttons.append(button)
      else:
         button = Tk.Button(self.filelist, text="No differences", command=master.quit)
         self.buttons.append(button)

      for button in self.buttons:
         button.config(width=self.width, padx=2, font="fixed", justify=Tk.LEFT, anchor=Tk.W)
         button.pack()

      self.main.pack()

