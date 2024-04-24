./runai-2.13.49 submit-dist pytorch \
  --name all-reduce-bench \
  --image registry.rcp.epfl.ch/meditron-ddx/basic:latest-solergib \
  --workers 3 \
  --gpu 8 \
  --pvc mlo-scratch:/mloscratch \
  -e PATH_TO_ROOT_REPO=/mloscratch/homes/solergib/getting-started \
  --large-shm \
  -- bash -c '"source \${PATH_TO_ROOT_REPO}/utils/distributed_pytorch/benchmark/RCP_run_benchmark_no_RDMA.sh &> \${PATH_TO_ROOT_REPO}/utils/distributed_pytorch/benchmark/reports/Output_\${JOB_UUID}.txt"'