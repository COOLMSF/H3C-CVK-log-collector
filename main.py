import os
import subprocess
import tempfile
import tarfile

LAST_NDAYS = 3

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

def run_commands_and_collect_logs(temp_dir, log_types):
    # @ [0]是要执行的命令
    # @ [1:-1]是命令的参数
    # @ [-1] 是要将命令输出结果保存的文件名称

    common_commands = [

        # 服务状态
        ['bash', '-c', 'for service in cvk-agent cvk-ha network-cvk-agent openvswitch ovn-northd frr; do echo "$service: $(systemctl is-active $service)"; done', 'network-service-status'],

        # 日志文件
        # TODO: convert dmesg timestap
        ['dmesg', 'dmesg'], 
        ['cat', '/var/log/messages', 'messages-log'],
        ['cat', '/var/log/dmesg.old', 'dmesg-old-log'], 

        # 配置文件

        # 版本信息
        ['cat', '/etc/cas_cvk-version', 'cas_cvk-version'],

        # 其他信息

        ['uname', '-a', 'uname'],
        ['lscpu', 'cpuinfo'], 
        ['free', '-h', 'meminfo'],

    ]

    commands = {
        'all': [],
        'network': [

            # network-cvk-agent
            ['sh', '-c', f'find /var/log/network-cvk-agent/ -type f -mtime -{LAST_NDAYS} | tar -czf /tmp/network-cvk-agent.tar.gz -T - && cat /tmp/network-cvk-agent.tar.gz', 'network-cvk-agent.tar.gz'],
            # network-audit-agent
            ['sh', '-c', f'find /var/log/network-audit-agent/ -type f -mtime -{LAST_NDAYS} | tar -czf /tmp/network-audit-agent.tar.gz -T - && cat /tmp/network-audit-agent.tar.gz', 'network-audit-agent.tar.gz'],
            # frr
            ['sh', '-c', f'find /var/log/frr/ -type f -mtime -{LAST_NDAYS} | tar -czf /tmp/frr.tar.gz -T - && cat /tmp/frr.tar.gz', 'frr.tar.gz'],

            # ovn
            ['sh', '-c', f'find /var/log/ovn/ -type f -mtime -{LAST_NDAYS} | tar -czf /tmp/ovn.tar.gz -T - && cat /tmp/ovn.tar.gz', 'ovn.tar.gz'],
            
            # openvswitch
            ['sh', '-c', f'find /var/log/openvswitch/ -type f -mtime -{LAST_NDAYS} | tar -czf /tmp/openvswitch.tar.gz -T - && cat /tmp/openvswitch.tar.gz', 'openvswitch.tar.gz'],

            # 配置文件
            ['cat', '/etc/cvk-agent/cvk-agent.yaml', 'cvk-agent-yaml'],
            ['cat', '/etc/network-cvk-agent/config.json', 'network-cvk-agent-config'],
            ['cat', '/etc/network-audit-agent/config.json', 'network-audit-agent-config'],
            ['cat', '/etc/frr/bgpd.conf', 'frr-config'],

            # 版本信息
            ['sh', '-c', 'rpm -qa | grep -E "cvk-agent|network-cvk-agent|openvswitch|ovn|frr"', 'cvk-agent', 'network-component-version'],
            # 其他信息

        ],
        'compute': [
            # 日志文件
            ['cat', '/var/log/cvk-ha/cvk-ha.log', 'cvk-ha-log'],
            ['cat', '/var/log/libvirt/libvirtd.log', 'libvirt-log'],

            # 配置文件
            ['cat', '/etc/cvk-ha/cvk-ha.yaml', 'cvk-ha-yaml'],

            # 版本信息
            ['cat', '/etc/cas_cvk-version', 'cas_cvk-version'],
            ['sh', '-c', 'rpm -qa | grep -E cvk-agent|cvk-ha', 'compute-component-version'],

            # 其他信息
        ],
        'storage': [
            ['cat', '/var/log/messages', 'messages']
        ],
        'security': [
            ['cat', '/var/log/auth.log', 'auth.log'],
            ['cat', '/var/log/secure', 'secure'],
        ]
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
                    log_name = f"{log_type}_{command[-1]}"
                    print("Executing: ")
                    print_with_color(command[0:-1], "green")
                    output = subprocess.check_output(command[0:-1])

                    # 检查是否存在错误信息
                    # for msg in common_err_msgs:
                    #     if msg in output.decode():
                    #         print_with_color(f"Running {output} failed", "red")
                    #         print_with_color(output, "red")

                    log_path = os.path.join(temp_dir, log_name)
                    with open(log_path, 'wb') as log_file:
                        log_file.write(output)
                    collected_logs[log_name] = log_path
                except subprocess.CalledProcessError as e:

                    print_with_color(f"Collecting {log_name} logs failed", "red")
                    collected_logs[log_name] = f"Error: {e}"

    # Collect system information
    try:
        kernel_version = subprocess.check_output(['uname', '-r']).decode('utf-8').strip()
        log_name = "kernel_version.log"
        log_path = os.path.join(temp_dir, log_name)
        with open(log_path, 'w') as log_file:
            log_file.write(kernel_version)
        collected_logs[log_name] = log_path
    except subprocess.CalledProcessError as e:
        collected_logs[log_name] = f"Error: {e}"

    return collected_logs

def create_tarball(temp_dir, tar_path):
    with tarfile.open(tar_path, 'w') as tar:
        for root, _, files in os.walk(temp_dir):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, temp_dir)
                tar.add(file_path, arcname=arcname)

def get_user_input():

    log_type_mapping = {
        "0": "all",
        "1": "network",
        "2": "compute",
        "3": "storage",
        "4": "security"
    }

    print_with_color("Choose log types to collect (separate multiple choices with commas):", "cyan")
    print_with_color("0. all", "purple")
    print_with_color("1. network", "green")
    print_with_color("2. compute", "blue")
    print_with_color("3. storage", "yellow")
    print_with_color("4. security", "magenta")
    user_input = input("Enter your choices(1-4): ")
    selected_numbers = [choice.strip() for choice in user_input.split(',')]
    
    # Validate and convert the selected numbers to log types
    log_types = []
    for number in selected_numbers:
        if number in log_type_mapping:
            log_types.append(log_type_mapping[number])
        else:
            print_with_color(f"Invalid choice: {number}. Skipping.", "red")
    
    return log_types


if __name__ == "__main__":
    log_types = get_user_input()
    with tempfile.TemporaryDirectory(dir='/tmp/') as temp_dir:
        collected_logs = run_commands_and_collect_logs(temp_dir, log_types)
        tar_path = '/tmp/auto_log.tar'
        create_tarball(temp_dir, tar_path)
        print_with_color(f"Data saved to {tar_path}", "blue")
