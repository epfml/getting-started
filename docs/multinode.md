# Distributed PyTorch with RunAI 
> [!NOTE]  
> Multi-Node scheduling needs to be enabled on the cluster and you should be using a RunAI CLI which 
> supports multi-node jobs. 

> [!CAUTION]  
> This doc explains an advanced usage of RunAI. 

Jobs can be submitted either through RunAI as documented in RunAI's website (https://docs.run.ai/v2.13/Researcher/cli-reference/runai-submit-dist-pytorch/).

To execute jobs in RCP, we will use the RunAI CLI, more specifically the `submit-dist pytorch` function, which will be responsible for launching the specified command on each pod. There are two ways to execute distributed applications:
1. Interactive sessions. To force interactive sessions, we will have to launch the command `sleep infinity` on each pod. This way, we can connect to each pod, but we will have to manually execute the jobs on each one. This is useful for short sessions for debugging applications and checking that everything works correctly before launching a longer job.
> [!TIP]
> Keep in mind that as soon as you disconnect from the pod, you will lose the current job you are executing.
2. Batched execution. In this mode, we will specify to the `submit-dist` function to execute a script, and it will defer execution until the requested resources are available. This is the recommended way to launch longer jobs such as model training.

To configure the number of nodes and GPUs, we will use the following flags of the `submit-dist` function:
1. `--workers`: The total number of nodes will be `n_workers` + 1, as RunAI adds a master node by default.
2. `--gpu`: The number of GPUs per node. Unless debugging applications, set this value as the number of GPUs per node. Otherwise, it would be possible to orchestrate 2 pods on the same node, which would not make sense.

RunAI handles scheduling the pods and also creates the necessary communication (rendezvous) backend (most likely c10d) between them. The following environment variables are set:

* `WORLD_SIZE`: Number of pods (number of GPUs in each pod does not matter.)
* `RANK`: Rank of the pod (number of GPUs in each pod does not matter.)
* `MASTER_ADDR`: IP Address of the master node.
* `MASTER_PORT`: Port on which master node is listening

## Using RDMA for efficient inter-node communication

Additional setup is necessary for efficient communication, in particular, using RDMA. We have already specified the following flags when running our pods to ensure RDMA support:
```--annotation k8s.v1.cni.cncf.io/networks=kube-system/roce --extended-resource rdma/rdma=1```.

However, the communication backend requires additional configuration to use RDMA. In particular, the following steps are needed when using NCCL. The necessary steps may vary for different OS distributions or versions as well as when alternative drivers for Inifiniband/RDMA are installed.

1. Determine the device name: Usually there should be a single directory in /sys/class/infiniband. The name of the folder, is the name of the registered RDMA device. In my settings, the infiniband device was registered as mlx5_bond_0.

2. Determine the correct GID index for RDMA:  

    2.1. In RPC, both IPv4 and IPv6 are available in the pod. Therefore there are two indices for each connection type, one for IPv4 and one for IPv6. For finding the one that uses IPv4, we can use the following command:

    ```bash
    grep '0000:0000:0000:0000:0000:ffff' /sys/class/infiniband/mlx5_bond_0/ports/1/gids/*
    ```

    2.2. It is also possible to either use RoCE v2 or RoCE v1. For example to find the indices corresponding to RoCE v2 we can use:

    ```bash
    grep 'RoCE v2' /sys/class/infiniband/mlx5_bond_0/ports/1/gid_attrs/types/* 2>/dev/null
    ```

    2.3. The port that appears in both of the above commands is the one we want. For the pods I was running this was always port 9. The following one-liner performs all the above operations:

    ```bash
    grep 'RoCE v2' $(grep '0000:0000:0000:0000:0000:ffff' /sys/class/infiniband/mlx5_bond_0/ports/1/gids/* | cut -d ':' -f 1 | sed 's/gids/gid_attrs\/types/') |  sed -e 's/.*\/\([0-9]*\):.*/\1/'
    ```


