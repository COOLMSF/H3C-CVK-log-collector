from datetime import datetime
from pathlib import Path
import socket
import os
from os.path import isdir
import subprocess
import tempfile
import tarfile
import json
import shutil
import time

g_last_ndays = 3

banner_top = "============================================================================="
banner_btm = "============================================================================="

common_err_msgs = {
    "err",
    "error", 
    "failed",
    "fail",
    "failure",
    "not found"
    "unhealthy",
}

def print_with_color(text, color):
    color_codes = {
        "red": "\033[91m",
        "green": "\033[92m",
        "yellow": "\033[93m",
        "blue": "\033[94m",
        "magenta": "\033[95m",
        "cyan": "\033[96m",
        "white": "\033[97m",
        "purple": "\033[35m",  # Using magenta for purple
        "orange": "\033[33m",  # Using yellow for orange (approximate)
    }
    end_code = "\033[0m"
    
    if color in color_codes:
        print(f"{color_codes[color]}{text}{end_code}")
    else:
        print(text)


def cleanup_recent_tar_files(project_name, directory, minutes=10):
    current_time = time.time()
    cutoff_time = current_time - (minutes * 60)

    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith('.tar.gz'):
                file_path = os.path.join(root, file)
                file_stat = os.stat(file_path)
                file_mtime = file_stat.st_mtime

                if file_mtime >= cutoff_time:
                    os.remove(file_path)
                    print_with_color(f"Deleted recent tar file: {file_path}", "yellow")

    # 删除对应目录
    os.system(f'rm -rf {project_name}')

def get_cvk_master_ip():
    return json.load(open('/var/lib/cvk-ha/nodes.json'))['MasterNode']['ManageIp']

