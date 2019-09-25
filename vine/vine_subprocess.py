import logging
import os
import subprocess


def executeSubProcess(command, working_dir=os.getcwd()):

    logging.debug(f"Executing: \'{command}\'\n\t" +
                  f"Working Directory: {working_dir}")

    completed_process = subprocess.run(command,
                                       capture_output=True,
                                       cwd=working_dir,
                                       shell=True)
    stdout_msg = completed_process.stdout.decode().strip()
    stderr_msg = completed_process.stderr.decode().strip()
    if stdout_msg:
        logging.info(stdout_msg)
    if stderr_msg:
        logging.info(stderr_msg)

    if completed_process.returncode != 0:
        logging.info(f"Command '{command}': exited with error code " +
                     f"{completed_process.returncode}")
    return completed_process
