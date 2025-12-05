# Managing Workflows and Advanced Topics

This guide covers day-to-day workflows, pod management, file operations, and important best practices when working with the EPFL RCP cluster.

## Table of Contents

- [Using VS Code](#using-vs-code)
- [Managing Pods](#managing-pods)
- [Important Notes and Workflow](#important-notes-and-workflow)
- [The HaaS Machine](#the-haas-machine)
- [File Management](#file-management)

---

## Using VS Code

To easily attach a VS Code window to a running pod:

1. **Install required extensions**  
   - [Kubernetes](https://marketplace.visualstudio.com/items?itemName=ms-kubernetes-tools.vscode-kubernetes-tools)
   - [Dev Containers](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers)

2. **Connect to your pod**  
   - In VS Code, navigate to: **Kubernetes** → **rcp-cluster** → **Workloads** → **Pods**
   - Right-click on your pod and select **Attach Visual Studio Code**
   - This will start a VS Code session attached to your pod

3. **Navigate to your workspace**  
   - The symlinks ensure that settings and extensions are stored in `/mloscratch/homes/<gaspar_username>` and shared across pods
   - Note: VS Code opens the home folder of the pod (not scratch!) by default
   - Navigate to `/mloscratch/homes/<your_username>` to access your working directory

**Pictorial guide**: See the [official RCP documentation](https://wiki.rcp.epfl.ch/en/home/CaaS/FAQ/how-to-vscode) for screenshots and additional details.

---

## Managing Pods

After starting pods with `csub.py`, you can manage them using run:ai commands:

### Basic Commands

```bash
# Open an interactive shell on the pod
runai exec <pod_name> -it -- zsh

# Kill the job and remove it from the list
runai delete job <pod_name>

# Show information on the status/execution of the job
runai describe job <pod_name>

# List all jobs and their status
runai list jobs

# Show the output/logs for the job
runai logs <pod_name>
```

### Useful One-Liners

```bash
# Clean up succeeded jobs from run:ai
runai list | grep " Succeeded " | awk '{print $1}' | parallel runai delete job {}

# Overview of active jobs that fits on your screen
runai list jobs | sed '1d' | awk '{printf "%-42s %-20s\n", $1, $2}'

# Auto-updating listing of jobs and their states (refreshes every 10 seconds)
watch -n 10 "runai list | sed 1d | awk '{printf \"%0-40s %0-20s\n\", \$1, \$2}'"
```

---

## Important Notes and Workflow

### Job Types

- **Interactive jobs** (default)
  - Used for development and debugging
  - Each user can have **1 interactive GPU**
  - Higher priority than training jobs
  - Can live up to **12 hours**
  - Created with: `python csub.py -n sandbox`

- **Training jobs** (use `--train` flag)
  - Used for actual experiments
  - Allows **more than 1 GPU** (up to 8 on one node)
  - Pod is automatically killed when your code finishes (saves money!)
  - Created with: `python csub.py -n experiment --train --command "..."`

### GPU Selection

When choosing GPU types on the RCP cluster, consider both **cost** and **memory/compute requirements**:

| GPU Type | Memory | Best For | Cost |
|----------|--------|----------|------|
| **V100** | 40GB | Older hardware, not memory-intensive | Lower cost, faster to schedule |
| **A100-40GB** | 40GB | Most use cases (default) | Moderate |
| **A100-80GB** | 80GB | Standard memory-intensive workloads | Moderate |
| **H100** | 80GB | High compute requirements | Higher cost |
| **H200** | 140GB | Very memory-intensive workloads | Highest cost |

**Usage:**
- With `csub.py`: Use `--node_type` flag (e.g., `--node_type default` for A100)
- With CLI directly: Use `--node-pools` flag

**Options:** `v100`, `h100`, `h200`, `default` (A100), `a100-40g`

> [!TIP]
> If you plan to run a series of jobs, especially with high-end GPUs like H100/H200, inform your supervisor in advance.

### Best Practices

> [!IMPORTANT]
> **Work within `/mloscratch`**
> - This is the shared storage mounted to your pod
> - Create a directory: `/mloscratch/homes/<your_username>` (automatically created by `csub.py`)
> - All your files should be kept inside your personal folder
> - Use a GitHub repo to store your code and clone it inside your folder

> [!IMPORTANT]
> **Remember: your job can get killed anytime**
> - run:ai may preempt your job to make space for other users
> - Always implement **checkpointing and recovery** in your scripts
> - Check job status regularly with `runai list`
> - Failed jobs must be deleted before restarting: `runai delete job <name>`

> [!TIP]
> **Recommended workflow**
> - **CPU-only pod for development**: Create a cheap (~3 CHF/month) CPU-only pod for code development and debugging through VS Code
> - **GPU pods for experiments**: When your code is ready, create GPU pods to run experiments
> - **Use training jobs**: Always use `--train` flag for experiments to automatically kill pods when finished

> [!CAUTION]
> **Using the cluster creates costs**
> - Do not forget to stop your jobs when not in use!
> - Use training jobs to automatically kill pods when experiments finish
> - Monitor your active jobs regularly

---

## The HaaS Machine

The HaaS machine is provided by IT and allows you to:
- Move files between storage systems
- Create folders
- Copy files between `mlodata1`, `mloraw1`, and `mloscratch`
- Access storage without creating a pod

### Accessing the HaaS Machine

```bash
ssh <gaspar_username>@haas001.rcp.epfl.ch
```

Use your **Gaspar password** to log in.

### Storage Locations

The volumes are mounted at:
- `/mnt/mlo/mlodata1` - Long-term replicated storage
- `/mnt/mlo/mloraw1` - Reserved for future use
- `/mnt/mlo/scratch` - High-performance working storage

---

## File Management

### Understanding Storage

> [!IMPORTANT]
> **Cluster pods are ephemeral**
> - Any file created inside a pod (outside mounted storage) will be deleted when the pod is killed
> - Always store your work on mounted network disks

### Storage Types

#### `mloscratch` (Primary Working Storage)

- **Purpose**: All code and experimentation
- **Location**: `/mloscratch/homes/<your_username>`
- **Characteristics**:
  - High-performance storage
  - Mounted to all pods
  - Not replicated across multiple hard drives (but generally reliable)
  - All your daily work should be here

#### `mlodata1` (Long-term Archive)

- **Purpose**: Long-term storage with replication
- **Characteristics**:
  - Backed up carefully with replication
  - Stored on multiple hard drives
  - For artifacts you want to keep indefinitely (e.g., paper results, final checkpoints)
  - **Cannot be mounted on pods** (use HaaS machine to access)

#### `mloraw1` (Reserved)

- **Status**: Not currently in active use (status: December 2023)
- **Cannot be mounted on pods** (use HaaS machine to access)

### Moving Data Between Storage

Since `mloscratch` is not replicated, move important artifacts to `mlodata1` for permanent storage.

**To move files between `mlodata1` and `scratch`:**

1. SSH into the HaaS machine:

```bash
ssh <gaspar_username>@haas001.rcp.epfl.ch
```

2. Copy files using `cp` or `rsync`:

```bash
# Example: Copy from scratch to mlodata1
rsync -avP /mnt/mlo/scratch/homes/<username>/results /mnt/mlo/mlodata1/<username>/

# Example: Copy from mlodata1 to scratch
rsync -avP /mnt/mlo/mlodata1/<username>/dataset /mnt/mlo/scratch/homes/<username>/
```

> [!NOTE]
> **TODO:** This section will be updated with permanent machine information for MLO once available.

---

## Additional Resources

- **FAQ**: See [`faq.md`](faq.md) for common questions and troubleshooting
- **csub.py reference**: See main [README.md](../README.md#csubpy-usage-and-arguments) for detailed argument documentation
- **Architecture details**: See [`README.md`](README.md) for deep dive into how the setup works
- **Multi-node training**: See [`multinode.md`](multinode.md) for distributed training documentation
- **Run:ai CLI**: See [`runai_cli.md`](runai_cli.md) for alternative workflows

