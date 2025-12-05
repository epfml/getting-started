> [!NOTE]  
> When you are using the MLO `csub.py` workflow, you **do not** need to manage secrets manually like this in most cases. Instead:
> - you keep all secret values in your local `.env` file (see the `user.env.example` template),
> - `csub.py` renders that file into a Kubernetes secret for your namespace (see section **“Local configuration & secrets”** and **“Secrets, SSH, and kube integration”** in [`README.md`](README.md)),
> - and maps selected keys into the pod via `--environment KEY=SECRET:<secretName>,KEY`.  
> This file is only meant as a minimal refresher on the underlying Kubernetes/run:ai mechanism if you ever need to debug or craft custom jobs by hand.

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