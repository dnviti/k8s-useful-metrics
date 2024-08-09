# Kubernetes NFS Storage Usage Script

This script is designed to interact with your Kubernetes cluster to gather and analyze resource information, particularly focused on nodes, resource quotas, and persistent volumes. It also has the capability to check NFS storage usage based on Persistent Volume (PV) configurations.

## What Does the Script Do?

- **Node Analysis**: Retrieves and displays information about nodes in your Kubernetes cluster, including their roles, CPU, and RAM capacity.
- **Resource Quota Analysis**: Aggregates and reports on resource requests (CPU and memory) across all pods in the cluster.
- **Top Metrics**: Provides a summary of current CPU and memory usage for each node using Kubernetes metrics.
- **Persistent Volume Analysis**: Lists all Persistent Volume Claims (PVCs) and their associated NFS paths.
- **NFS Storage Usage Check**: Mounts each unique NFS path as specified by the Persistent Volumes, checks the storage usage, and then unmounts it. The depth of the mount can be controlled by a parameter, allowing you to check root or sub-directory usage.

## Usage

### General Command Structure

```bash
python script.py --task <task-name> --output <format> [--context <context-name>] [--nfs-level <level>] [--debug <level>]
```

### Tasks

- `get-nodes`: Fetches details of nodes in the cluster.
- `get-resourcequotas`: Summarizes resource quotas based on pod resource requests.
- `get-top`: Provides a summary of current CPU and memory usage for each node.
- `get-pvcs`: Lists all PVCs and their NFS paths.
- `check-nfs`: Mounts NFS paths based on PV configurations and checks storage usage.

### Output Formats

- `yaml`: Outputs data in YAML format.
- `json`: Outputs data in JSON format.
- `csv`: Outputs data in CSV format.

### Parameters

- `--context | -c <context-name>`: (Optional) Specify the Kubernetes context to use. If not provided, the current context is used.
- `--nfs-level | -l <level>`: (Optional, for `check-nfs` task) Set how deep to mount the NFS directory. Default is `0`, meaning the root directory will be mounted.
- `--debug | -d <level>`: (Optional) Set the logging level. Available options: `ERROR`, `WARN`, `INFO`, `DEBUG`. Default is `ERROR`.

### Examples

#### 1. Get Node Details in JSON Format

```bash
python script.py --task get-nodes --output json
```

This command fetches details about all nodes in the cluster and outputs the information in JSON format.

#### 2. Summarize Resource Quotas in YAML Format

```bash
python script.py --task get-resourcequotas --output yaml
```

This command gathers and summarizes resource quotas from all pods across all namespaces, outputting the data in YAML format.

#### 3. Retrieve Top Metrics with Detailed Logging

```bash
python script.py --task get-top --output csv --debug INFO
```

This command retrieves real-time CPU and memory usage metrics for each node, outputs the data in CSV format, and logs all information-level messages.

#### 4. List Persistent Volume Claims in CSV Format

```bash
python script.py --task get-pvcs --output csv
```

This command lists all PVCs in the cluster along with their associated NFS paths and outputs the data in CSV format.

#### 5. Check NFS Storage Usage for Root NFS Directories

```bash
python script.py --task check-nfs --output json --nfs-level 0
```

This command mounts the root NFS directories as specified by the Persistent Volumes, checks their storage usage, and outputs the results in JSON format.

#### 6. Check NFS Storage Usage for Sub-Directories

```bash
python script.py --task check-nfs --output yaml --nfs-level 1 --debug WARN
```

This command mounts each NFS path one level deep, checks storage usage, and outputs the results in YAML format. Warnings and errors during execution are logged.

## Logging

The script offers multiple levels of logging to help you monitor its execution:

- **ERROR**: Logs only critical issues.
- **WARN**: Logs warnings and errors.
- **INFO**: Logs general information and above.
- **DEBUG**: Logs detailed debug information, including command executions and outputs.

The default logging level is `ERROR`, which can be adjusted with the `--debug` or `-d` parameter.

---

This script is a powerful tool for managing and analyzing your Kubernetes cluster, especially for checking NFS storage usage. By adjusting parameters, you can customize its operation to suit your environment and needs.