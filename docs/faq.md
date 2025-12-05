# Frequently Asked Questions (FAQ)

This FAQ covers common questions about the EPFL RCP cluster and this setup.

## Getting Help

If your question isn't answered here or in the [main README](../README.md) and [architecture explainer](README.md):

- **Ask colleagues**: Reach out on Slack channels `#-cluster` or `#-it`
- **Report issues**: Open a ticket to `supportrcp@epfl.ch` for technical problems
- **Contribute**: Add common problems and solutions to this FAQ!

---

## Storage and File Management

### Where should I store my files and training data?

**TL;DR**: Keep everything in `/mloscratch/homes/<your_username>`, including training data.

**Explanation**: The storage system has multiple types:
- **`mloscratch`**: High-performance storage that can be mounted on pods (use this for everything)
- **`mlodata1`**: Long-term replicated storage for permanent artifacts (papers, final results)

Only `mloscratch` can be mounted on pods, so all your code and training data must be there.

**See also**: [File Management guide](managing_workflows.md#file-management)

### How do I move data onto the cluster or between storage systems?

Use the **HaaS machine** to transfer files between `mlodata1` and `mloscratch`:

```bash
ssh <gaspar_username>@haas001.rcp.epfl.ch
```

**See also**: [HaaS Machine guide](managing_workflows.md#the-haas-machine)

---

## Job Management

### My job doesn't show up in `runai list jobs`

**Likely cause**: Wrong PVC (Persistent Volume Claim) name

This can happen when submitting with an incorrect PVC name. For example, RCP-Prod renamed storage from `runai-mlo-$GASPAR_USERNAME-scratch` to `mlo-scratch`.

**Solution**:
1. Check the [run:ai web interface](https://rcpepfl.run.ai/workloads) – your job may still be listed there
2. Resubmit the job with the correct PVC name

> [!NOTE]
> Jobs with wrong PVC names may end up in an unmanageable state and cannot be deleted or stopped. Resubmission is the easiest fix.

### My job has been "Pending" for a long time

**Possible causes**:

1. **Cluster is busy** – Wait a bit longer, check the [dashboard](https://portal.rcp.epfl.ch/)

2. **Incorrect resources requested**
   - Verify CPU, memory, and GPU requests are within limits
   - Check node type is correct (e.g., don't use `G10` on RCP cluster)
   - Use `runai describe job <name>` to see detailed status

**Check cluster usage**: https://portal.rcp.epfl.ch/

---

## VS Code

### VS Code opens an empty window when connecting to my pod

**Explanation**: VS Code opens the pod's home folder (`~/`) by default, not scratch.

**Solution**: Navigate to `/mloscratch/homes/<your_username>` after connecting.

**See also**: [VS Code guide](managing_workflows.md#using-vs-code)

---

## Docker Images

### Can I create my own Docker images?

**Yes!** See the [Creating Custom Docker Images](../README.md#creating-custom-docker-images) guide in the main README.

**Quick steps**:
1. Get registry access at https://ic-registry.epfl.ch/
2. Modify `docker/Dockerfile`
3. Build and push with `docker/publish.sh`

---

## csub.py

### What are the available csub.py arguments?

See the comprehensive reference in the main README:

**[`csub.py` Usage and Arguments](../README.md#csubpy-usage-and-arguments)**

**For advanced users**: `csub.py` wraps `runai submit` and passes most flags 1:1. See the run:ai docs:
- [Training jobs API](https://docs.run.ai/v2.15/developer/cluster-api/reference/training/)
- [Interactive jobs API](https://docs.run.ai/v2.15/developer/cluster-api/reference/interactive/)

---

## Permissions and Errors

### I get permission errors for `/mloscratch/hf_cache/...`

**Cause**: Incorrect user/group permissions or umask settings

**Solution**:

1. **Verify UID/GID in `.env`**:
   - `LDAP_UID`: Your numeric user ID
   - `LDAP_GID`: `83070` (runai-mlo group)

2. **Set umask**:
   ```bash
   echo "umask 007" >> ~/.zshrc
   source ~/.zshrc
   ```
   This ensures group-writable permissions.

3. **Still having issues?** Contact `#-it` or `#-cluster` on Slack

**Background**: The Hugging Face cache (`HF_HOME=/mloscratch/hf_cache`) is shared between users to avoid redundant downloads. Correct permissions are essential for shared access.

---

## GPU and Memory

### I keep getting CUDA out of memory errors

**Understanding GPU allocation**: When you request 1 GPU, you get the **full GPU and all its RAM**. An OOM error means you're saturating the GPU's memory.

**Debugging steps**:

1. **Check memory usage**:
   ```bash
   nvidia-smi  # Basic GPU monitoring
   nvtop       # Interactive GPU monitoring
   ```

2. **Optimize your code**:
   - Reduce batch size
   - Enable gradient checkpointing
   - Use mixed precision training (fp16/bf16)
   - Free unused tensors

3. **Use larger GPUs**:
   - Switch to A100-80GB or H200-140GB
   - Example: `python csub.py -n job --node_type h200 ...`

**GPU memory by type**:
- V100: 40GB
- A100-40GB: 40GB
- A100-80GB: 80GB
- H100: 80GB
- H200: 140GB

---

## Still Need Help?

- **Slack**: `#-cluster` or `#-it` channels
- **Support**: supportrcp@epfl.ch
- **Main docs**: [README](../README.md), [Architecture](README.md), [Workflows](managing_workflows.md)
