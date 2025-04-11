import subprocess
import sys
import json
import os
import shutil
import logging

# Function to print the usage instructions for the script
def print_usage():
    print("Usage: script.py --task|-t <get-nodes|get-resourcequotas|get-top|get-pvcs|check-nfs|get-k8s-info> --output|-o <yaml|json|csv> [--context|-c <context-name>] [--nfs-level|-l <level>] [--debug|-d <ERROR|WARN|INFO|DEBUG>] [--parameter|-p <key=value>]")

# Function to run a shell command and capture its output
def run_command(cmd):
    logging.debug(f"Executing command: {cmd}")
    try:
        process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        stdout, stderr = process.communicate()
        if process.returncode != 0:  # If the command fails, log the error and exit
            logging.error(f"Command failed: {stderr}")
            sys.exit(1)
        logging.debug(f"Command output: {stdout}")
        return stdout.strip()  # Return the output, stripped of any leading/trailing whitespace
    except Exception as e:
        logging.error(f"Exception occurred: {str(e)}")
        sys.exit(1)

# Function to switch the Kubernetes context if provided, or use the current context
def switch_context(context):
    try:
        if context:
            logging.info(f"Switching to context: {context}")
            run_command(f"kubectl config use-context {context}")
        else:
            context = run_command("kubectl config current-context")
            logging.info(f"Using current context: {context}")
    except Exception as e:
        logging.error(f"Failed to switch context: {str(e)}")
        sys.exit(1)

# Function to retrieve the roles of Kubernetes nodes
def get_node_roles():
    try:
        output = run_command("kubectl get nodes -o json")
        nodes = json.loads(output)
        roles = {}
        for item in nodes['items']:
            node_name = item['metadata']['name']
            labels = item['metadata']['labels']
            if 'node-role.kubernetes.io/control-plane' in labels or 'node-role.kubernetes.io/master' in labels:
                roles[node_name] = "Master"
            else:
                roles[node_name] = "Worker"
        return roles
    except Exception as e:
        logging.error(f"Failed to retrieve node roles: {str(e)}")
        sys.exit(1)

# Function to convert data into CSV format
def convert_to_csv(headers, data):
    lines = [headers]
    for item in data:
        lines.append(",".join(str(i) for i in item))
    return "\n".join(lines)

# Function to convert data into JSON format
def convert_to_json(headers, data):
    keys = headers.split(',')
    json_data = [dict(zip(keys, item)) for item in data]
    return json.dumps(json_data, indent=2)

# Function to convert data into YAML format
def convert_to_yaml(headers, data):
    keys = headers.split(',')
    yaml_lines = []
    for item in data:
        yaml_lines.append("-")
        for key, value in zip(keys, item):
            yaml_lines.append(f"  {key}: {value}")
    return "\n".join(yaml_lines)

# Function to process and print the output in the specified format
def process_output(output_format, headers, data):
    if output_format == "yaml":
        logging.info("Converting data to YAML format")
        print(convert_to_yaml(headers, data))
    elif output_format == "json":
        logging.info("Converting data to JSON format")
        print(convert_to_json(headers, data))
    elif output_format == "csv":
        logging.info("Converting data to CSV format")
        print(convert_to_csv(headers, data))

# Function to retrieve and process basic Kubernetes cluster information
def get_k8s_info(output_format, custom_params):
    try:
        logging.info("Fetching Kubernetes cluster information")
        version = run_command("kubectl version --output=json")
        nodes = run_command("kubectl get nodes -o wide")
        namespaces = run_command("kubectl get namespaces -o json")

        version_info = json.loads(version)
        server_version = version_info.get('serverVersion', {})
        version_str = f"{server_version.get('major', 'N/A')}.{server_version.get('minor', 'N/A')}"

        namespaces_info = json.loads(namespaces)
        
        data = [
            ("Kubernetes Version", version_str),
            ("Node Count", len(nodes.splitlines()) - 1),  # Subtract header line
            ("Namespace Count", len(namespaces_info.get('items', []))),
        ]
        
        for key, value in custom_params.items():
            data.append((key, value))
        
        headers = "Parameter,Value"
        process_output(output_format, headers, data)
    except Exception as e:
        logging.error(f"Failed to retrieve Kubernetes cluster information: {str(e)}")
        sys.exit(1)

