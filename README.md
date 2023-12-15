# MLO: Getting started with the EPFL Clusters
**WARNING:** work in progress, currently updating this

This repository contains the basic steps to start running scripts and notebooks on the EPFL Clusters (both IC and RCP), with a simple setup and scripts that can make your life easier by automating a lot of things. It is based on a similar setup from our friends at TML and scripts created by Atli Kosson :)

There are two clusters available to us: the IC cluster (department only) and the RCP cluster (EPFL-wide). The IC cluster is equipped with V100 (32GB RAM) and A100 (40GB RAM) GPUs, while the RCP cluster has A100 (80GB) GPUs. You can switch between the two clusters and their respective GPUs.

<!-- The main idea is to use docker containers (kubernetes pods) to run experiments. They are non-permanent and the compute is shared with other users -->

If you have any questions about the cluster or the setup, please reach out to any of your colleagues. For specific problems, open a ticket to `support-icit@epfl.ch` (for IC cluster) or `supportrcp@epfl.ch` (for RCP cluster).

## Minimal step-by-step instructions to quickly get a notebook running

1. Ask Jennifer to add you to the group `runai-mlo` and potentially `rcp-runai-mlo` (for the RCP cluster): https://groups.epfl.ch/ 

2. Install kubectl. To make sure the version matches with the clusters (status: 15.12.2023), on macOS with Apple Silicon, run the following commands. For other systems, you will need to change the URL in the command above (check https://kubernetes.io/docs/tasks/tools/install-kubectl/). Make sure that the version matches with the version of the cluster!
```bash
    # Sketch for macOS with Apple Silicon.
    # Download a specific version (here 1.26.7 for Apple Silicon macOS)
    curl -LO "https://dl.k8s.io/release/v1.26.7/bin/darwin/arm64/kubectl"
    # Give it the right permissions and move it.
    chmod +x ./kubectl
    sudo mv ./kubectl /usr/local/bin/kubectl
    sudo chown root: /usr/local/bin/kubectl
``` 
1. Setup the kube config file: Create a file in your home directory as ``~/.kube/config`` and copy the contents from the file [`kubeconfig.yaml`](kubeconfig.yaml) in this file. Note that the file on your machine has no suffix.
2. Install the RunAI CLI:
   ```bash
      # Sketch for macOS with Apple Silicon
      # Download the CLI from the link shown in the help section.
      wget --content-disposition https://rcp-caas-test.rcp.epfl.ch/cli/darwin
      # Give it the right permissions and move it.
      chmod +x ./runai
      sudo mv ./runai /usr/local/bin/runai
      sudo chown root: /usr/local/bin/runai
   ```
3. Switch between contexts and login to both clusters:
   ```bash
      # Switch to the IC cluster
      runai config cluster ic-cluster
      # Login to the cluster
      runai login
      # Check that things worked fine
      runai list projects
      # put your default project
      runai config project mlo-$GASPAR_USERNAME
      # Repeat for the RCP cluster
      runai config cluster rcp-cluster
      runai login
      runai list projects
      runai config project mlo-$GASPAR_USERNAME
   ```
4. Run a quick test to see that you can launch jobs:
   ```bash
      # Try to submit a job that mounts our shared storage and see its content.
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
      runai delete jobs setup-test
    ```

The `runai submit` command already suffices to run jobs. Remember that you can switch between the two contexts of the IC cluster and RCP cluster (e.g. if you need a 80GB A100 GPU, use the RCP cluster) with the command `runai config cluster <cluster-name>` as shown above. See the 

However, we provide a few scripts in this repository to make your life easier to get started. 

1. Clone this repository and create a `user.yaml` file in the root folder of the repo using the template in `templates/user_template.yaml` but <ins>**do not modify the template**</ins>.

2. Fill in `user.yaml` your username, userID and groupID in `user.yaml`. You can find this information in your profile on people.epfl.ch (e.g. https://people.epfl.ch/alexander.hagele) under “Administrative data”. There's also a field for wandb API key to fill out.
   
3. Create a pod with 1 GPU which expires in 7 days and uses the image stored at [link](https://ic-registry.epfl.ch/harbor/projects/33/repositories/tml%2Ftml). You may need to install pyyaml with `pip install pyyaml` first.
```bash
python csub.py --n sandbox -g 1 -t 7d -i ic-registry.epfl.ch/mlo/mlo:v1 --command "cd /mloscratch/homes/<your username>; pip install jupyter && jupyter notebook"
```

4. Wait until the pod has a 'running' status. Check the status of the job with `runai describe job sandbox`. This can take a bit (max ~3 min or so).

5. When it is running, get the logs and the link for the notebook with 
```bash
kubectl logs sandbox-0-0
```

6. Then enable port-forwarding via
```bash 
kubectl port-forward sandbox-0-0 8888:8888
```

7. If everything worked correctly, you should be able to open the link from the logs in your browser and see the notebook! 


**Important notes:**
* The default job is just an interactive one (with `sleep`) that you can use for development. 
  * 'Interactive' jobs are a concept from run:ai. Every user can have 1 interactive GPU. They have higher priority than other jobs and can live up to 24 hours. You can use them for debugging. If you need more than 1 GPU, you need to submit a training job.
* For a training job, use the flag `--train`, and replace the command with your training command. 
* Work within `/mloscratch`. This is the shared storage that is mounted to your pod. See [File storage](#file-storage) for more details.
* Remember that your job can get killed anytime if run:ai needs to make space for other users. Make sure to implement checkpointing and recovery into your scripts. 

## Managing pods
To manage your pods you can use RunAI and the following commands: 
``` bash
runai exec pod_name -it -- zsh # - opens an interactive shell on the pod 
runai delete job pod_name # kills the job and removes it from the list of jobs
runai describe job pod_name # shows information on the status/execution of the job
runai list jobs # list all jobs and their status 
runai logs pod_name # shows the output/logs for the job
``` 

## What this repository does (first time access)

- We provide a default MLO docker image `mlo/mlo:v1` that should work for most use cases. If you use this default image, the first time you run `csub.py`, it will create a working directory with your username inside `/mloscratch/homes`. Moreover, for each symlink you find the `user.yaml` file the script will create the respective file/folder inside `mloscratch` and link it to the home folder of the pod. This is to ensure that these files and folders are persistent across different pods. 
- The `entrypoint.sh` script is also installing conda in your scratch home folder. This means that you can manage your packages via conda (as you're probably used to), and the environment is shared across pods.
- Alternatively, the bash script `utils/conda.sh` that you can find in your pod under `docker/conda.sh`, installs some packages in `utils/extra_packages.txt` in the default environment and creates an additional `torch` environment with pytorch and the packages in `utils/extra_packages.txt`. It's up to you to run this or manually customize your environment installation and configuration. 


## Suggested workflow: 
This is one suggested workflow that tries to maximize productivity and minimize costs -- you're free to find your own workflow, of course.
 - CPU-only pods are cheap, approx 3 CHF/month, so we recommend creating a CPU-only machine that you can let run for the entire duration of a project and that you use for code development/debugging through VSCODE.
 - When your code is ready and you want to run some experiments or you need to debug on GPU, you can create one or more new pods with GPU (multiple pods with 1 GPU are easier to get than one pod with multiple GPUs). Simply specify the command in the python launch script.
 -  This makes sure that you kill the pod when your code/experiment is finished in order to save money.
 -  Remember to work on mloscratch so that your code will be shared across all your pods and stored.

## Using VSCODE
To easily attach a VSCODE window to a pod we recommend the following steps: 
1. Install the [Kubernetes](https://marketplace.visualstudio.com/items?itemName=ms-kubernetes-tools.vscode-kubernetes-tools) and [Dev Containers](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers) extensions.
2. From your VSCODE window, click on Kubernetes -> ic-cluster -> Workloads -> Pods, and you should be able to see all your running pods.
3. Right-click on the pod you want to access and select `Attach Visual Studio Code`, this will start a vscode session attached to your pod.
4. The symlinks ensure that settings and extensions are stored in `mloscratch/homes/<gaspar username>` and therefore shared across pods.

&nbsp;
&nbsp;
&nbsp;
&nbsp;

---
&nbsp;
&nbsp;
&nbsp;
&nbsp;

# More background on the cluster usage, RunAI and the scripts
We go through a few more details on the cluster usage, RunAI and the scripts in this section, and provide alternative ways to use the cluster.

## File storage
In principle, any file created inside a pod will be deleted when the pod is killed. To store files permanently, you need to mount network disks to your pod. In our case, this is `scratch` -- all code and experimentation should be stored there. It is meant to be accessed by experiment pods.

To get a list of available pods, run `kubectl get pvc` (this stands for PersistentVolumeClaim). You should see
 * `runai-mlo-$GASPAR_USERNAME-mlodata1`
   * long term storage, backed up carefully with replication (i.e. stored on multiple hard drives). This is meant to contain artifacts that you want to keep for an undetermined amount of time (e.g. things for a publication). 
   * YOU SHOULD NOT MOUNT THIS FOR EXPERIMENTS.
 * `runai-mlo-$GASPAR_USERNAME-mloraw1`
   * Same idea, but not clear right now how this will be used in the future (status: 15.12.2023).
 * `runai-mlo-$GASPAR_USERNAME-scratch`
   * High-performance storage that is meant to be accessed/mounted from pods. You should contain your code, current artifacts, etc. Once you need things to become permanent, move them to `mlodata1`.

Currently, if you need to move things between `mlodata1` and `scratch`, you need to do this manually via a machine provided by IT:
```bash
  # Copy from mlodata1 to scratch in this machine
  ssh <gaspar_username>@haas001.rcp.epfl.ch
```
The volumes are mounted inside the folders `/mnt/mlo/mlodata1`, `/mnt/mlo/mloraw1`, `/mnt/mlo/scratch`. You can copy files between them using `cp` or `rsync`.

**TODO:** Update with permanent machine for MLO once we have it.

## Alternative workflow: using the RunAI CLI and base docker images with pre-installed packages
The setup in this repository is just one way of running and managing the cluster. You can also use the RunAI CLI directly, or use the scripts in this repository as a starting point for your own setup.

Thijs created a crash course with the main overview for the cluster with [these slides](https://docs.google.com/presentation/d/1n_yimybA3SbdnpMapyAMhA00lq_SN0BMHU_Ji-7mr2w/edit#slide=id.p). Additionally, he created a few base docker images with pre-installed packages:
  * mlo/basic: numpy, jupyter, ...
  * mlo/pytorch: basic + computer vision + pytorch
  * mlo/jax: basic + computer vision + jax
  * mlo/tensorflow: basic + computer vision + tensorflow
  * mlo/latex: basic + texlive

To update these, go to https://github.com/epfml/mlocluster-setup. Run `publish.sh` in `docker-images/`. 

To extend them or make your own: follow a Docker tutorial, or check [the section below](#creating-a-custom-docker-image).

**NOTE**: These base images are not compatible with the python script in this repository. The reason is that this python script is set up to use your GASPAR user id and group id as the main user in the docker image. Thijs' images use the root user and have the GASPAR user on top; you can still use the python script, but you need to modify it to use the correct user id and group id.

**Running an interactive session (for development / playing around)**

Examples:
 * RunAI CLI
```bash
runai submit \
		--name sandbox \
		--interactive \ 
		--gpu 1 \
		--image ic-registry.epfl.ch/mlo/pytorch:latest \ # or any other image
		--pvc runai-mlo-$GASPAR_USERNAME-scratch:/mloscratch \ # mount scratch
		--large-shm --host-ipc \ # just some optimization
		--environment EPFML_LDAP=$GASPAR_USERNAME \ # environment variables
		--command -- /entrypoint.sh sleep infinity # keeps the pod runnning until killed
```

Wait until the pod has status RUNNING. This can take a while (10 min or so).
```bash
runai describe job sandbox
```

You can run things (like a bash shell) on the machine like this:
```bash 
runai exec sandbox -it -- su $GASPAR_USERNAME
```

The `'su $GASPAR_USERNAME'` gives you a shell running under your user account, allowing you to access network storage. While your user can access /mloscratch, the root user cannot.

## Running a job (for experiments)
Simply replace the command in the RunAI CLI example above with your command. For example, to run a python script:
```bash
runai submit \
		--name experiment-hyperparams-1 \
		--gpu 1 \
		--image ic-registry.epfl.ch/mlo/pytorch:latest \
		--pvc runai-mlo-$GASPAR_USERNAME-scratch:/mloscratch \
		--large-shm --host-ipc \
		--environment EPFML_LDAP=$GASPAR_USERNAME \
		--environment LEARNING_RATE=0.5 \
		--environment OPTIMIZER=Adam \
		--command -- /entrypoint.sh su $GASPAR_USERNAME -c 'cd code_dir && python train.py'
```
Remember that your job can get killed anytime if run:ai needs to make space for other users. Make sure to implement checkpointing and recovery into your scripts. 


## Creating a custom docker image
In case you want to customize it and create your own docker image, follow these steps:
- **Request registry access**: This step is needed to push your own docker images in the container. Try login here https://ic-registry.epfl.ch/ and see if you see members inside the MLO project. The groups of runai are already added, it should work already. If not, reach out to Alex or a colleague.
 - **Install Docker:** `brew install --cask docker` (or any other preferred way according to the docker website). If when you execute commands via terminal you see an error '“Cannot connect to the Docker daemon”' try running docker via GUI the first time and then the commands should work.
 - **Login registry:** `docker login ic-registry.epfl.ch` and use your GASPAR credentials. Same for the RCP cluster: `docker login registry.rcp.epfl.ch` (but we're currently not using it).
 - **Modify Dockerfile:** 
   - The repo contains a template Dockerfile that you can modify in case you need a custom image 
   - Push the new docker using the script `publish.sh`, <ins>**Remember to rename the image (`mlo/username:tag`) such that you do not overwrite the default one**</ins>

Alternatively, Matteo also wrote a custom one and summarized the steps here: https://gist.github.com/mpagli/6d0667654bf8342eb4923fedf731660e
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
kubectl port-forward sandbox-0-0 8888:8888
```


## File overview of this repository
```
├── utils
    ├── entrypoint.sh             # Sets up credentials and symlinks
    ├── conda.sh                  # Conda installation   
    └── extra_packages.txt        # Extra python packages you want to install 
├── csub.py                       # Creates a pod through RunAI; you can specify the number of GPUS, CPUS, docker image and time 
├── templates
    ├── user.yaml                 # Template for your user file COPY IT, DO NOT CHANGE IT
├── Dockerfile                    # Dockerfile example  
├── publish.sh                    # Script to push the docker image in the registry
└── README.md
```

## Quick links

IC Cluster
 * Docs: https://icitdocs.epfl.ch/display/clusterdocs/IC+Cluster+Documentation
 * Dashboard: https://epfl.run.ai
 * Docker registry: https://ic-registry.epfl.ch/harbor/projects

RCP Cluster
 *  Docs: https://wiki.rcp.epfl.ch
 *  Dashboard: https://rcpepfl.run.ai
 *  Docker registry: https://registry.rcp.epfl.ch/

RunAI docs: https://docs.run.ai

### Other cluster-related code repositories
We use these repositories to manage shared compute infrastructure. If you want to contribute, please ask Martin to add you as an editor.
* [epfml/epfml-utils](https://github.com/epfml/epfml-utils)
  * Python package (pip install epfml-utils) for shared tooling.
* [epfml/mlocluster-setup](https://github.com/epfml/mlocluster-setup)
  * Base docker images, and setup code for semi-permanent shared machines (less recommended).