3. Once we know the device name as well as the correct GID index, we can configure NCCL by settings the environment variable `NCCL_IB_GID_INDEX` to the desired GID index. Furthermore, we should set `NCCL_IB_HCA` to a prefix to ensure NCCL uses the right device. For example, either `mlx5_bond_0` or a prefix such as `mlx5` should work. 

    ```bash
    export NCCL_IB_GID_INDEX=$(grep 'RoCE v2' $(grep '0000:0000:0000:0000:0000:ffff' /sys/class/infiniband/mlx5_bond_0/ports/1/gids/* | cut -d ':' -f 1 | sed 's/gids/gid_attrs\/types/') |  sed -e 's/.*\/\([0-9]*\):.*/\1/')
    export NCCL_IB_HCA=mlx5
    export NCCL_SOCKET_NTHREADS=4 
    export NCCL_NSOCKS_PERTHREAD=8
    ```

4. You should run `torchrun` with the above environment variables set. This should usually be enough to get NCCL to correctly use RDMA. To verify this, you can use tools such as ifstats. These tools monitor network traffic that goes through CPU. When using RDMA, no such traffic should be visible (assuming you are not using the network interface for other things).

## Running your first distributed application
In [`/utils/distributed_pytorch/my_first_distributed_app/`](/utils/distributed_pytorch/my_first_distributed_app/), you will find everything necessary to run a distributed application in PyTorch. This application simply computes number PI using the trapezoid rule by distributing the integral among the total number of processes.

To launch our first application, we will use the batched execution format from the `submit-dist pytorch` function. We will launch the job as follows to distribute the work across two nodes ([`/utils/distributed_pytorch/my_first_distributed_app/RUNAI_run_app.sh`](/utils/distributed_pytorch/my_first_distributed_app/RUNAI_run_app.sh)):

```
./runai-2.13.49 submit-dist pytorch \
  --name my_first_distributed_app \
  --image registry.rcp.epfl.ch/meditron-ddx/basic:latest-solergib \
  --workers 1 \
  --gpu 0 \
  --pvc mlo-scratch:/mloscratch \
  --annotation k8s.v1.cni.cncf.io/networks=kube-system/roce \
  --extended-resource rdma/rdma=1 \
  -e PATH_TO_ROOT_REPO=/mloscratch/homes/solergib/getting-started \
  --large-shm \
  -- bash -c '"source \${PATH_TO_ROOT_REPO}/utils/distributed_pytorch/my_first_distributed_app/RCP_run_app.sh &> \${PATH_TO_ROOT_REPO}/utils/distributed_pytorch/my_first_distributed_app/reports/Output_\${JOB_UUID}.txt"'
```

Note the following:
1. We aren't requesting any GPU, as the application doesn't needs any. 
2. We include the annotations to use RDMA.
3. The environment variable `PATH_TO_ROOT_REPO` contains the path to this repository within the PVC `mlo-scratch` mounted at `/mlo-scratch`.
4. We launch the job with `bash -c "..."` to:
   1. Allow for the delayed interpolation of environment variables to work (e.g., `PATH_TO_ROOT_REPO`).
   2. Store the output of the job in a file. It can also be checked with `runai logs --name`, but after some time, it will be inaccessible.
> [!WARNING]  
> Don't forget the double double quotes in `bash -c` (`'"..."'`).

The script to be executed on each node is as follows ([`/utils/distributed_pytorch/my_first_distributed_app/RCP_run_app.sh`](/utils/distributed_pytorch/my_first_distributed_app/RCP_run_app.sh)):

```
#!/bin/bash

echo "START TIME: $(date)"

export NCCL_IB_GID_INDEX=$(grep 'RoCE v2' $(grep '0000:0000:0000:0000:0000:ffff' /sys/class/infiniband/mlx5_bond_0/ports/1/gids/* | cut -d ':' -f 1 | sed 's/gids/gid_attrs\/types/') |  sed -e 's/.*\/\([0-9]*\):.*/\1/')
export NCCL_IB_HCA=mlx5
export NCCL_SOCKET_NTHREADS=4 
export NCCL_NSOCKS_PERTHREAD=8

# MASTER_ADDR -> The IP of the master node
# MASTER_PORT -> The port that of the master node 
# WORLD_SIZE -> Number of nodes in total, NOT Numer of nodes X GPUs per node
PROCESSES_PER_NODE=20

LAUNCHER="torchrun \
    --nproc_per_node $PROCESSES_PER_NODE \
    --nnodes $WORLD_SIZE \
    --node_rank $RANK \
    --rdzv_endpoint $MASTER_ADDR:$MASTER_PORT \
    --rdzv_backend c10d \
    --max_restarts 0 \
    --role \$(hostname -s|tr -dc '0-9'): \
    --tee 3 \
    "

PYTHON_FILE=/mloscratch/homes/solergib/getting-started/utils/distributed_pytorch/my_first_distributed_app/my_first_distributed_app.py

export CMD="$LAUNCHER $PYTHON_FILE"
bash -c "$CMD"

echo "END TIME: $(date)"
```

