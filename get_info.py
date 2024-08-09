import subprocess
import sys
import json

def print_usage():
    print("Usage: script.py --task|-t <get-nodes|get-resourcequotas|get-top|get-pvcs> --output|-o <yaml|json|csv> [--context|-c <context-name>]")

def run_command(cmd):
    process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
    stdout, stderr = process.communicate()
    if process.returncode != 0:
        print(stderr)
        sys.exit(1)
    return stdout.strip()

def switch_context(context):
    if context:
        print("Switching to context: {}".format(context))
        run_command("kubectl config use-context {}".format(context))
    else:
        context = run_command("kubectl config current-context")
        print("Using current context: {}".format(context))

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
            yaml_lines.append("  {key}: {value}".format(key=key, value=value))
    return "\n".join(yaml_lines)

def process_output(output_format, headers, data):
    if output_format == "yaml":
        print(convert_to_yaml(headers, data))
    elif output_format == "json":
        print(convert_to_json(headers, data))
    elif output_format == "csv":
        print(convert_to_csv(headers, data))

def get_nodes(output_format):
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
        data.append((role, name, "{memory_gb}Gi".format(memory_gb=memory_gb), cpu))
        total_ram += memory_gb
        total_cpu += int(cpu)
        if role == "Worker":
            worker_ram += memory_gb
            worker_cpu += int(cpu)

    data.append(("Somma Totale", "", "{total_ram}Gi".format(total_ram=total_ram), total_cpu))
    data.append(("Somma Worker", "", "{worker_ram}Gi".format(worker_ram=worker_ram), worker_cpu))

    headers = "role,node,ram_gb,cpu"
    process_output(output_format, headers, data)

def get_resourcequotas(output_format):
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
        data.append((role, node, "{allocated_ram_gb}Gi".format(allocated_ram_gb=allocated_ram_gb), allocated_cpu_millicores))

    headers = "role,node,allocated_ram_gb,allocated_cpu_millicores"
    process_output(output_format, headers, data)

def get_top(output_format):
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

        data.append((role, node, "{ram}Mi".format(ram=ram), "{cpu}m".format(cpu=cpu)))
        total_ram += ram
        total_cpu += cpu

        if role == "Worker":
            worker_ram += ram
            worker_cpu += cpu
            worker_count += 1

    node_count = len(nodes['items'])
    total_ram_gb = total_ram // 1024
    worker_ram_gb = worker_ram // 1024

    data.append(("Somma Totale", "", "{total_ram_gb}Gi".format(total_ram_gb=total_ram_gb), "{total_cpu}m".format(total_cpu=total_cpu)))
    data.append(("Somma Worker", "", "{worker_ram_gb}Gi".format(worker_ram_gb=worker_ram_gb), "{worker_cpu}m".format(worker_cpu=worker_cpu)))

    headers = "role,node,ram_mi,cpu_m"
    process_output(output_format, headers, data)

def get_persistent_volumes(output_format):
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

if __name__ == "__main__":
    context = None

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
    else:
        print_usage()
        sys.exit(1)