# Function to retrieve and process node information in the cluster
def get_nodes(output_format):
    try:
        logging.info("Fetching nodes")
        roles = get_node_roles()
        output = run_command("kubectl get nodes -o json")
        nodes = json.loads(output)
        data = []
        total_ram, total_cpu, worker_ram, worker_cpu = 0, 0, 0, 0

        for item in nodes['items']:
            name = item['metadata']['name']
            cpu = item['status']['capacity']['cpu']
            memory = item['status']['capacity']['memory']
            memory_gb = int(memory.rstrip('Ki')) // 1024 // 1024  # Convert memory from Ki to Gi
            role = roles[name]
            data.append((role, name, f"{memory_gb}Gi", cpu))
            total_ram += memory_gb
            total_cpu += int(cpu)
            if role == "Worker":
                worker_ram += memory_gb
                worker_cpu += int(cpu)

        data.append(("Total", "", f"{total_ram}Gi", total_cpu))
        data.append(("Worker Total", "", f"{worker_ram}Gi", worker_cpu))

        headers = "role,node,ram_gb,cpu"
        process_output(output_format, headers, data)
    except Exception as e:
        logging.error(f"Failed to retrieve nodes: {str(e)}")
        sys.exit(1)

# Function to retrieve and process resource quota usage in the cluster
def get_resourcequotas(output_format):
    try:
        logging.info("Fetching resource quotas")
        roles = get_node_roles()
        output = run_command("kubectl get pods --all-namespaces -o json")
        pods = json.loads(output)
        cpu_usage, mem_usage = {}, {}

        total_cpu_millicores, total_ram_gb = 0, 0
        worker_cpu_millicores, worker_ram_gb = 0, 0

        for item in pods['items']:
            
            if "nodeName" not in item['spec']:
                continue
            
            node = item['spec']['nodeName']
            for container in item['spec']['containers']:
                if 'resources' in container and 'requests' in container['resources']:
                    if 'cpu' in container['resources']['requests']:
                        cpu_request = container['resources']['requests']['cpu']
                        if cpu_request.endswith('m'):
                            cpu_usage[node] = cpu_usage.get(node, 0) + int(cpu_request.rstrip('m'))
                        else:
                            cpu_usage[node] = cpu_usage.get(node, 0) + int(cpu_request) * 1000
                    if 'memory' in container['resources']['requests']:
                        mem_request = container['resources']['requests']['memory']
                        if mem_request.endswith('Ki'):
                            mem_usage[node] = mem_usage.get(node, 0) + int(mem_request.rstrip('Ki')) // 1024
                        elif mem_request.endswith('Mi'):
                            mem_usage[node] = mem_usage.get(node, 0) + int(mem_request.rstrip('Mi'))
                        elif mem_request.endswith('Gi'):
                            mem_usage[node] = mem_usage.get(node, 0) + int(mem_request.rstrip('Gi')) * 1024

        data = []
        for node in cpu_usage:
            role = roles[node]
            allocated_ram_gb = mem_usage[node] // 1024 if node in mem_usage else 0
            allocated_cpu_millicores = cpu_usage[node]
            
            # Accumulate totals
            total_cpu_millicores += allocated_cpu_millicores
            total_ram_gb += allocated_ram_gb

            if role == "Worker":
                worker_cpu_millicores += allocated_cpu_millicores
                worker_ram_gb += allocated_ram_gb

            data.append((role, node, f"{allocated_ram_gb}Gi", allocated_cpu_millicores))

        # Add totals to the data
        data.append(("Total", "", f"{total_ram_gb}Gi", total_cpu_millicores))
        data.append(("Worker Total", "", f"{worker_ram_gb}Gi", worker_cpu_millicores))

        headers = "role,node,allocated_ram_gb,allocated_cpu_millicores"
        process_output(output_format, headers, data)
    except Exception as e:
        logging.error(f"Failed to retrieve resource quotas: {str(e)}")
        sys.exit(1)

