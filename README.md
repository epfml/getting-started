 # MLO: Getting started with the EPFL Clusters
This repository contains the basic steps to start running scripts and notebooks on the EPFL Clusters (both RCP and IC) -- so that you don't have to go through the countless documentations by yourself! We also provide scripts that can make your life easier by automating a lot of things. It is based on a similar setup from our friends at TML and CLAIRE, and scripts created by Atli :)

There are two clusters available to us: the IC cluster (department only) and the RCP cluster (EPFL-wide). The RCP cluster has A100 (80GB) GPUs, while the IC cluster is equipped with older V100 (32GB) and A100 (40GB) GPUs. You can switch between the two clusters and their respective GPUs. The system is built on top of [Docker](https://www.docker.com) (containers), [Kubernetes](https://kubernetes.io) (automating deployment of containers) and [run:ai](https://run.ai) (scheduler on top of Kubernetes).

For starters, we recommend you to go through the [minimal basic setup](#minimal-basic-setup) first and then read the [important notes](#important-notes-and-workflow). 

If you come up with any question about the cluster or the setup that you do not find answered here, you can check the [frequently asked questions page](docs/faq.md). Also, please do not hesitate to reach out to any of your colleagues. There are some more resources under the [quick links](#quick-links) below.

> [!TIP]
> If you have little prior experience with ML workflows, the setup below may seem daunting at first. But the guide tries to make it as simple as possible for you by providing you all commands in order, and with a script that does most of the work for you. The only requirement is that you have a basic understanding of how to use a terminal and git.

> [!CAUTION]
> Using the cluster creates costs. Please be mindful of the resources you use. **Do not forget to stop your jobs when not used!**

Content overview:
- [MLO: Getting started with the EPFL Clusters](#mlo-getting-started-with-the-epfl-clusters)
- [Minimal basic setup](#minimal-basic-setup)
  - [1: Pre-setup (access, repository)](#1-pre-setup-access-repository)
  - [2: Setup the tools on your own machine](#2-setup-the-tools-on-your-own-machine)
  - [3: Login](#3-login)
  - [4: Use this repo to start a job](#4-use-this-repo-to-start-a-job)
  - [5: Cloning and running your code](#5-cloning-and-running-your-code)
- [Managing Workflows and Advanced Topics](#managing-workflows-and-advanced-topics)
  - [Using VSCODE](#using-vscode)
  - [Managing pods](#managing-pods)
  - [Important notes and workflow](#important-notes-and-workflow)
  - [The HaaS machine](#the-haas-machine)
  - [File management](#file-management)
    - [Moving data onto/between storage](#moving-data-ontobetween-storage)
  - [More background on the csub script](#more-background-on-the-csub-script)
  - [Alternative workflow: using the run:ai CLI and base docker images with pre-installed packages](#alternative-workflow-using-the-runai-cli-and-base-docker-images-with-pre-installed-packages)
  - [Creating a custom docker image](#creating-a-custom-docker-image)
  - [Port forwarding](#port-forwarding)
  - [Distributed training](#distributed-training)
- [File overview of this repository](#file-overview-of-this-repository)
- [Quick links](#quick-links)
  - [Other cluster-related code repositories](#other-cluster-related-code-repositories)


# Minimal basic setup
The step-by-step instructions for first time users to quickly get a job running. 

> [!TIP] 
> After completing the setup, the **TL;DR** of the interaction with the cluster (using the scripts in this repo) is:
> * Choose a cluster and just run the command to set it up: `ic-cluster`, `rcp-cluster`, or `rcp-cluster-prod`
> 
> * Get a running job with one GPU that is reserved for you: `python csub.py -n sandbox`
> 
> * Connect to a terminal inside your job: `runai exec sandbox -it -- zsh`
> 
> * Run your code: `cd /mloscratch/homes/<your username>; python main.py`
>
> * In one go, you can also do: `python csub.py -n experiment --train --command "cd /mloscratch/homes/<your username>/<your code>; python main.py "`

---

> [!IMPORTANT]
> Make sure you are on the EPFL wifi or connected to the VPN. The cluster is otherwise not accessible.

## 1: Pre-setup (access, repository)

**Group access:** You need to have access to the cluster. For that, ask Jennifer or Martin (or someone else) to add you to the group `runai-mlo`: https://groups.epfl.ch/

**Prepare your code:** While you are waiting to get access, create a GitHub repository where you will implement your code. Irrespective of our cluster or this guide, it is best practice to keep track of your code with a GitHub repo.

**Prepare Weights and Biases:** For logging the results of your experiments, you can use [Weights and Biases](https://wandb.ai/). Create an account if you don't already have one. You will need an API key to later log your experiments.

The following are just a bunch of commands you need to run to get started. If you do not understand them in detail, you can copy-paste them into your terminal :)

## 2: Setup the tools on your own machine

> [!IMPORTANT]
> The setup below was tested on macOS with Apple Silicon. If you are using a different system, you may need to adapt the commands.
> For Windows, we have no experience with the setup and thereby recommend WSL (Windows Subsystem for Linux) to run the commands.

1. Install kubectl. To make sure the version matches with the clusters (status: 15.12.2023), on macOS with Apple Silicon, run the following commands. For other systems, you will need to change the URL in the command above (check https://kubernetes.io/docs/tasks/tools/install-kubectl/). Make sure that the version matches with the version of the cluster!
```bash
# Sketch for macOS with Apple Silicon.
# Download a specific version (here v1.29.6 for Apple Silicon macOS)
curl -LO "https://dl.k8s.io/release/v1.29.6/bin/darwin/arm64/kubectl"
# Linux: curl -LO "https://dl.k8s.io/release/v1.29.6/bin/linux/amd64/kubectl"
# Give it the right permissions and move it.
chmod +x ./kubectl
sudo mv ./kubectl /usr/local/bin/kubectl
sudo chown root: /usr/local/bin/kubectl
``` 

2. Setup the kube config file: Take our template file [`kubeconfig.yaml`](kubeconfig.yaml) as your config in the home folder `~/.kube/config`. Note that the file on your machine has no suffix.
```bash
curl -o  ~/.kube/config https://raw.githubusercontent.com/epfml/getting-started/main/kubeconfig.yaml
```

3. Install the run:ai CLI for RCP (two RCP clusters) and IC:
```bash
# Sketch for macOS with Apple Silicon
# Download the CLI from the link shown in the help section.
# for Linux: replace `darwin` with `linux`
wget --content-disposition https://rcp-caas-test.rcp.epfl.ch/cli/darwin
# Give it the right permissions and move it.
chmod +x ./runai
sudo mv ./runai /usr/local/bin/runai-rcp
sudo chown root: /usr/local/bin/runai-rcp

# Repeat for RCP Prod Cluster  
wget --content-disposition https://rcp-caas-prod.rcp.epfl.ch/cli/darwin
chmod +x ./runai
sudo mv ./runai /usr/local/bin/runai-rcp-prod
sudo chown root: /usr/local/bin/runai-rcp-prod

# Repeat for IC Cluster
# for Linux: replace `macos` with `linux`
curl -sLo /tmp/runai https://go.epfl.ch/iccluster-runai-macos
chmod +x ./runai
sudo mv ./runai /usr/local/bin/runai-ic
sudo chown root: /usr/local/bin/runai-ic
```

## 3: Login
1. Switch between contexts and login to both clusters.
```bash
# Switch to the IC cluster
runai-ic config cluster ic-caas
# Login to the cluster
runai-ic login
# Check that things worked fine
runai-ic list projects
# Put default project
runai-ic config project mlo-$GASPAR_USERNAME
# Repeat for the RCP cluster
runai-rcp config cluster rcp-caas-test
runai-rcp login
runai-rcp list projects
runai-rcp config project mlo-$GASPAR_USERNAME
```

2. You probably notice that it's a bit cumbersome to have the different `runai` commands. That is why we have
   litte helper functions (see [template/cluster_switch](template/cluster_switch.sh)) that you can use to switch between the clusters.
   To have these functions available in every terminal session, we add them to your `.zshrc` or `.bashrc` file. 
   On the newest versions of macOS (which this guide is written with), put in your username for `<your username>` below and run the following commands:
```bash
export GASPAR_USERNAME=<your username>
# on linux, replace .zshrc with .bashrc
echo "export GASPAR_USERNAME=$GASPAR_USERNAME" >> ~/.zshrc
curl -s https://raw.githubusercontent.com/epfml/getting-started/main/template/cluster_switch.sh | tee -a ~/.zshrc
source ~/.zshrc
```

3. Run a quick test to see that you can launch jobs:
```bash
# Let's use the normal RCP cluster
rcp-cluster
# Try to submit a job that mounts our shared storage and see its content. (side note: on the new rcp-prod, the pvc is called mlo-scratch, so the arg below has to be changed)
runai submit \
  --name setup-test-storage \
  --image ubuntu \
  --pvc runai-mlo-$GASPAR_USERNAME-scratch:/mloscratch \
  -- ls -la /mloscratch/homes
# Check the status of the job
runai describe job setup-test-storage

# Check its logs to see that it ran.
runai logs setup-test-storage

# Delete the successful jobs
runai delete jobs setup-test-storage
```

The `runai submit` command already suffices to run jobs. If that is fine for you, you can jump to the section on using provided images and the run:ai CLI [here](#alternative-workflow-using-the-runai-cli-and-base-docker-images-with-pre-installed-packages).

However, we provide a few scripts in this repository to make your life easier to get started. 

## 4: Use this repo to start a job
1. Clone this repository and create a `user.yaml` file in the root folder of the repo using the template in `templates/user_template.yaml`.
```bash
git clone https://github.com/epfml/getting-started.git
cd getting-started
touch user.yaml # then copy the content from templates/user_template.yaml inside here and update
```

2. Fill in `user.yaml` with your username, userID in `user.yaml` and also update the working_dir with your username. You can find this information in your profile on people.epfl.ch (e.g. https://people.epfl.ch/alexander.hagele) under “Administrative data”. **Also important for logging** (if you want to use wandb), get an API key from [Weights and Biases](https://wandb.ai/) and add it to the yaml.
   
3. Create a pod with 1 GPU (you may need to install pyyaml with `pip install pyyaml` first).
```bash
rcp-cluster # switch to RCP cluster context
python csub.py -n sandbox
```

4. Wait until the pod has a 'running' status -- this can take a bit (max ~5 min or so). Check the status of the job with 
```bash
runai list # shows all jobs
runai describe job sandbox # shows the status of the job sandbox
```

5. When it is running, connect to the pod with the command:
```bash
runai exec sandbox -it -- zsh
```

6. If everything worked correctly, you should be inside a terminal on the cluster!

## 5: Cloning and running your code
1. Clone your fork of your GitHub repository (where you have your experiment code) into the pod **inside your home folder**.
```bash
# Inside the pod
cd /mloscratch/homes/<your_username>
git clone https://github.com/<your username>/<your code>.git
cd <your code>
```
2. Conda should be automatically installed. To create an environment that contains the packages needed for your experiments, you can do something like
```bash
# inside the pod
conda create -n env python=3.10
conda activate env
# inside /mloscratch/homes/<your username>/<your code>
pip install -r requirements.txt
```
3. Now you can run the code as you would on your local machine. For example, to run a `main.py` script (assuming you wrote it in your code), you simply do:
```bash
# Inside the pod, inside /mloscratch/homes/<your username>/<your code>
python main.py
```

Hopefully, this should work and you're up and running! If you set up Weights and Biases, the API key in the `user.yaml` file should also automatically enable tracking your job on your wandb dashboard (so you can see the loss going down :) )

For remote development (changing code, debugging, etc.), we recommend using VSCode. You can find more information on how to set it up in the [VSCode section](#using-vscode).

> [!TIP]
> Generally, the workflow we recommend is simple: develop your code locally or on the cluster (e.g. with VS Code), then push it to your repository. Once you want to try, run it on the cluster with the terminal that is attached via `runai exec sandbox -it -- zsh`. This way, you can keep your code and experiments organized and reproducible.
>
> Note that your pods **can be killed anytime**. This means you might need to restart an experiment (with the `python csub.py` command we give above). You can see the status of your jobs with `runai list`. If a job has status "Failed", you have to delete it via `runai delete job sandbox` before being able to start the same job again.
> 
> **Keep your files inside your home folder**: Importantly, when a job is restarted or killed, everything inside the container folders of `~/` are lost. This is why you need to work inside `/mloscratch/homes/<your username>`. For conda and other things (e.g. `~/.zshrc`), we have set up automatic symlinks to files that are persistent on scratch.
>
> To have a job that can run in the background, do `python csub.py -n sandbox --train --command "cd /mloscratch/homes/<your username>/<your code>; python main.py "`
>
>  There are differences between the clusters of IC and RCP, which require different tool versions (`runai-ic`, `runai-rcp`, ...). Since this is a bit of a hassle, we made it easy to switch between the clusters via the commands `ic-cluster`, `rcp-cluster` and `rcp-cluster-prod`. To make sure you're aware of the cluster you're using, the `csub` script asks you to set the cluster to use before submitting a job: `python csub.py -n sandbox --cluster ic-caas` (choosing between `["rcp-caas-test", "ic-caas", "rcp-caas-prod"]`). It only works when the cluster argument matches your currently chosen cluster. 

You're good to go now! :) It's up to you to customize your environment and install the packages you need. Read up on the rest of this README to learn more about the cluster and the scripts.

>[!CAUTION]
> Using the cluster creates costs. Please do not forget to stop your jobs when not used!

# Managing Workflows and Advanced Topics

## Using VSCODE
To easily attach a VSCODE window to a pod we recommend the following steps: 
1. Install the [Kubernetes](https://marketplace.visualstudio.com/items?itemName=ms-kubernetes-tools.vscode-kubernetes-tools) and [Dev Containers](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers) extensions.
2. From your VSCODE window, click on Kubernetes -> ic-cluster/rcp-cluster -> Workloads -> Pods, and you should be able to see all your running pods.
3. Right-click on the pod you want to access and select `Attach Visual Studio Code`, this will start a vscode session attached to your pod.
4. The symlinks ensure that settings and extensions are stored in `mloscratch/homes/<gaspar username>` and therefore shared across pods.
5. Note that when opening the VS code window, it opens the home folder of the pod (not scratch!). You can navigate to your working directory (code) by navigating to `/mloscratch/homes/<your username>`.

You can also see a pictorial description [here](https://wiki.rcp.epfl.ch/en/home/CaaS/how-to-vscode).

## Managing pods
After starting pods with the script, you can manage your pods using run:ai and the following commands: 
``` bash
runai exec pod_name -it -- zsh # - opens an interactive shell on the pod 
runai delete job pod_name # kills the job and removes it from the list of jobs
runai describe job pod_name # shows information on the status/execution of the job
runai list jobs # list all jobs and their status 
runai logs pod_name # shows the output/logs for the job
ic-cluster # switch to IC cluster context
rcp-cluster # switch to RCP cluster context
```
Some commands that might come in handy (credits to Thijs):
```bash
# Clean up succeeded jobs from run:ai.
runai list | grep " Succeeded " | awk '{print $1}' | parallel runai delete job {}
# Overview of active jobs that fits on your screen.
runai list jobs | sed '1d' | awk '{printf "%-42s %-20s\n", $1, $2}'
# Auto-updating listing of jobs and their states.
watch -n 10 "runai list | sed 1d | awk '{printf \"%0-40s %0-20s\n\", \$1, \$2}'"
```

## Important notes and workflow
We provide the script in this repo as a convenient way of creating jobs (see more details in the section below).
* The default job is just an interactive one (with `sleep`) that you can use for development. 
  * 'Interactive' jobs are a concept from run:ai. Every user can have 1 interactive GPU. They have higher priority than other jobs and can live up to 12 hours. You can use them for debugging. If you need more than 1 GPU, you need to submit a training job.
* For a training job, use the flag `--train`, and replace the command with your training command. Using a training job allows you to use more than 1 GPU (up to 8 on one node). Moreover, a training job makes sure that the pod is killed when your code/experiment is finished in order to save money.

Of course, the script is just one suggested workflow that tries to maximize productivity and minimize costs -- you're free to find your own workflow, of course. For whichever workflow you go for, keep these things in mind:
> [!IMPORTANT]
> * Work within `/mloscratch`. This is the shared storage that is mounted to your pod.
>   * Create a directory with your GASPAR username in `/mloscratch/` folder. This will be your personal folder. Except under special circumstances, all your files should be kept inside your personal folder (e.g. `/mloscratch/nicolas` if your username is nicolas) or in your personal home folder (e.g. `/mloscratch/homes/nicolas`).**  
>   * Should you use the `csub.py` script, the first run will automatically create a working directory with your username inside `/mloscratch/homes`.
>   * Suggestion: use a GitHub repo to store your code and clone it inside your folder.
> * Moving things onto the cluster or between folders can also be done easily via [HaaS machine](#the-haas-machine). For more details on storage, see [file management](#file-management).
> * Remember that your job can get killed ***anytime*** if run:ai needs to make space for other users. Make sure to implement checkpointing and recovery into your scripts. 
> * CPU-only pods are cheap, approx 3 CHF/month, so we recommend creating a CPU-only machine that you can let run and use for code development/debugging through VSCODE.
> * When your code is ready and you want to run some experiments or you need to debug on GPU, you can create one or more new pods with GPU. Simply specify the command in the python launch script.
> * Using a training job makes sure that you kill the pod when your code/experiment is finished in order to save money.

Most importantly:
>[!CAUTION]
> Using the cluster creates costs. Please do not forget to stop your jobs when not used!


## The HaaS machine
The HaaS machine is provided by IT that allows you to move files, create folders, and copy files between `mlodata1`, `mloraw1`, and `mloscratch`, without needing to create a pod. You can access it via:
```bash
  # For basic file movement, folder creation, or
  # copying from/to mlodata1 to/from scratch:
  ssh <gaspar_username>@haas001.rcp.epfl.ch
```
The volumes are mounted inside the folders `/mnt/mlo/mlodata1`, `/mnt/mlo/mloraw1`, `/mnt/mlo/scratch`. See below for what the spaces are used for.

## File management
Reminder: the cluster uses kubernetes pods, which means that in principle, any file created inside a pod will be deleted when the pod is killed. 

To store files permanently, you need to mount network disks to your pod. In our case, this is `mloscratch` -- _all_ code and experimentation should be stored there. Except under special circumstances, all your files should be kept inside your personal folder (e.g. `/mloscratch/nicolas` if your username is nicolas) or in your personal home folder (e.g. `/mloscratch/homes/nicolas`). Scratch is high-performance storage that is meant to be accessed/mounted from pods. Even though it is called "scratch", you do not need to generally worry about losing data (it is just not replicated across multiple hard drives).

For very secure long-term storage, we have:
* `mlodata1`. 
  * This is long term storage, backed up carefully with replication (i.e. stored on multiple hard drives). This is meant to contain artifacts that you want to keep for an undetermined amount of time (e.g. things for a publication). 
* `mloraw1`
   * Not clear right now how this will be used in the future (status: 15.12.2023).
> [!CAUTION]
> You cannot mount mlodata or mloraw on pods. Use the haas machine below to access it.

### Moving data onto/between storage
Since `mloscratch` is not _replicated_, whenever you need things to become permanent, move them to `mlodata1`. This could be the case for paper artifacts, certain results or checkpoints, and so on. 

Currently, if you need to move things between `mlodata1` and `scratch`, you need to do this manually via a machine provided by IT:
```bash
  # For basic file movement, folder creation, or
  # copying from/to mlodata1 to/from scratch:
  ssh <gaspar_username>@haas001.rcp.epfl.ch
```
The volumes are mounted inside the folders `/mnt/mlo/mlodata1`, `/mnt/mlo/mloraw1`, `/mnt/mlo/scratch`. You can copy files between them using `cp` or `rsync`.

**TODO:** Update with permanent machine for MLO once we have it.

## More background on the csub script
The python script `csub.py` is a wrapper around the run:ai CLI that makes it easier to launch jobs. It is meant to be used for both interactive jobs (e.g. notebooks) and training jobs.
General usage:

```bash
python csub.py --n <job_name> -g <number of GPUs> -t <time> --cluster rcp-caas-test -i ic-registry.epfl.ch/mlo/mlo:v1 --command <cmd> [--train]
```
Check the arguments for the script to see what they do.

What this repository does on first run:
- We provide a default MLO docker image `mlo/mlo:v1` that should work for most use cases. If you use this default image, the first time you run `csub.py`, it will create a working directory with your username inside `/mloscratch/homes`. Moreover, for each symlink you find the `user.yaml` file the script will create the respective file/folder inside `mloscratch` and link it to the home folder of the pod. This is to ensure that these files and folders are persistent across different pods. 
    - **Small caveat**: csub.py expects your image to have zsh installed.
- The `entrypoint.sh` script is also installing conda in your scratch home folder. This means that you can manage your packages via conda (as you're probably used to), and the environment is shared across pods.
  - In other words: you can use have and environment (e.g. `conda activate env`) and this environment stays persistent.
- Alternatively, the bash script `utils/conda.sh` that you can find in your pod under `docker/conda.sh`, installs some packages in `utils/extra_packages.txt` in the default environment and creates an additional `torch` environment with pytorch and the packages in `utils/extra_packages.txt`. It's up to you to run this or manually customize your environment installation and configuration. 

## Alternative workflow: using the run:ai CLI and base docker images with pre-installed packages
The setup in this repository is just one way of running and managing the cluster. You can also use the run:ai CLI directly, or use the scripts in this repository as a starting point for your own setup. For more details, see the [the dedicated readme](docs/runai_cli.md).

## Creating a custom docker image
In case you want to customize it and create your own docker image, follow these steps:
- **Request registry access**: This step is needed to push your own docker images in the container. Try login here https://ic-registry.epfl.ch/ and see if you see members inside the MLO project. The groups of runai are already added, it should work already. If not, reach out to Alex or a colleague.
 - **Install Docker:** `brew install --cask docker` (or any other preferred way according to the docker website). When you execute commands via terminal and you see an error '“Cannot connect to the Docker daemon”', try running docker via GUI the first time and then the commands should work.
 - **Login registry:** `docker login ic-registry.epfl.ch` and use your GASPAR credentials. Same for the RCP cluster: `docker login registry.rcp.epfl.ch` (but we're currently not using it).
 
 
 Modify Dockerfile:** 
   - The repo contains a template Dockerfile that you can modify in case you need a custom image 
   - Push the new docker using the script `publish.sh`
   - **Remember to rename the image (`mlo/username:tag`) such that you do not overwrite the default one**

**Additional example:** Alternatively, Matteo also wrote a custom one and summarized the steps here: https://gist.github.com/mpagli/6d0667654bf8342eb4923fedf731660e
* He created an image that runs by default under his Gaspar user ID and group ID. You can find those IDs in e.g. https://people.epfl.ch/matteo.pagliardini under 'donnees administratives'.
* Upload your image to EPFL's registry
```bash
docker build . -t <your-tag>
docker login ic-registry.epfl.ch -u <your-epfl-username> -p <your-epfl-password> # use your epfl credentials
docker tag <your-tag> ic-registry.epfl.ch/mlo/<your-tag>
docker push ic-registry.epfl.ch/mlo/<your-tag>
```

## Port forwarding
If you want to access a port on your pod from your local machine, you can use port forwarding. For example, if you want to access a jupyter notebook running on your pod, you can do the following:
```bash
kubectl get pods
kubectl port-forward <pod_name> 8888:8888
```

## Distributed training
Newer versions of runai support distributed training, meaning the ability to use run accross multiple compute nodes, even beyond the several GPUs available on one node. This is currently set up on the new RCP Prod cluster (rcp-caas-prod).
A nice [documentation to get started with distributed jobs is available here](docs/multinode.md).

# File overview of this repository
```bash
├── utils
    ├── entrypoint.sh             # Sets up credentials and symlinks
    ├── conda.sh                  # Conda installation   
    └── extra_packages.txt        # Extra python packages you want to install 
├── csub.py                       # Creates a pod through run:ai; you can specify the number of GPUS, CPUS, docker image and time 
├── templates
    ├── user_template.yaml                 # Template for your user file COPY IT, DO NOT CHANGE IT
├── Dockerfile                    # Dockerfile example  
├── publish.sh                    # Script to push the docker image in the registry
├── kubeconfig.yaml               # Kubeconfig that you should store in ~/.kube/config
└── README.md                     # This file
├── docs
  ├── faq.md                        # FAQ
  └── runai_cli.md                  # Run:ai CLI guide
```


# Quick links

IC Cluster
 * Docs: https://icitdocs.epfl.ch/display/clusterdocs/IC+Cluster+Documentation
 * Dashboard: https://epfl.run.ai
 * Docker registry: https://ic-registry.epfl.ch/harbor/projects
 * Getting started guide: https://icitdocs.epfl.ch/display/clusterdocs/Getting+Started+with+RunAI

RCP Cluster
 * RCP main page: https://www.epfl.ch/research/facilities/rcp/
 * Docs: https://wiki.rcp.epfl.ch
 * Dashboard: https://rcpepfl.run.ai
 * Docker registry: https://registry.rcp.epfl.ch/
 * Getting started guide: https://wiki.rcp.epfl.ch/en/home/CaaS/Quick_Start

run:ai docs: https://docs.run.ai

If you want to read up more on the cluster, you can checkout a great in-depth guide by our colleagues at CLAIRE. They have a similar setup of compute and storage: 
* [Compute and Storage @ CLAIRE](https://prickly-lip-484.notion.site/Compute-and-Storage-CLAIRE-91b4eddcc16c4a95a5ab32a83f3a8294#)


## Other cluster-related code repositories
These repositories are mostly by previous PhDs. They used these repositories to manage shared compute infrastructure. If you want to contribute, please ask Martin to add you as an editor.
* [epfml/epfml-utils](https://github.com/epfml/epfml-utils)
  * Python package (pip install epfml-utils) for shared tooling.
* [epfml/mlocluster-setup](https://github.com/epfml/mlocluster-setup)
  * Base docker images, and setup code for semi-permanent shared machines (less recommended).
