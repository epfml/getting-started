#!/bin/bash

cd $PATH_TO_ROOT_REPO

echo "START TIME: $(date)"

# MASTER_ADDR -> The IP of the master node
# MASTER_PORT -> The port that of the master node 
# WORLD_SIZE -> Number of nodes in total, NOT Numer of nodes X GPUs per node
GPUS_PER_NODE=8

LAUNCHER="torchrun \
    --nproc_per_node $GPUS_PER_NODE \
    --nnodes $WORLD_SIZE \
    --node_rank $RANK \
    --rdzv_endpoint $MASTER_ADDR:$MASTER_PORT \
    --rdzv_backend c10d \
    --max_restarts 0 \
    --role \$(hostname -s|tr -dc '0-9'): \
    --tee 3 \
    "

PYTHON_FILE=utils/distributed_pytorch/benchmark/all_reduce_bench.py

export CMD="$LAUNCHER $PYTHON_FILE $PYTHON_ARGS"
bash -c "$CMD"

echo "END TIME: $(date)"
