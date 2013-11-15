import option

class Quit(option.Option):
    key = "q"
    section = " OTHER "

    def Description(self):
        return "Quit."

    def Execute(self):
        return True
