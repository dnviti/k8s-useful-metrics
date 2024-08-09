import subprocess
import sys
import json
import os
import shutil
import logging

def print_usage():
    print("Usage: script.py --task|-t <get-nodes|get-resourcequotas|get-top|get-pvcs|check-nfs> --output|-o <yaml|json|csv> [--context|-c <context-name>] [--nfs-level|-l <level>] [--debug|-d <ERROR|WARN|INFO|DEBUG>]")

def run_command(cmd):
    logging.debug(f"Executing command: {cmd}")
    process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
    stdout, stderr = process.communicate()
    if process.returncode != 0:
        logging.error(f"Command failed: {stderr}")
        sys.exit(1)
    logging.debug(f"Command output: {stdout}")
    return stdout.strip()

def switch_context(context):
    if context:
        logging.info(f"Switching to context: {context}")
        run_command(f"kubectl config use-context {context}")
    else:
        context = run_command("kubectl config current-context")
        logging.info(f"Using current context: {context}")

def get_node_roles():
    output = run_command("kubectl get nodes -o json")
    nodes = json.loads(output)
    roles = {}
    for item in nodes['items']:
        node_name = item['metadata']['name']
        labels = item['metadata']['labels']
        if 'node-role.kubernetes.io/control-plane' in labels:
            roles[node_name] = "Master"
        else:
            roles[node_name] = "Worker"
    return roles

def convert_to_csv(headers, data):
    lines = [headers]
    for item in data:
        lines.append(",".join(str(i) for i in item))
    return "\n".join(lines)

def convert_to_json(headers, data):
    keys = headers.split(',')
    json_data = [dict(zip(keys, item)) for item in data]
    return json.dumps(json_data, indent=2)

def convert_to_yaml(headers, data):
    keys = headers.split(',')
    yaml_lines = []
    for item in data:
        yaml_lines.append("-")
        for key, value in zip(keys, item):
            yaml_lines.append(f"  {key}: {value}")
    return "\n".join(yaml_lines)

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

def get_nodes(output_format):
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
        memory_gb = int(memory.rstrip('Ki')) // 1024 // 1024
        role = roles[name]
        data.append((role, name, f"{memory_gb}Gi", cpu))
        total_ram += memory_gb
        total_cpu += int(cpu)
        if role == "Worker":
            worker_ram += memory_gb
            worker_cpu += int(cpu)

    data.append(("Somma Totale", "", f"{total_ram}Gi", total_cpu))
    data.append(("Somma Worker", "", f"{worker_ram}Gi", worker_cpu))

    headers = "role,node,ram_gb,cpu"
    process_output(output_format, headers, data)

def get_resourcequotas(output_format):
    logging.info("Fetching resource quotas")
    roles = get_node_roles()
    output = run_command("kubectl get pods --all-namespaces -o json")
    pods = json.loads(output)
    cpu_usage, mem_usage = {}, {}

    for item in pods['items']:
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
        data.append((role, node, f"{allocated_ram_gb}Gi", allocated_cpu_millicores))

    headers = "role,node,allocated_ram_gb,allocated_cpu_millicores"
    process_output(output_format, headers, data)

def get_top(output_format):
    logging.info("Fetching top metrics")
    roles = get_node_roles()
    output = run_command("kubectl get nodes.metrics.k8s.io -o json")
    nodes = json.loads(output)
    data = []
    total_ram, total_cpu, worker_ram, worker_cpu = 0, 0, 0, 0
    worker_count = 0

    for item in nodes['items']:
        node = item['metadata']['name']
        cpu = int(item['usage']['cpu'].rstrip('n')) // 1000000
        ram = int(item['usage']['memory'].rstrip('Ki')) // 1024
        role = roles.get(node, "Unknown")

        data.append((role, node, f"{ram}Mi", f"{cpu}m"))
        total_ram += ram
        total_cpu += cpu

        if role == "Worker":
            worker_ram += ram
            worker_cpu += cpu
            worker_count += 1

    node_count = len(nodes['items'])
    total_ram_gb = total_ram // 1024
    worker_ram_gb = worker_ram // 1024

    data.append(("Somma Totale", "", f"{total_ram_gb}Gi", f"{total_cpu}m"))
    data.append(("Somma Worker", "", f"{worker_ram_gb}Gi", f"{worker_cpu}m"))

    headers = "role,node,ram_mi,cpu_m"
    process_output(output_format, headers, data)

def get_persistent_volumes(output_format):
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
    
    headers = "Namespace,Pvc,Volume,Access Modes,Path"
    process_output(output_format, headers, data)

def check_nfs_storage_usage(output_format, nfs_level):
    mount_dir = "/mnt/sizecheck"
    
    if not os.path.exists(mount_dir):
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

    shutil.rmtree(mount_dir)

if __name__ == "__main__":
    context = None
    nfs_level = 0  # Default level is 0
    debug_level = "ERROR"  # Default logging level is ERROR

    if len(sys.argv) < 5:
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

    # Set up logging based on the debug level, default is ERROR
    logging.basicConfig(level=getattr(logging, debug_level, "ERROR"), format='%(asctime)s - %(levelname)s - %(message)s')

    if not task or not output_format or output_format not in ("yaml", "json", "csv"):
        print_usage()
        sys.exit(1)

    # Switch context before running any tasks
    switch_context(context)

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
    else:
        print_usage()
        sys.exit(1)
