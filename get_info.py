import subprocess
import sys
import json

def print_usage():
    print("Usage: script.py --task|-t <get-nodes|get-resourcequotas|get-top> --output|-o <yaml|json|csv>")

def run_command(cmd):
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stderr)
        sys.exit(1)
    return result.stdout.strip()

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

if __name__ == "__main__":
    if len(sys.argv) != 5 or sys.argv[1] not in ("--task", "-t") or sys.argv[3] not in ("--output", "-o"):
        print_usage()
        sys.exit(1)

    task = sys.argv[2]
    output_format = sys.argv[4]

    if output_format not in ("yaml", "json", "csv"):
        print_usage()
        sys.exit(1)

    if task == "get-nodes":
        get_nodes(output_format)
    elif task == "get-resourcequotas":
        get_resourcequotas(output_format)
    elif task == "get-top":
        get_top(output_format)
    else:
        print_usage()
        sys.exit(1)
