# Multi-Node Training with RunAI 
> [!NOTE]  
> Multi-Node scheduling needs to be enabled on the cluster and you should be using a RunAI CLI which 
> supports multi-node jobs (>2.13). As of April 30th 2025 this setup works on the RCP cluster with runai 2.18.94.

> [!CAUTION]  
> This doc explains an advanced usage of RunAI. 

The RCP wiki includes some documentation on running distributed workloads [here](https://wiki.rcp.epfl.ch/en/home/CaaS/FAQ/how-to-run-distributed-jobs), with [introductory slides](https://wiki.rcp.epfl.ch/public/files/distributed_training_epfl_session_june_2024.pdf) and an [example repository](https://gitlab.epfl.ch/rcp/caas/caas-usage-example/pytorch-distributed).

Jobs can be submitted via the updated `csub.py` script (as of Dec 16th 2025), or directly through RunAI as documented in RunAI's website (https://docs.run.ai/latest/Researcher/cli-reference/runai-submit-dist-pytorch/).

## Starting distributed workloads

The following commands launch 2 pods, each with 4 GPUs. Note that the number of pods is one more than the number of workers as the master node is not counted as a worker.

```bash
# directly with runai
runai submit-dist pytorch \
    --name distributed-job \
    --workers=1 -g 4 -i ic-registry.epfl.ch/mlo/mlo:v1 \
    --annotation k8s.v1.cni.cncf.io/networks=kube-system/roce \
    --extended-resource rdma/rdma=1 \
    -- bash -c "sleep infinity" 

# with csub.py, which takes care of the --annotation and --extended-resource flags
python csub.py -n distributed-job --distributed --workers=1 -g 4
```
Note that it is not possible to control how these pods are scheduled so these two pods can be either on the same node or on different nodes. For best performance, local GPUs should be maximized, which would mean asking for pods of 8 GPUs each (taking a full node). You can open a bash on a specific pod with `runai bash job_name --pod pod_name`. You can list pods with `kubectl get pods`.

RunAI handles scheduling the pods and also creates the necessary communication (rendezvous) backend (most likely c10d) between them. The following environment variables are set:

* `PET_NNODES`: PyTorch Elastic Number of Nodes, the number of pods (number of GPUs in each pod does not matter).
* `RUNAI_NUM_OF_GPUS`: The number of GPUs per node, set by RunAI.
* `WORLD_SIZE`: Total number of GPUs across nodes: i.e., PET_NNODES * RUNAI_NUM_OF_GPUS.
* `RANK`: Rank of the pod (number of GPUs in each pod does not matter).
* `LOCAL_RANK`: Rank of the GPU within a pod.
* `MASTER_ADDR`: IP Address of the master node.
* `MASTER_PORT`: Port on which master node is listening.

You can find more in [torchrun's documentation](https://pytorch.org/docs/stable/elastic/run.html#environment-variables)
For running a training job, torchrun accepts the above variables as arguments and automatically schedules the job. For example the following command can be used to schedule a training job on the 3 pods we launched before. 

> [!NOTE]
> The command needs to be run on each of the pods separately.

```bash
torchrun \
    --nproc-per-node gpu \ # All these parameters can be omitted and automatically inferred
    --nnodes ${PET_NNODES} \
    --node_rank ${RANK} \
    --master_addr ${MASTER_ADDR} \
    --master_port ${MASTER_PORT} \
    main.py # you can use the example script below
```

torchrun automatically launches a separate process for each GPU and assigns the correct global and local ranks. As such, for basic usage (e.g. FSDP), no changes to python code is necessary.

## Using RDMA for efficient inter-node communication

#### TL;DR:
Set the following environment variables before starting training:
```
export NCCL_IB_GID_INDEX=$(grep 'RoCE v2' $(grep '0000:0000:0000:0000:0000:ffff' /sys/class/infiniband/mlx5_bond_0/ports/1/gids/* | cut -d ':' -f 1 | sed 's/gids/gid_attrs\/types/') |  sed -e 's/.*\/\([0-9]*\):.*/\1/')
export NCCL_IB_HCA=mlx5_bond_
export NCCL_SOCKET_NTHREADS=4
export NCCL_NSOCKS_PERTHREAD=$RUNAI_NUM_OF_GPUS
````

---

While the previous section should get a job running, additional setup is necessary for efficient communication, in particular, using RDMA. We have already specified the following flags when running our pods to ensure RDMA support (this is done automatically with `cusb.py`):
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

    2.3. The port that appears in both of the above commands is the one we want. For the pods I was running this was always port 7 or 9. The following one-liner performs all the above operations:

    ```bash
    grep 'RoCE v2' $(grep '0000:0000:0000:0000:0000:ffff' /sys/class/infiniband/mlx5_bond_0/ports/1/gids/* | cut -d ':' -f 1 | sed 's/gids/gid_attrs\/types/') |  sed -e 's/.*\/\([0-9]*\):.*/\1/'
    ```


3. Once we know the device name as well as the correct GID index, we can configure NCCL by settings the environment variable `NCCL_IB_GID_INDEX` to the desired GID index. Furthermore, we should set `NCCL_IB_HCA` to a prefix to ensure NCCL uses the right device. For example, either `mlx5_bond_0` or a prefix such as `mlx5` should work. 

    ```bash
    sudo apt update # on RCP your password is your username
    sudo apt install libibverbs-dev librdmacm-dev libmlx5-1 # Install RDMA libraries required by NCCL if needed
    export NCCL_IB_GID_INDEX=$(grep 'RoCE v2' $(grep '0000:0000:0000:0000:0000:ffff' /sys/class/infiniband/mlx5_bond_0/ports/1/gids/* | cut -d ':' -f 1 | sed 's/gids/gid_attrs\/types/') |  sed -e 's/.*\/\([0-9]*\):.*/\1/')
    export NCCL_IB_HCA=mlx5_bond_
    export NCCL_SOCKET_NTHREADS=4
    export NCCL_NSOCKS_PERTHREAD=$RUNAI_NUM_OF_GPUS
    ```

4. You should run torchrun with the above environment variables set. This should usually be enough to get NCCL to correctly use RDMA. To verify this, you can use tools such as `ifstat`. These tools monitor network traffic that goes through CPU. When using RDMA, no such traffic should be visible (assuming you are not using the network interface for other things). By exporting `NCCL_DEBUG=INFO`, executing the torchrun command should show `NCCL INFO NET/IB : Using [0]mlx5_bond_0:1/RoCE [RO]` (RoCE is indeed being used) and `NCCL INFO Channel 00/0 : 0[0] -> 2[0] [send] via NET/IB/0(1)/GDRDMA` with possibly different ranks for `0[0] -> 2[0]`. GDRDMA stands for GPUDirect RDMA — direct transfers between GPUs over RDMA without staging through host memory. If RDMA is **not** being used you may see `NCCL INFO NET/Socket : Using [0]net1:172.18.128.3<0> [1]**eth0**:172.16.46.52<0>` and `NCCL INFO Using network Socket`.

## Working example

For convenience, you can create a script, which I'll call `multi_node_training.sh` that sets all the environment variables before starting the actual training:
```bash
#!/usr/bin/env bash

echo "START TIME: $(date)"

export NCCL_IB_GID_INDEX=$(grep 'RoCE v2' $(grep '0000:0000:0000:0000:0000:ffff' /sys/class/infiniband/mlx5_bond_0/ports/1/gids/* | cut -d ':' -f 1 | sed 's/gids/gid_attrs\/types/') |  sed -e 's/.*\/\([0-9]*\):.*/\1/')
export NCCL_IB_HCA=mlx5_bond_
export NCCL_SOCKET_NTHREADS=4
export NCCL_NSOCKS_PERTHREAD=$RUNAI_NUM_OF_GPUS
export NCCL_DEBUG=INFO

export PROCESSES_PER_NODE=$RUNAI_NUM_OF_GPUS

# Uncomment if using DeepSpeed
# export ACCELERATE_DEEPSPEED_ZERO3_INIT=true

# Uncomment for fast huggingface hub download and upload
# export HF_HUB_ENABLE_HF_TRANSFER=1

# Display the role of the current node
echo "Role: $(hostname -s | tr -dc '0-9')"
echo "Num nodes: $PET_NNODES"
echo "Num GPU: $(($PROCESSES_PER_NODE * $PET_NNODES))"
echo "rdzv endpoint: $MASTER_ADDR:$MASTER_PORT"

# torch.distributed.run is equivalent to torchrun
python -m torch.distributed.run \
  --nnodes=$PET_NNODES \
  --rdzv_endpoint=$MASTER_ADDR:$MASTER_PORT \
  --rdzv_backend=c10d \
  --nproc-per-node=$PROCESSES_PER_NODE \
  --role $(hostname -s|tr -dc '0-9'): \
  --max-restarts=0 \
  --tee 1 \
  train.py 2>&1 | tee rank_${RANK}.log
EXIT_CODE=$?

echo "END TIME: $(date)"

# Finally exit with the same error code as the torchrun command
exit $EXIT_CODE
```
Don't forget to `chmod +x multi_node_training.sh`.

Here's an example PyTorch script that you can use for the `train.py` called from `multi_node_training.sh`:

```python
import os
import torch
import torch.distributed as dist
import torch.nn as nn
import torch.optim as optim
from torch.nn.parallel import DistributedDataParallel as DDP
from torchvision import models
from time import sleep

def setup():
    dist.init_process_group("nccl", rank=int(os.environ['RANK']), world_size=int(os.environ['WORLD_SIZE']))
    print(f"Process group initialized for rank {os.environ['RANK']}")

def cleanup():
    dist.destroy_process_group()

def main():
    setup()
    local_rank = int(os.environ['LOCAL_RANK'])

    try:
        # Create a simple model
        model = models.resnet18().cuda(local_rank)
        model = DDP(model, device_ids=[local_rank])

        # Create a random input tensor and move it to the current device
        for _ in range(10):
            input_tensor = torch.randn(20, 3, 224, 224).cuda(local_rank)

            # Define a simple loss function and optimizer
            loss_fn = nn.CrossEntropyLoss()
            optimizer = optim.Adam(model.parameters(), lr=0.001)

            # Forward pass
            output = model(input_tensor)
            target = torch.randint(0, 1000, (20,)).cuda(local_rank)
            
            # Compute loss
            loss = loss_fn(output, target)

            # Backward pass and optimization step
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

            print(f"Local rank {local_rank}, Loss: {loss.item()}")
            sleep(1)
    finally:
        cleanup()

if __name__ == "__main__":
    main()
```

Finally, you can start the job with:
```
python csub.py -n distributed-job --distributed --workers 1 -g 4 --large_shm -c "./mloscratch/homes/<path to script>/multi_node_training.sh 2>&1 | tee out.log"
```