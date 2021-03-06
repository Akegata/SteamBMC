import subprocess
import os

"""
shellOutput: Execute a shell command, return the output.

@param      Command to execute

@return     Result of command, as a string
"""
def shellOutput(cmd):
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE, shell=True)
    lines = []
    while True:
        ret = p.poll() 
        line = p.stdout.readline()
        lines.append(line)
        if ret == 0:
            break
    return "\n".join(lines)

"""
getProcessesList: Get the list of running processes.

@return     List of running executables
"""
def getProcessesList():
    tasklist = shellOutput("tasklist")
    tasks = []
    for line in tasklist.split('\n')[5:]:
        parts = line.split('  ') # re.split?
        if len(parts) > 1:
            if parts[0].startswith("System Idle Process") or parts[0].strip() == "System":
                continue
            tasks.append(parts[0].strip())
    return tasks


"""
launchFork: Launch an application (forked execution.) Return immediately. 
            Simply a subprocess wrapper. (For now...)
"""
def launchFork(cmd):
    # Subprocess doesn't work as expected. It creates a new child process. Which it shouldn't.
    # os.system fits our needs perfectly here, because it essentially just pipes the command to the cmd.
    #
    # We also could spawn a process:
    # os.spawnl(os.P_NOWAIT, cmd)
    #
    # Windows specific alternative and usage of subprocess:
    # subprocess.Popen(cmd, close_fds=True)
    #
    # Original way:
    # subprocess.Popen(cmd, shell=True)
    os.system(cmd)

