# FAQ about the EPFL clusters and the setup of this repo
This is a list of questions that might pop up when you use the IC and RCP clusters.

If you encounter problems that are not covered in this list or in the [main readme](README.md), either ...
* Please reach out to the colleagues and other members of the group (e.g. via the #cluster or #it channel on Slack) -- someone might know the answer :)
* If there are errors you think you should not be getting, open a ticket to `support-icit@epfl.ch` (for IC cluster) or `supportrcp@epfl.ch` (for RCP cluster)
* When appropriate and it's a common error, add the problem and solution to this list to keep it up to date!


___ 
<details>
<summary><i>I'm confused by the storages mlodata, mloscratch... Where should I store my files or training data ?</i> </summary>
We agreee that the storage system can be confusing -- simply put: keep everything in your personal home folder on mloscratch, including training data, because only scratch can be mounted on a pod. The other storage mlodata is just for very long-term (e.g. replication for published papers). Moving things onto the cluster or between folders can also be done easily via [HaaS machine](README.md#the-haas-machine). For more details on storage, see [file management](README.md#file-management) again.
</details>

---

<details>

<summary><i>I want to move data onto the cluster or between mlodata and mloscratch. How do I do that?</i> </summary>
Moving things onto the cluster or between folders can also be done easily via [HaaS machine](README.md#the-haas-machine).
</details>

---

<details>
<summary><i> When connecting to a pod via VS Code, it just opens an empty window. Why is my code not restored?</i> </summary>
Note that when opening the VS code window, it opens the home folder of the pod (not scratch!). You can navigate to your working directory (code) by navigating to `/mloscratch/homes/<your username>`.
</details>

---

<details>
<summary><i> My job is shown as "Pending" since quite some time. Why? </i> </summary>
Make sure that you have requested the correct resources (CPU, memory, GPU, etc.) and that you are not exceeding the limits of the cluster. For example, if you launched the csub script with a node type such as "G10", but you are on RCP, the job will not start because the node type does not exist on RCP. Otherwise, it might just be that the cluster is busy and you need to wait a bit. See the question below.
</details>

---

<details>
<summary><i> Where can I see the usage of the cluster? </i> </summary>
Check the dashboard for the [IC cluster](https://ic-dashboard.epfl.ch/) or the [RCP cluster](https://rcp-dashboard.epfl.ch/).
</details>

---

<details>
<summary><i> Can I create my own Docker images? </i> </summary>
Yes, you can -- see [README.md#creating-a-custom-docker-image](README.md#creating-a-custom-docker-image) for more information.
</details>