def run_commands_and_collect_logs(temp_dir, log_types):
    # @ [0]是要执行的命令
    # @ [1:-1]是命令的参数
    # @ [-1] 是要将命令输出结果保存的文件名称


    try:
        cvk_master_ip = get_cvk_master_ip()
    except Exception as e:
        print_with_color(f"Failed to get master ip: {e}", "red")
        # return

    common_commands = [

        # 服务状态
        ['bash', '-c', f'echo "{banner_top}\nService Status:"; for service in cvk-agent cvk-ha network-cvk-agent openvswitch ovn-northd frr; do echo "$service: $(systemctl is-active $service)"; done; echo {banner_btm}', 'network-service-status', 'info'],

        # 日志文件
        # TODO: convert dmesg timestap
        ['dmesg', 'dmesg-log', 'log'], 
        ['cat', '/var/log/messages', 'messages', 'log'],
        ['cat', '/var/log/dmesg.old', 'dmesg.old', 'log'], 

        # 配置文件

        # 主机信息
    #     ['sh', '-c', 
    #      f'''
    #         echo "{banner_top}";
    #         echo -e "Host Info:\n\n$(hostname)\n\nKernel Version:\n\n$(uname -a)\n\nDisk Info:\n\n$(df -h)\n\nMem Info:\n\n$(free -h)\n\nCVK Version:\n\n$(cat /etc/cas_cvk-version)\n\nCPU Info:\n\n$(lscpu | grep -E "Architecture|Vendor ID|Model name")\n\n;echo {banner_btm}"''', 
    #      'host-info', 'info'],
    # ]
        ['sh', '-c', 
         f'''
            echo -e "{banner_top}\nHost Info:\n$(hostname)\n{banner_btm}\nKernel Version:\n$(uname -a)\n{banner_btm}\nDisk Info:\n$(df -h)\n{banner_btm}\nMem Info:\n$(free -h)\n{banner_btm}\nCVK Version:\n$(cat /etc/cas_cvk-version)\n{banner_btm}\nCPU Info:\n$(lscpu | grep -E "Architecture|Vendor ID|Model name")\n{banner_btm}\n
            "
        ''', 
         'host-info', 'info'],
    ]

    commands = {
        'all': [],
        'network': [

            # network-cvk-agent
            ['sh', '-c', f'find /var/log/network-cvk-agent/ -type f -mtime -{g_last_ndays} | tar -czf /tmp/network-cvk-agent.tar.gz -T - && cat /tmp/network-cvk-agent.tar.gz', 'network-cvk-agent.tar.gz', 'log'],
            # network-audit-agent
            ['sh', '-c', f'find /var/log/network-audit-agent/ -type f -mtime -{g_last_ndays} | tar -czf /tmp/network-audit-agent.tar.gz -T - && cat /tmp/network-audit-agent.tar.gz', 'network-audit-agent.tar.gz', 'log'],
            # frr
            ['sh', '-c', f'find /var/log/frr/ -type f -mtime -{g_last_ndays} | tar -czf /tmp/frr.tar.gz -T - && cat /tmp/frr.tar.gz', 'frr.tar.gz', 'log'],

            # ovn
            ['sh', '-c', f'find /var/log/ovn/ -type f -mtime -{g_last_ndays} | tar -czf /tmp/ovn.tar.gz -T - && cat /tmp/ovn.tar.gz', 'ovn.tar.gz', 'log'],
            
            # openvswitch
            ['sh', '-c', f'find /var/log/openvswitch/ -type f -mtime -{g_last_ndays} | tar -czf /tmp/openvswitch.tar.gz -T - && cat /tmp/openvswitch.tar.gz', 'openvswitch.tar.gz', 'log'],

            # 配置文件
            ['cat', '/etc/cvk-agent/cvk-agent.yaml', 'cvk-agent-yaml', 'config'],
            ['cat', '/etc/network-cvk-agent/config.json', 'network-cvk-agent-config', 'config'],
            ['cat', '/etc/network-audit-agent/config.json', 'network-audit-agent-config', 'config'],
            ['cat', '/etc/frr/bgpd.conf', 'frr-config', 'config'],

            # 版本信息
            ['sh', '-c', f'echo -e "{banner_top}\nNetwork Component Versions:\n$(rpm -qa | grep -E "cvk-agent|network-cvk-agent|openvswitch|ovn|frr")\n{banner_btm}\n"', 'cvk-agent', 'network-component-version', 'info'],
            # 其他信息
        ],
        'compute': [
            # 日志文件
            ['sh', '-c', f'find /var/log/cvk-ha/ -type f -mtime -{g_last_ndays} | tar -czf /tmp/cvk-ha.tar.gz -T - && cat /tmp/cvk-ha.tar.gz', 'cvk-ha.tar.gz', 'log'],

            # 获取master节点cvk-ha日志
            # ['sh', '-c', f'master_ip=$(python3 -c "import json; print(f\"{json.load(open('/var/lib/cvk-ha/nodes.json'))['MasterNode']['ManageIp']}\")"); G_LAST_NDAYS={g_last_ndays}; ssh root@$master_ip "find /var/log/cvk-ha/ -type f -mtime -$G_LAST_NDAYS  | tar -czf /tmp/cvk-master-ha.tar.gz -T - && cat /tmp/cvk-master-ha.tar.gz"', 'log'],

            ['sh', '-c', f'ssh root@{cvk_master_ip} "find /var/log/cvk-ha/ -type f -mtime -{g_last_ndays} | tar -czf /tmp/cvk-master-ha.tar.gz -T - && cat /tmp/cvk-master-ha.tar.gz"', 'cvk-master-ha-log.tar.gz', 'log'],

            ['cat', '/var/log/libvirt/libvirtd.log', 'libvirt.log', 'log'],
            ['sh', '-c', 'tar -czf /tmp/qemu.tar.gz /var/log/libvirt/qemu && cat /tmp/qemu.tar.gz', 'qemu.tar.gz', 'log'],

            # 配置文件
            ['cat', '/etc/cvk-ha/cvk-ha.yaml', 'cvk-ha-yaml', 'config'],

            # 版本信息
            ['sh', '-c', f'echo -e "{banner_top}\nCompute Component Versions:\n$(rpm -qa | grep -E "cvk-agent|cvk-ha")\n{banner_btm}\n"', 'compute-component-version', 'info'],
            # 其他信息
        ],
    }

    # Iterate through each key in the commands dictionary
    for key in commands:
        # Append each command in common_commands to the list associated with the key
        for command in common_commands:
            commands[key].append(command)

        # commands[key] = list(set(commands[key]))

    # 收集所有日志，选项0，把所有其他的选项都包含进来
    # Populate the 'all' key with all commands from other keys
    for key in commands:
        if key != 'all':
            commands['all'].extend(commands[key])

    collected_logs = {}

    for log_type in log_types:
        print_with_color(f"Collecting {log_type} logs...", "green")
        print(commands[log_type])

        if log_type in commands:
            for idx, command in enumerate(commands[log_type]):
                try:
                    log_name = f"{command[-2]}"
                    print("Executing: ")
                    print_with_color(command[0:-2], "green")
                    output = subprocess.check_output(command[0:-2])

                    # 检查是否存在错误信息
                    # for msg in common_err_msgs:
                    #     if msg in output.decode():
                    #         print_with_color(f"Running {output} failed", "red")
                    #         print_with_color(output, "red")

                    # 检查是否存在config, log, info目录，如果不存在，则创建

                    if not os.path.exists(os.path.join(temp_dir, command[-1])):
                        print_with_color(f"Creating {os.path.join(temp_dir, command[-1])} {command[-1]} directory", "green")
                        os.makedirs(os.path.join(temp_dir, command[-1]))

                    log_path = os.path.join(os.path.join(temp_dir,command[-1]), log_name)
                    print_with_color(f"Writing {log_name} logs to {log_path}", "yellow")

                    with open(log_path, 'wb') as log_file:
                        log_file.write(output)

                    collected_logs[log_name] = log_path
                except subprocess.CalledProcessError as e:

                    print_with_color(f"Collecting {log_name} logs failed", "red")
                    collected_logs[log_name] = f"Error: {e}"

    return collected_logs

