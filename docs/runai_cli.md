# Alternative Workflow: Using run:ai CLI Directly

This guide covers using the **raw run:ai CLI** without the `csub.py` wrapper.

> [!NOTE]
> **Recommended for most users**: The `csub.py` + `.env` workflow described in the [main README](../README.md).
>
> This guide is for **advanced users** who:
> - Prefer to drive everything through the raw run:ai CLI
> - Want to use Thijs' base images directly without `csub.py`
> - Need more granular control over job submission

---

## Background

### Base Docker Images

Thijs created several base images with common packages pre-installed:

| Image | Includes |
|-------|----------|
| `mlo/basic` | numpy, jupyter, common utilities |
| `mlo/pytorch` | basic + computer vision + PyTorch |
| `mlo/jax` | basic + computer vision + JAX |
| `mlo/tensorflow` | basic + computer vision + TensorFlow |
| `mlo/latex` | basic + texlive (for LaTeX documents) |

**Registry**: `ic-registry.epfl.ch/mlo/<image>:latest`

### Updating Base Images

To update these images:
1. Clone: https://github.com/epfml/mlocluster-setup
2. Navigate to `docker-images/`
3. Run `./publish.sh`

### Creating Custom Images

- **Quick start**: Follow a Docker tutorial
- **MLO integration**: See [Architecture: Images & Publishing](README.md#images-and-publishing)

### Additional Resources

- [Thijs' cluster overview slides](https://docs.google.com/presentation/d/1n_yimybA3SbdnpMapyAMhA00lq_SN0BMHU_Ji-7mr2w/edit#slide=id.p)

---

## Running an Interactive Session

Interactive sessions are ideal for development, debugging, and exploratory work.

### Submit Interactive Job

```bash
runai submit \
  --name sandbox \
  --interactive \
  --gpu 1 \
  --image ic-registry.epfl.ch/mlo/pytorch:latest \
  --pvc runai-mlo-$GASPAR_USERNAME-scratch:/mloscratch \
  --large-shm --host-ipc \
  --environment EPFML_LDAP=$GASPAR_USERNAME \
  --command -- /entrypoint.sh sleep infinity
```

**Flag explanations**:
- `--interactive`: Marks as interactive job (1 GPU limit, higher priority, 12h max)
- `--gpu 1`: Request 1 GPU
- `--image`: Docker image to use
- `--pvc`: Mount scratch storage
- `--large-shm --host-ipc`: Optimization flags for shared memory
- `--environment`: Pass environment variables
- `--command`: Keep pod running indefinitely

### Wait for Pod to Start

Monitor status (can take up to 10 minutes):

```bash
runai describe job sandbox
```

Wait until status shows `RUNNING`.

### Connect to Your Pod

```bash
runai exec sandbox -it -- su $GASPAR_USERNAME
```

**Why `su $GASPAR_USERNAME`?**
- Gives you a shell under your user account
- Enables access to network storage (`/mloscratch`)
- Root user cannot access `/mloscratch` due to NFS permissions

> [!IMPORTANT]
> **Compatibility note**: These base images are **not plug-and-play compatible** with the `csub.py` workflow.
>
> - **csub.py workflow**: Uses `NB_UID`, `NB_GID` environment variables and `docker/entrypoint.sh` to mirror your Gaspar identity
> - **Thijs' images**: Use a different layout (root + separate user)
>
> You can:
> - Use these images with raw CLI (as shown here)
> - Adapt them to the new entrypoint/UID model for `csub.py` compatibility

---

## Running a Training Job

Training jobs are for actual experiments and long-running workloads.

### Submit Training Job

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
  --command -- /entrypoint.sh su $GASPAR_USERNAME -c 'cd /mloscratch/homes/$GASPAR_USERNAME/code && python train.py'
```

**Key differences from interactive jobs**:
- **No `--interactive` flag**: Runs as training workload
- **Custom command**: Executes your training script
- **Environment variables**: Pass hyperparameters as env vars
- **Multiple GPUs**: Can request more than 1 GPU (up to 8)

### Example: CIFAR Training

See this [minimal CIFAR example with W&B logging](https://github.com/epfml/cifar/tree/wandb).

### Important Reminders

> [!IMPORTANT]
> **Job preemption**: Your job can be killed anytime if run:ai needs space for other users.
>
> **Always implement**:
> - Checkpointing (save model state regularly)
> - Recovery logic (resume from checkpoint)
>
> See [Managing Workflows](managing_workflows.md#important-notes-and-workflow) for more best practices.

---

## Advantages and Disadvantages

### Raw CLI Approach

**Advantages**:
- ✅ Full control over submission parameters
- ✅ Can use any Docker image
- ✅ No dependency on `csub.py` script
- ✅ Easier to script custom workflows

**Disadvantages**:
- ❌ No automatic secret management (manual `kubectl create secret`)
- ❌ More verbose commands
- ❌ Manual UID/GID configuration needed
- ❌ Must manually sync SSH keys and tokens

### csub.py Workflow

**Advantages**:
- ✅ Automatic secret management from `.env`
- ✅ Consistent UID/GID mapping
- ✅ Auto-sync of SSH keys and tokens
- ✅ Shorter, cleaner commands
- ✅ Less error-prone

**Disadvantages**:
- ❌ Less flexibility for custom setups
- ❌ Requires compatible Docker image with entrypoint

---

## Common Patterns

### CPU-Only Development Pod

```bash
runai submit \
  --name dev-cpu \
  --interactive \
  --cpu 4 \
  --memory 16G \
  --image ic-registry.epfl.ch/mlo/pytorch:latest \
  --pvc runai-mlo-$GASPAR_USERNAME-scratch:/mloscratch \
  --environment EPFML_LDAP=$GASPAR_USERNAME \
  --command -- /entrypoint.sh sleep infinity
```

Cost: ~3 CHF/month

### Multi-GPU Training

```bash
runai submit \
  --name multi-gpu-experiment \
  --gpu 4 \
  --image ic-registry.epfl.ch/mlo/pytorch:latest \
  --pvc runai-mlo-$GASPAR_USERNAME-scratch:/mloscratch \
  --large-shm --host-ipc \
  --environment EPFML_LDAP=$GASPAR_USERNAME \
  --command -- /entrypoint.sh su $GASPAR_USERNAME -c 'cd code && python train.py'
```

### With Port Forwarding (Jupyter)

```bash
runai submit \
  --name jupyter \
  --interactive \
  --gpu 1 \
  --image ic-registry.epfl.ch/mlo/pytorch:latest \
  --pvc runai-mlo-$GASPAR_USERNAME-scratch:/mloscratch \
  --port 8888:8888 \
  --environment EPFML_LDAP=$GASPAR_USERNAME \
  --command -- /entrypoint.sh su $GASPAR_USERNAME -c 'jupyter notebook --ip=0.0.0.0 --port=8888 --no-browser'
```

Then forward locally:
```bash
kubectl port-forward <pod-name> 8888:8888
```

---

## Additional Resources

- **Main README**: [Getting Started Guide](../README.md)
- **Architecture**: [Deep Dive](README.md)
- **Managing Workflows**: [Daily Operations](managing_workflows.md)
- **Distributed Training**: [Multi-node Guide](multinode.md)
- **run:ai Docs**: https://docs.run.ai