Note the following:
1. At the beginning, we set both the network and environment configurations (Activate conda environment, set environment variables, etc.).
2. To launch the distributed applications, we will use `torchrun`. In short, `torchrun` spawns `--nproc-per-node` processes on each node by executing the specified script. Additionally, it also handles communications between nodes before launching the script. For this, it is necessary to specify `MASTER_ADDR` and `MASTER_PORT`, variables that are automatically defined by RunAI when using `submit-dist pytorch`. `--nodes` will be the number of pods launched (`WORLD_SIZE`), and we will use `--node-rank` to specify the rank of each node; otherwise, `torchrun` will assign a value to each `--node-rank`. In this example, for which we will not use GPUs, we will launch 20 processes on each of the two nodes, dividing the work among a total of 40 processes.
> [!WARNING]  
> Do not confuse the variables `WORLD_SIZE` and `RANK` produced by RunAI with the `submit-dist function` with the same variables generated by `torchrun` when launching the scripts. In the case of RunAI, they are configured based on the **number of pods**, while in `torchrun`, they are configured based on the **number of spawned processes**, which is defined by `--nnodes` x `--nproc-per-node`.

## Inter-Node communication benchmark
We conducted a benchmark to determine the bandwidth between nodes (In Gbps). As can be seen, the benefit of RDMA is significant, so it is advisable to ensure that it is enabled.

<table class="tg">
<thead>
  <tr>
    <th class="tg-lboi"></th>
    <th class="tg-9wq8" colspan="2">RDMA</th>
    <th class="tg-9wq8" colspan="2">NO RDMA</th>
  </tr>
</thead>
<tbody>
  <tr>
    <td class="tg-9wq8">GPUs</td>
    <td class="tg-9wq8">busbw</td>
    <td class="tg-9wq8">algbw</td>
    <td class="tg-9wq8">busbw</td>
    <td class="tg-9wq8">algbw</td>
  </tr>
  <tr>
    <td class="tg-9wq8">2</td>
    <td class="tg-9wq8">1687.1</td>
    <td class="tg-9wq8">1687.1</td>
    <td class="tg-9wq8">-</td>
    <td class="tg-9wq8">-</td>
  </tr>
  <tr>
    <td class="tg-9wq8">4</td>
    <td class="tg-9wq8">1621.5</td>
    <td class="tg-9wq8">1081.0</td>
    <td class="tg-9wq8">-</td>
    <td class="tg-9wq8">-</td>
  </tr>
  <tr>
    <td class="tg-9wq8">8</td>
    <td class="tg-9wq8">1662.4</td>
    <td class="tg-9wq8">949.9</td>
    <td class="tg-9wq8">-</td>
    <td class="tg-9wq8">-</td>
  </tr>
  <tr>
    <td class="tg-9wq8">16</td>
    <td class="tg-9wq8">122.3</td>
    <td class="tg-9wq8">65.2</td>
    <td class="tg-9wq8">29.1</td>
    <td class="tg-9wq8">15.5</td>
  </tr>
</tbody>
</table>

Pay attention to the `busbw` result (not `algbw`) as explained [here](https://github.com/NVIDIA/nccl-tests/blob/master/doc/PERFORMANCE.md#bandwidth). For intra-node communications (GPUs on the same node), RDMA is disabled, so the data shown reflects the performance achieved with NVLINK. Keep in mind that to shard big models using DeepSpeed/FSDP, it is recommended to have at least 400 Gbps, so it is advisable to restrict training to a single node whenever possible.

Both the benchmark and the script to launch the job in RCP are located in [`/utils/distributed_pytorch/benchmark/`](/utils/distributed_pytorch/benchmark/). This benchmark is a reduced version of `nccl-test` in Python developed by [Stas Bekman](https://github.com/stas00/ml-engineering/blob/master/network/benchmarks/all_reduce_bench.py).