import global_state


def printMsg(msg):
    if global_state.globalVerbosity > 0:
        print("GRAPE: %s" % msg)