# Function to retrieve and process top metrics (resource usage) in the cluster
def get_top(output_format):
    try:
        logging.info("Fetching top metrics")
        roles = get_node_roles()
        node_output = run_command("kubectl get nodes -o json")
        metric_output = run_command("kubectl get nodes.metrics.k8s.io -o json")

        nodes = json.loads(node_output)
        metrics = json.loads(metric_output)
        data = []
        total_ram, total_cpu, worker_ram, worker_cpu = 0, 0, 0, 0
        worker_count = 0

        for item in metrics['items']:
            node_name = item['metadata']['name']
            cpu_usage_m = int(item['usage']['cpu'].rstrip('n')) // 1000000
            ram_usage_mi = 0
            
            if item['usage']['memory'].endswith('Ki'):
                ram_usage_mi = int(item['usage']['memory'].rstrip('Ki')) // 1024
            elif item['usage']['memory'].endswith('Mi'):
                ram_usage_mi = int(item['usage']['memory'].rstrip('Mi'))
            elif item['usage']['memory'].endswith('Gi'):
                ram_usage_mi = int(item['usage']['memory'].rstrip('Gi')) * 1024
            else:
                ram_usage_mi = 0
                
            role = roles.get(node_name, "Unknown")
            
            # Find corresponding node capacity
            node_capacity = next(node for node in nodes['items'] if node['metadata']['name'] == node_name)
            cpu_capacity = int(node_capacity['status']['capacity']['cpu'])
            ram_capacity_mi = 0
            
            if node_capacity['status']['capacity']['memory'].endswith('Ki'):
                ram_capacity_mi = int(node_capacity['status']['capacity']['memory'].rstrip('Ki')) // 1024
            elif node_capacity['status']['capacity']['memory'].endswith('Mi'):
                ram_capacity_mi = int(node_capacity['status']['capacity']['memory'].rstrip('Mi'))
            elif node_capacity['status']['capacity']['memory'].endswith('Gi'):
                ram_capacity_mi = int(node_capacity['status']['capacity']['memory'].rstrip('Gi')) * 1024
            else:
                ram_capacity_mi = 0

            # Calculate percentage
            cpu_percent = (cpu_usage_m / (cpu_capacity * 1000)) * 100
            ram_percent = (ram_usage_mi / ram_capacity_mi) * 100

            data.append((role, node_name, f"{ram_usage_mi}Mi", f"{ram_percent:.0f}%", f"{cpu_usage_m}m", f"{cpu_percent:.0f}%"))
            total_ram += ram_usage_mi
            total_cpu += cpu_usage_m

            if role == "Worker":
                worker_ram += ram_usage_mi
                worker_cpu += cpu_usage_m
                worker_count += 1

        total_ram_gb = total_ram // 1024
        worker_ram_gb = worker_ram // 1024

        # Add totals as the final rows
        data.append(("Total", "", f"{total_ram_gb} GB", "", f"{total_cpu}m", ""))
        data.append(("Worker Total", "", f"{worker_ram_gb} GB", "", f"{worker_cpu}m", ""))

        headers = "Role,Node,RAM Used,RAM %,CPU Used,CPU %"
        process_output(output_format, headers, data)
    except Exception as e:
        logging.error(f"Failed to retrieve top metrics: {str(e)}")
        sys.exit(1)

# Function to retrieve and process information about Persistent Volumes in the cluster
def get_persistent_volumes(output_format):
    try:
        logging.info("Fetching persistent volumes")
        access_mode_map = {
            "ReadWriteOnce": "RWO",
            "ReadOnlyMany": "ROX",
            "ReadWriteMany": "RWX",
            "ReadWriteOncePod": "RWOP"
        }
        
        pvc_output = run_command("kubectl get pvc --all-namespaces -o json")
        pv_output = run_command("kubectl get pv -o json")
        
        pvcs = json.loads(pvc_output)
        pvs = json.loads(pv_output)
        
        pv_map = {pv['metadata']['name']: pv for pv in pvs['items']}
        
        data = []
        
        for pvc in pvcs['items']:
            namespace = pvc['metadata']['namespace']
            pvc_name = pvc['metadata']['name']
            volume_name = pvc['spec']['volumeName']
            access_modes = ",".join([access_mode_map.get(mode, mode) for mode in pvc['spec']['accessModes']])
            
            pv = pv_map.get(volume_name, {})
            pv_name = pv.get('metadata', {}).get('name', '-')
            nfs_path = pv.get('spec', {}).get('nfs', {}).get('path', '-')
            
            data.append((namespace, pvc_name, pv_name, access_modes, nfs_path))
        
        headers = "Namespace,PVC,Volume,Access Modes,Path"
        process_output(output_format, headers, data)
    except Exception as e:
        logging.error(f"Failed to retrieve persistent volumes: {str(e)}")
        sys.exit(1)

