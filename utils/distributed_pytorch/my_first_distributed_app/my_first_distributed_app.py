import os

from numba import jit
from numpy import pi
from numpy.testing import assert_almost_equal
import torch
import torch.distributed as dist

TRIALS = 5

a = 0           # Lower bound
b = 1           # Upper bound
n = 1000000000   # Number of trapezoids

@jit(nopython=True) # Set "nopython" mode for best performance, equivalent to @njit
def compute_partial_pi(local_a, local_b, local_n, h):
    estimate = (local_a**2 + local_b**2) / 2.0

    for i in range(local_n):
        x = local_a + i * h
        estimate += 4.0 / (1.0 + x*x)

    return estimate * h

def compute_pi(local_a, local_b, local_n, h):
    estimate = compute_partial_pi(local_a, local_b, local_n, h)
    estimate = torch.tensor([estimate])
    dist.all_reduce(estimate, op=dist.ReduceOp.SUM)
    return estimate

def timed_compute_pi(local_a, local_b, local_n, h, start_event, end_event):
    dist.barrier()
    start_event.record()
    # Compute partial result of pi
    pi_estimate = compute_pi(local_a, local_b, local_n, h)
    end_event.record()
    
    torch.cuda.synchronize()
    assert_almost_equal(pi_estimate.item(), pi, decimal=5)
    duration = start_event.elapsed_time(end_event) / 1000
    duration = torch.tensor([duration])

    # Compute mean across all ranks
    dist.reduce(duration, dst=0, op=dist.ReduceOp.SUM)

    return duration


def run():
    rank, world_size = int(os.environ["RANK"]), int(os.environ["WORLD_SIZE"]) # Variables set up by torchrun
    
    # Note: h and local_n are the same for all processes
    h = (b-a)/n          # Length of each trapezoid
    local_n = int(n/world_size)  # Number of trapezoids per process 

    # Length of each process interval of integration = local_n*h.
    local_a = a + rank * local_n * h
    local_b = local_a + local_n * h

    start_event = torch.cuda.Event(enable_timing=True)
    end_event = torch.cuda.Event(enable_timing=True)

    # Do a few warm up iterations
    for _ in range(2):
        timed_compute_pi(local_a, local_b, local_n, h, start_event, end_event)

    # Real benchmark
    times = []
    for _ in range(TRIALS):
        times += timed_compute_pi(local_a, local_b, local_n, h, start_event, end_event)

    avg_times = torch.mean(torch.stack(times))

    if rank == 0:
        print(f"Total number of processes: {world_size}")
        print(f"AVG Time: {avg_times}\n")


if __name__ == "__main__":
    # Init PyTorch process group with "gloo" backend for CPU comms (NOT NVIDIA NCCL)
    dist.init_process_group(backend="gloo")
    run()