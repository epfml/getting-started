# Kubernetes Secrets with run:ai

This is a quick reference for using Kubernetes secrets with run:ai jobs.

> [!NOTE]
> **Using the MLO `csub.py` workflow?** You **don't need to manage secrets manually**.
>
> Instead:
> 1. Store all secrets in your local `.env` file (see `user.env.example`)
> 2. `csub.py` automatically syncs `.env` into a Kubernetes secret
> 3. Secrets are mapped into pods via `--environment KEY=SECRET:<secretName>,KEY`
>
> See:
> - [Architecture: Secrets, SSH, and Kubernetes Integration](README.md#secrets-ssh-and-kubernetes-integration)
> - [Main README: Configure Your `.env` File](../README.md#4-configure-your-env-file)
>
> This reference is for **debugging** or **crafting custom jobs by hand**.

---

## Basic Usage

### 1. Create a Kubernetes Secret

```bash
kubectl create secret generic my-secret --from-literal=key1=supersecret
```

### 2. Submit a run:ai Job with Secret

```bash
runai submit --name demo-secret \
  --image ic-registry.epfl.ch/mlo/mlo-base:uv1 \
  --pvc mlo-scratch:/mloscratch \
  --environment WANDB_API_KEY=SECRET:my-secret,key1 \
  -- /bin/bash -ic "sleep infinity"
```

**Syntax**: `--environment VAR_NAME=SECRET:<secret-name>,<key-name>`

### 3. Verify Secret Inside Container

```bash
# Connect to the pod
runai exec demo-secret -it -- bash

# Check environment variable
env | grep WANDB_API_KEY
# Output: WANDB_API_KEY=supersecret
```

---

## Multiple Secrets

You can reference multiple secrets:

```bash
runai submit --name multi-secret \
  --image ic-registry.epfl.ch/mlo/mlo-base:uv1 \
  --environment WANDB_API_KEY=SECRET:my-secret,wandb_key \
  --environment HF_TOKEN=SECRET:my-secret,hf_token \
  --environment CUSTOM_VAR=SECRET:other-secret,custom_key \
  -- /bin/bash -ic "sleep infinity"
```

---

## Managing Secrets

### List Secrets

```bash
kubectl get secrets
```

### View Secret Details

```bash
kubectl describe secret my-secret
```

### Delete a Secret

```bash
kubectl delete secret my-secret
```

### Update a Secret

Delete and recreate:

```bash
kubectl delete secret my-secret
kubectl create secret generic my-secret --from-literal=key1=newsupersecret
```

---

## Additional Resources

- [Kubernetes Secrets Documentation](https://kubernetes.io/docs/concepts/configuration/secret/)
- [run:ai Environment Variables](https://docs.run.ai/v2.15/developer/cluster-api/reference/training/#environment-variables)
- [MLO Setup: Architecture Deep Dive](README.md)