"""Short `colab exec` from colab/launch.sh: start the VM-side CLI client, then return.

GPU runtimes were reclaimed ~20 min after the `colab exec` client in Claude's container lost its kernel websocket
(Claude's container is paused between turns), even with the VM pinging its keep-alive endpoint (CPU runtimes were
not). So the client that runs colab/cli_bootstrap.py in this kernel is the colab CLI on the VM itself
(colab/vm_client.sh), with the Colab-scoped token and session state uploaded by launch.sh. The env this exec sets
(--env ...) stays in the kernel and is seen by the bootstrap, which the VM client runs in the same kernel.
"""
import os
import subprocess

E = os.environ.get
REPO = E("MEMPROF_REPO_DIR", "/content/Agent_Mem_Sys")
BRANCH = E("MEMPROF_BRANCH", "claude/gifted-maxwell-td8cnz")
URL = E("MEMPROF_REPO_URL", "https://github.com/envymoon/Agent_Mem_Sys.git")
os.makedirs("/content/outbox/status", exist_ok=True)
if not os.path.isdir(os.path.join(REPO, ".git")):
    subprocess.run(["git", "clone", "-q", "-b", BRANCH, URL, REPO], check=True)
else:
    subprocess.run(["git", "-C", REPO, "pull", "-q", "--ff-only", "origin", BRANCH])
p = subprocess.Popen(["bash", os.path.join(REPO, "colab", "vm_client.sh"), E("COLAB_SESSION", "memprof")],
                     stdout=open("/content/outbox/status/vm_client.log", "a"), stderr=subprocess.STDOUT,
                     stdin=subprocess.DEVNULL, start_new_session=True, cwd="/content")
print(f"vm_client.sh started, pid {p.pid}")
