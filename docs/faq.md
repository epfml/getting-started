# FAQ about the EPFL clusters and the setup of this repo
This is a list of questions that might pop up when you use the IC and RCP clusters.

If you encounter problems that are not covered in this list or in the [main readme](../README.md), either ...
* Please reach out to the colleagues and other members of the group (e.g. via the #cluster or #it channel on Slack) -- someone might know the answer :)
* If there are errors you think you should not be getting, open a ticket to `support-icit@epfl.ch` (for IC cluster) or `supportrcp@epfl.ch` (for RCP cluster)
* When appropriate and it's a common error, add the problem and solution to this list to keep it up to date!


___ 
<details>
<summary><i>I'm confused by the storages mlodata, mloscratch... Where should I store my files or training data ?</i> </summary>
We agreee that the storage system can be confusing -- simply put: keep everything in your personal home folder on mloscratch, including training data, because only scratch can be mounted on a pod. The other storage mlodata is just for very long-term (e.g. replication for published papers). Moving things onto the cluster or between folders can also be done easily via <a href="../README.md#the-haas-machine">HaaS machine </a>. For more details on storage, see <a href="../README.md#file-management">file management</a> again.
</details>

___ 
<details>
<summary><i>I submitted my job successfully (at least I did not see any error), but my job does not show up with the command `runai list jobs`.</i> </summary>
We have found a scenario where jobs do not appear after they were submitted with a *wrong* PVC name -- notably, this can happen with the new RCP-Prod that renamed "runai-mlo-$GASPAR_USERNAME-scratch" to "mlo-scratch". Check the <a href=https://rcpepfl.run.ai/workloads>
web interface</a> where your jobs should still be listed. At the moment of writing this, the jobs just end up in neverland and cannot be deleted or stopped :D So the easiest is just to resubmit the job with the correct PVC.
</details>

---

<details>

<summary><i>I want to move data onto the cluster or between mlodata and mloscratch. How do I do that?</i> </summary>
Moving things onto the cluster or between folders can also be done easily via <a href="../README.md#the-haas-machine"> HaaS machine</a>.
</details>

---

<details>
<summary><i> When connecting to a pod via VS Code, it just opens an empty window. Why is my code not restored?</i> </summary>
Note that when opening the VS code window, it opens the home folder of the pod (not scratch!). You can navigate to your working directory (code) by navigating to `/mloscratch/homes/<your username>`.
</details>

---

<details>
<summary><i> My job is shown as "Pending" since quite some time. Why? </i> </summary>
It might just be that the cluster is busy and you need to wait a bit. See the question below.

At the same time, always make sure that you have requested the correct resources (CPU, memory, GPU, etc.) and that you are not exceeding the limits of the cluster. For example, if you launched the csub script with a node type such as "G10", but you are on RCP, the job will not start because the node type does not exist on RCP. 
</details>

---

<details>
<summary><i> Where can I see the usage of the cluster? </i> </summary>
Check the dashboard for the IC cluster (https://ic-dashboard.epfl.ch/) or the RCP cluster (https://rcp-dashboard.epfl.ch/).
</details>

---

<details>
<summary><i> Can I create my own Docker images? </i> </summary>
Yes, you can -- see <a href="../README.md#creating-a-custom-docker-image">../README.md#creating-a-custom-docker-image</a> for more information.
</details>

---

<details>
<summary><i> How do I update the csub.py with other arguments? What's the API? </i> </summary>
The script uses the run:ai yaml API. You can find the documentation (which fields there are, etc.) here: https://docs.run.ai/v2.15/developer/cluster-api/reference/training/ (for training jobs) and https://docs.run.ai/v2.15/developer/cluster-api/reference/interactive/ (interactive jobs).
</details>

---

<details>
<summary><i> I get some permission error such as PermissionError: [Errno 13] Permission denied: '/mloscratch/hf_cache/...`. </i> </summary>
This is probably related to the user and group permissions. Two things: for containers, make sure your user id is yours and the group id is 75545 (which stands for the runai-mlo group).
Also, please add the following line to your .bashrc or .zshrc: umask 007 (e.g. via echo "umask 007" >> ~/.zshrc. Make sure that this is persistent or always done for all containers you use).
If the problem persists, please contact us in the #it or #cluster channel. 

As an explanation, we set up the huggingface cache (via the environment variable HF_HOME=/mloscratch/hf_cache) to be shared between users so that large datasets, checkpoints, ... are not downloaded repeatedly. You can also deactivate the huggingface cache, but it should work; so let us know if there's a problem.
</details>

---

<details>
<summary><i> I keep getting torch cuda out of memory errors, is there a way to ensure I have enough GPU memory available to be allocated? </i> </summary>
If you request one GPU, you also receive the full GPU and its RAM. This means that getting an OOM error means you are saturating the GPU's memory, e.g. 40GB for the A100s on the IT cluster.

You can try and debug your code to see where the memory is being used up. Some tools like nvidia-smi or nvtop might help you with that.
If debugging does not solve your issue, you can try switching to RCP where there are 80GB RAM GPUs.
</details>
