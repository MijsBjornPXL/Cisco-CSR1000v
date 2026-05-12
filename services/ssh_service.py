import time
import paramiko

def deploy_ssh_cli(cli_text, router, log, set_status):
    log(f"Connecting via SSH to {router['host']}:22...")
    set_status("Connecting via SSH...", 0.35)

    commands = [
        line.strip()
        for line in cli_text.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]

    if not commands:
        raise ValueError("Selected CLI file does not contain any commands.")

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        ssh.connect(
            hostname=router["host"],
            username=router["username"],
            password=router["password"],
            timeout=15,
            look_for_keys=False,
            allow_agent=False,
        )

        shell = ssh.invoke_shell()
        time.sleep(1)

        if shell.recv_ready():
            shell.recv(65535)

        for index, command in enumerate(commands, start=1):
            log(f"SSH sending: {command}")
            set_status(f"SSH command {index}/{len(commands)}", 0.35 + (index / len(commands)) * 0.55)

            shell.send(command + "\n")
            time.sleep(0.6)

            output = ""
            while shell.recv_ready():
                output += shell.recv(65535).decode(errors="ignore")

            if "% Invalid input" in output or "% Ambiguous command" in output or "% Incomplete command" in output:
                log(output[-1500:])
                raise RuntimeError(f"SSH CLI command failed: {command}")

        shell.send("end\n")
        time.sleep(0.3)
        shell.send("write memory\n")
        time.sleep(1)

        output = ""
        while shell.recv_ready():
            output += shell.recv(65535).decode(errors="ignore")

        if output.strip():
            log("SSH output:")
            log(output[-1500:])

        log("SSH CLI deployment successful.")

    finally:
        ssh.close()