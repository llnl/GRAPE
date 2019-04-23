from grape.vine import global_state


def printMsg(msg):
    if global_state.globalVerbosity > 0:
        print(f"GRAPE: {msg}")
