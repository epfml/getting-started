```bash
# Create a generic Kubernetes secret
kubectl create secret generic my-secret --from-literal=key1=supersecret

# Submit a RunAI job
runai submit --name demo-secret \
  # ... other submission flags ... \
  --environment WANDB_API_KEY=SECRET:my-secret,key1 \
  --command \
  -- /bin/bash -ic "command-line-to-run"
```

# Check secret inside the job container
```bash
runai bash demo-secret
root@demo-secret-0-0:/# env | grep WANDB_API_KEY
WANDB_API_KEY=supersecret
```