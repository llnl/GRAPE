import gridTesting
from testGrape import *

class QuickGridTests(unittest.TestCase):
    def gridtestAddCommitFile(self, project):
        os.chdir(project.projectDir)
        f1name = os.path.join(project.projectDir, "f1")
        writeFile1(f1name)
        commitStr = "testCommit: added f1"
        git.add("f1")
        git.commit("f1 -m \"%s\"" % commitStr)
        log = git.log()
        self.assertTrue(commitStr in log)

if __name__ == "__main__":
    base_dir = os.getcwd()
    empty_project = gridTesting.ResettableProject(os.path.join(base_dir, "empty_project"))

    onedir_project = gridTesting.ResettableProject(os.path.join(base_dir, "onedir_project"))
    onedir_project.addCommands([(os.mkdir, "dir1",),
                                (git.add, "dir1"),
                                (writeFile1, "dir1/f1"),
                                (git.add, "dir1/f1"),
                                (git.commit, "-m \"%s\"" % "Added a single directory with 1 file")])

    projects = [empty_project,
                onedir_project]
    
    gridTesting.gridifyTestClass(projects, QuickGridTests)
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(QuickGridTests))
    result = unittest.TextTestRunner(verbosity=2).run(suite)


    #Clean up all of the Resettable projects
    for project in projects:
        project.tearDown()
