import os
import subprocess
import tempfile
import tarfile

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

        # 日志文件
        ['systemctl', 'is-active', 'cvk-agent', 'systemctl-cvk-agent-status-log'],
        ['systemctl', 'is-active', 'cvk-ha', 'systemctl-cvk-ha-status-log'],
        ['systemctl', 'is-active', 'network-cvk-agent', 'systemctl-network-cvk-agent-status-log'],
        ['systemctl', 'is-active', 'openvswitch', 'systemctl-openvswitch-status-log'],
        ['systemctl', 'is-active', 'ovn-northd', 'systemctl-ovn-northd-status-log'],
        ['systemctl', 'is-active', 'frr', 'systemctl-frr-status-log'],

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

            # 日志文件
            ['cat', '/var/log/messages', 'messages-log'],
            ['cat', '/var/log/network-cvk-agent/network-cvk-agent.log', 'network-cvk-agent-log'],
            ['cat', '/var/log/network-audit-agent/network-audit-agent.log', 'network-audit-agent-log'],

            # frr
            ['cat', '/var/log/frr/bgpd.log', 'frr-log'],
            ['cat', '/var/log/frr/ospfd.log', 'ospfd-log'],
            ['cat', '/var/log/frr/zebra.log', 'zebra-log'],

            # ovn
            ['cat', '/var/log/ovn/ovn-controller.log', 'ovn-controller-log'],
            ['cat', '/var/log/ovn/ovn-northd.log', 'ovn-northd-log'],
            ['cat', '/var/log/ovn/ovsdb-server-nb.log', 'ovsdb-server-nb-log'],
            ['cat', '/var/log/ovn/ovsdb-server-sb.log', 'ovsdb-server-sb-log'],

            # openvswitch
            ['cat', '/var/log/openvswitch/ovs-vswitchd.log', 'ovs-vswitchd-log'],
            ['cat', '/var/log/openvswitch/ovs-ctl.log', 'ovs-ctl-log'],
            ['cat', '/var/log/openvswitch/ovsdb-server.log', 'ovsdb-server-log'],

            # 配置文件
            ['cat', '/etc/cvk-agent/cvk-agent.yaml', 'cvk-agent-yaml'],
            ['cat', '/etc/network-cvk-agent/config.json', 'network-cvk-agent-config'],
            ['cat', '/etc/network-audit-agent/config.json', 'network-audit-agent-config'],
            ['cat', '/etc/frr/bgpd.conf', 'frr-config'],

            # 版本信息
            ['sh', '-c', 'rpm -qa | grep cvk-agent', 'cvk-agent-version'],
            ['sh', '-c', 'rpm -qa | grep network-cvk-agent', 'network-cvk-agent-version'],
            ['sh', '-c', 'rpm -qa | grep openvswitch', 'openvswitch-version'],
            ['sh', '-c', 'rpm -qa | grep ovn', 'ovn-version'],
            ['sh', '-c', 'rpm -qa | grep frr', 'frr-version'],

            # 其他信息

        ],
        # TODO: convert dmesg timestap
        'compute': [
            # 日志文件
            ['dmesg', 'dmesg'], 
            ['cat', '/var/log/dmesg.old', 'dmesg-old-log'], 
            ['cat', '/var/log/cvk-ha/cvk-ha.log', 'cvk-ha-log'],
            ['cat', '/var/log/libvirt/libvirtd.log', 'libvirt-log'],

            # 配置文件
            ['cat', '/etc/cvk-ha/cvk-ha.yaml', 'cvk-ha-yaml'],

            # 版本信息
            ['cat', '/etc/cas_cvk-version', 'cas_cvk-version'],
            ['sh', '-c', 'rpm -qa | grep cvk-agent', 'cvk-agent'],
            ['sh', '-c', 'rpm -qa | grep cvk-ha', 'cvk-ha'],

            # 其他信息
        ],
        'storage': [
            ['cat', '/var/log/messages', 'messages']
        ],
        'security': [
            ['cat', '/var/log/auth.log', 'auth.log'],
            ['cat', '/var/log/secure', 'secure'],
            ['cat', '/var/log/frr/bgpd.log-20240805.gz', 'bgpd.log-20240805.gz']
        ]
    }

    # Iterate through each key in the commands dictionary
    for key in commands:
        # Append each command in common_commands to the list associated with the key
        for command in common_commands:
            commands[key].append(command)

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