# def create_tarball(temp_dir, tar_path):
#     with tarfile.open(tar_path, 'w') as tar:
#         for root, _, files in os.walk(temp_dir):
#             for file in files:
#                 file_path = os.path.join(root, file)
#                 arcname = os.path.relpath(file_path, temp_dir)
#                 tar.add(file_path, arcname=arcname)

# def create_tarball(temp_dir, tar_path):
#     # Extract the base name of the tarball (without extension)
#     tar_base_name = os.path.splitext(os.path.basename(tar_path))[0]
#     
#     # Create a top-level directory name
#     top_level_dir = os.path.join(temp_dir, tar_base_name)
#     
#     # Ensure the top-level directory exists
#     os.makedirs(top_level_dir, exist_ok=True)
#     
#     # Move all files from temp_dir to the top-level directory
#     for root, _, files in os.walk(temp_dir):
#         for file in files:
#             file_path = os.path.join(root, file)
#             new_file_path = os.path.join(top_level_dir, os.path.relpath(file_path, temp_dir))
#             os.makedirs(os.path.dirname(new_file_path), exist_ok=True)
#             os.rename(file_path, new_file_path)
#     
#     # Create the tarball
#     with tarfile.open(tar_path, 'w') as tar:
#         for root, _, files in os.walk(top_level_dir):
#             for file in files:
#                 file_path = os.path.join(root, file)
#                 arcname = os.path.relpath(file_path, top_level_dir)
#                 tar.add(file_path, arcname=arcname)
#     
#     # Clean up: Remove the top-level directory
#     for root, _, files in os.walk(top_level_dir, topdown=False):
#         for file in files:
#             os.remove(os.path.join(root, file))
#         os.rmdir(root)


def create_tarball(temp_dir, tar_path):
    # Extract the base name of the tarball (without extension)
    tar_base_name = os.path.splitext(os.path.basename(tar_path))[0]
    
    # Create the tarball
    with tarfile.open(tar_path, 'w') as tar:
        for root, _, files in os.walk(temp_dir):
            for file in files:
                file_path = os.path.join(root, file)
                # Create the relative path with the top-level directory
                arcname = os.path.join(tar_base_name, os.path.relpath(file_path, temp_dir))
                tar.add(file_path, arcname=arcname)

def get_user_input():

    print_with_color("How many days of logs to collect?(default 3 days)", "cyan")
    global g_last_ndays
    g_last_ndays = input()

    log_type_mapping = {
        "0": "all",
        "1": "network",
        "2": "compute",
        "3": "storage",
        "4": "security"
    }

    # print_with_color("Choose log types to collect (separate multiple choices with commas):", "cyan")
    # print_with_color("0. all", "purple")
    # print_with_color("1. network", "green")
    # print_with_color("2. compute", "blue")
    # print_with_color("3. storage", "yellow")
    # print_with_color("4. security", "magenta")
    # user_input = input("Enter your choices(1-4): ")
    # selected_numbers = [choice.strip() for choice in user_input.split(',')]
    
    # Validate and convert the selected numbers to log types
    #nlog_types = []
    #nfor number in selected_numbers:
    #n    if number in log_type_mapping:
    #n        log_types.append(log_type_mapping[number])
    #n    else:
    #n        print_with_color(f"Invalid choice: {number}. Skipping.", "red")

    # 只收集所有日志，不区分计算和网络
    log_types = ["all"]

    return log_types


if __name__ == "__main__":
    log_types = get_user_input()
    default_project_name = 'test'
    print_with_color(f"enter project name(default is:%s)" % default_project_name, "green")
    project_name = input()

    # Get the current date and time
    current_datetime = datetime.now()
    # Format the date and time as YYYY-MM-DD HH:MM:SS
    current_datetime = current_datetime.strftime("%Y-%m-%d-%H%M%S")

    hostname = socket.gethostname()

    if not project_name:
        tar_path = "/tmp/" + project_name + '-' + hostname + '-' + current_datetime
    else:
        tar_path = default_project_name
        tar_path = "/tmp/" + project_name + '-' + hostname + '-' + current_datetime

    tar_path = Path(tar_path)

    if os.path.isdir(tar_path):
        print_with_color(f"Directory {tar_path.name} already exists. Delete it.", "red")
        # Remove the directory and its contents recursively
        shutil.rmtree(tar_path)
    else:
        # Create the directory
        tar_path.mkdir(parents=True, exist_ok=True)
        print_with_color(f"Directory '{tar_path.name}' created.", "green")
        collected_logs = run_commands_and_collect_logs(tar_path.name, log_types)

        create_tarball(tar_path.name, tar_path.name + '.tar')
        print_with_color(f"Data saved to {tar_path}.tar", "red")
        print_with_color(f"Cleaning up...", "yellow")
        # 删除最近10分钟的临时日志文件，和项目相关文件
        cleanup_recent_tar_files(tar_path.name, "/tmp", minutes=10)