# Function to check NFS storage usage for Persistent Volumes in the cluster
def check_nfs_storage_usage(output_format, nfs_level):
    try:
        mount_dir = "/mnt/sizecheck"
        
        if not os.path.exists(mount_dir):  # Create the mount directory if it doesn't exist
            logging.debug(f"Creating mount directory: {mount_dir}")
            os.makedirs(mount_dir)
        
        pv_output = run_command("kubectl get pv -o json")
        pvs = json.loads(pv_output)

        mounted_paths = set()
        data = []

        for pv in pvs['items']:
            if pv['spec'].get('nfs'):
                nfs_server = pv['spec']['nfs']['server']
                nfs_path = pv['spec']['nfs']['path']

                # Determine the path to mount based on the nfs_level
                mount_path_parts = nfs_path.strip("/").split("/")
                mount_path = "/" + "/".join(mount_path_parts[:nfs_level + 1])

                # Check if this path has already been mounted
                if (nfs_server, mount_path) not in mounted_paths:
                    logging.info(f"Mounting {nfs_server}:{mount_path} to {mount_dir}")
                    mounted_paths.add((nfs_server, mount_path))
                    
                    mount_cmd = f"mount -t nfs {nfs_server}:{mount_path} {mount_dir}"
                    run_command(mount_cmd)
                    
                    df_output = run_command(f"df -h {mount_dir} | tail -n 1")
                    umount_cmd = f"umount {mount_dir}"
                    logging.info(f"Unmounting {mount_dir}")
                    run_command(umount_cmd)

                    filesystem, size, used, available, percent_used, mountpoint = df_output.split()
                    data.append((nfs_server, mount_path, size, used, available, percent_used))
                else:
                    logging.warning(f"Skipping duplicate mount for {nfs_server}:{mount_path}")
        
        headers = "NFS Server,NFS Path,Size,Used,Available,Percent Used"
        process_output(output_format, headers, data)

        shutil.rmtree(mount_dir)  # Remove the temporary mount directory after use
    except Exception as e:
        logging.error(f"Failed to check NFS storage usage: {str(e)}")
        sys.exit(1)

# Main execution block: parses command-line arguments and executes the specified task
if __name__ == "__main__":
    context = None
    nfs_level = 0  # Default NFS level is 0
    debug_level = "ERROR"  # Default logging level is ERROR
    custom_params = {}

    if len(sys.argv) < 5:  # If not enough arguments are provided, show usage and exit
        print_usage()
        sys.exit(1)

    task = None
    output_format = None

    for i in range(1, len(sys.argv)):
        if sys.argv[i] in ("--task", "-t") and i + 1 < len(sys.argv):
            task = sys.argv[i + 1]
        elif sys.argv[i] in ("--output", "-o") and i + 1 < len(sys.argv):
            output_format = sys.argv[i + 1]
        elif sys.argv[i] in ("--context", "-c") and i + 1 < len(sys.argv):
            context = sys.argv[i + 1]
        elif sys.argv[i] in ("--nfs-level", "-l") and i + 1 < len(sys.argv):
            nfs_level = int(sys.argv[i + 1])
        elif sys.argv[i] in ("--debug", "-d") and i + 1 < len(sys.argv):
            debug_level = sys.argv[i + 1].upper()
        elif sys.argv[i].startswith("-p:"):
            param = sys.argv[i][3:]
            key, value = param.split("=", 1)
            custom_params[key] = value

    # Set up logging based on the debug level, default is ERROR
    logging.basicConfig(level=getattr(logging, debug_level, "ERROR"), format='%(asctime)s - %(levelname)s - %(message)s')

    if not task or not output_format or output_format not in ("yaml", "json", "csv"):
        print_usage()
        sys.exit(1)

    # Switch context before running any tasks
    switch_context(context)

    # Execute the appropriate function based on the specified task
    try:
        if task == "get-nodes":
            get_nodes(output_format)
        elif task == "get-resourcequotas":
            get_resourcequotas(output_format)
        elif task == "get-top":
            get_top(output_format)
        elif task == "get-pvcs":
            get_persistent_volumes(output_format)
        elif task == "check-nfs":
            check_nfs_storage_usage(output_format, nfs_level)
        elif task == "get-k8s-info":
            get_k8s_info(output_format, custom_params)
        else:
            print_usage()  # If an unknown task is provided, show usage and exit
            sys.exit(1)
    except Exception as e:
        logging.error(f"Failed to execute task '{task}': {str(e)}")
        sys.exit(1)
