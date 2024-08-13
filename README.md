# Kubernetes Resource Management Script

This script is designed to interact with your Kubernetes cluster, providing detailed information and analysis of nodes, resource quotas, persistent volumes, and NFS storage usage. It is a versatile tool for Kubernetes administrators, offering multiple output formats and customization options.

## Features

- **Node Analysis**: Retrieves comprehensive details about nodes in your Kubernetes cluster, including roles, CPU, and RAM capacity.
- **Resource Quota Analysis**: Aggregates and reports on resource requests (CPU and memory) across all pods in the cluster.
- **Top Metrics**: Provides real-time CPU and memory usage statistics for each node using Kubernetes metrics.
- **Persistent Volume Analysis**: Lists all Persistent Volume Claims (PVCs) along with their associated NFS paths.
- **NFS Storage Usage Check**: Mounts each unique NFS path as specified by Persistent Volumes, checks the storage usage, and then unmounts it. The depth of the mount can be controlled by a parameter, allowing you to check root or sub-directory usage.

## Usage

### General Command Structure

```bash
python get_info.py --task <task-name> --output <format> [--context <context-name>] [--nfs-level <level>] [--debug <level>] [--parameter <key=value>]
```

### Tasks

- `get-nodes`: Fetches detailed information about the nodes in the cluster.
- `get-resourcequotas`: Summarizes resource quotas based on pod resource requests.
- `get-top`: Provides a real-time summary of CPU and memory usage for each node.
- `get-pvcs`: Lists all PVCs and their NFS paths.
- `check-nfs`: Mounts NFS paths based on PV configurations and checks storage usage.
- `get-k8s-info`: Retrieves and summarizes basic Kubernetes cluster information, including Kubernetes version, node count, and namespace count.

### Output Formats

- `yaml`: Outputs data in YAML format.
- `json`: Outputs data in JSON format.
- `csv`: Outputs data in CSV format.

### Parameters

- `--context | -c <context-name>`: (Optional) Specify the Kubernetes context to use. If not provided, the current context is used.
- `--nfs-level | -l <level>`: (Optional, for `check-nfs` task) Sets how deep to mount the NFS directory. Default is `0`, meaning the root directory will be mounted.
- `--debug | -d <level>`: (Optional) Sets the logging level. Available options: `ERROR`, `WARN`, `INFO`, `DEBUG`. Default is `ERROR`.
- `--parameter | -p <key=value>`: (Optional, for `get-k8s-info` task) Passes custom parameters to include in the output.

### Examples

#### 1. Get Node Details in JSON Format

```bash
python get_info.py --task get-nodes --output json
```

This command fetches details about all nodes in the cluster and outputs the information in JSON format.

#### 2. Summarize Resource Quotas in YAML Format

```bash
python get_info.py --task get-resourcequotas --output yaml
```

This command gathers and summarizes resource quotas from all pods across all namespaces, outputting the data in YAML format.

#### 3. Retrieve Top Metrics with Detailed Logging

```bash
python get_info.py --task get-top --output csv --debug INFO
```

This command retrieves real-time CPU and memory usage metrics for each node, outputs the data in CSV format, and logs all information-level messages.

#### 4. List Persistent Volume Claims in CSV Format

```bash
python get_info.py --task get-pvcs --output csv
```

This command lists all PVCs in the cluster along with their associated NFS paths and outputs the data in CSV format.

#### 5. Check NFS Storage Usage for Root NFS Directories

```bash
python get_info.py --task check-nfs --output json --nfs-level 0
```

This command mounts the root NFS directories as specified by the Persistent Volumes, checks their storage usage, and outputs the results in JSON format.

#### 6. Check NFS Storage Usage for Sub-Directories

```bash
python get_info.py --task check-nfs --output yaml --nfs-level 1 --debug WARN
```

This command mounts each NFS path one level deep, checks storage usage, and outputs the results in YAML format. Warnings and errors during execution are logged.

#### 7. Get Kubernetes Cluster Info with Custom Parameters

```bash
python get_info.py --task get-k8s-info --output json --parameter "Environment=Production" --parameter "Owner=DevOps"
```

This command retrieves basic Kubernetes cluster information and includes custom parameters in the output, formatted in JSON.

## Logging

The script offers multiple levels of logging to help you monitor its execution:

- **ERROR**: Logs only critical issues.
- **WARN**: Logs warnings and errors.
- **INFO**: Logs general information and above.
- **DEBUG**: Logs detailed debug information, including command executions and outputs.

The default logging level is `ERROR`, which can be adjusted with the `--debug` or `-d` parameter.
