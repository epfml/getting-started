# Alternative workflow: using the run:ai CLI and base docker images with pre-installed packages
The setup in this repository is just one way of running and managing the cluster. You can also use the run:ai CLI directly, or use the scripts in this repository as a starting point for your own setup.

Thijs created a crash course with the main overview for the cluster with [these slides](https://docs.google.com/presentation/d/1n_yimybA3SbdnpMapyAMhA00lq_SN0BMHU_Ji-7mr2w/edit#slide=id.p). Additionally, he created a few base docker images with pre-installed packages:
  * mlo/basic: numpy, jupyter, ...
  * mlo/pytorch: basic + computer vision + pytorch
  * mlo/jax: basic + computer vision + jax
  * mlo/tensorflow: basic + computer vision + tensorflow
  * mlo/latex: basic + texlive

To update these, go to https://github.com/epfml/mlocluster-setup. Run `publish.sh` in `docker-images/`. To extend them or make your own: follow a Docker tutorial, or check [the section below](#creating-a-custom-docker-image).


The following description is taken from Thijs' slides and notes:

## Running an interactive session (for development / playing around)

Examples:
 * run:ai CLI
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

> [!NOTE] These base images are not compatible with the python script in this repository. The reason is that this python script is set up to use your GASPAR user id and group id as the main user in the docker image. Thijs' images use the root user and have the GASPAR user on top; you can still use the python script, but you need to modify it to use the correct user id and group id.

## Running a job (for experiments)
[[Minimal cifar example including logging to wandb]](https://github.com/epfml/cifar/tree/wandb)

Simply replace the command in the run:ai CLI example above with your command. For example, to run a python script:
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