import os
import time
import uuid
import random
import paramiko
import xml.etree.ElementTree as ET

def ssh_exec(ssh, command):
    stdin, stdout, stderr = ssh.exec_command(command)
    out = stdout.read().decode(errors="ignore")
    err = stderr.read().decode(errors="ignore")
    code = stdout.channel.recv_exit_status()

    if code != 0:
        raise RuntimeError(f"Command failed:\n{command}\n\n{err}")

    return out.strip()

def generate_mac():
    return "52:54:00:%02x:%02x:%02x" % (
        random.randint(0x00, 0xFF),
        random.randint(0x00, 0xFF),
        random.randint(0x00, 0xFF),
    )

def deploy_router_vm(params, log, set_status, update_last_log_line):
    ssh = None

    try:
        kvm_host = params["kvm_host"]
        kvm_user = params["kvm_user"]
        kvm_password = params["kvm_password"]
        base_vm = params["base_vm"]
        new_vm = params["new_vm"]
        source_qcow = params["source_qcow"]
        libvirt_network = params["libvirt_network"]

        log(f"Connecting to KVM host {kvm_host}...")

        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(
            hostname=kvm_host,
            username=kvm_user,
            password=kvm_password,
            timeout=15,
        )

        log(f"Reading XML from base VM: {base_vm}")
        base_xml = ssh_exec(ssh, f"sudo virsh dumpxml {base_vm}")

        source_dir = os.path.dirname(source_qcow)
        new_disk = f"{source_dir}/{new_vm}.qcow2"
        remote_xml = f"/tmp/{new_vm}.xml"

        log(f"Cloning disk to {new_disk}...")
        ssh_exec(ssh, f"sudo cp '{source_qcow}' '{new_disk}'")
        ssh_exec(ssh, f"sudo chown libvirt-qemu:libvirt-qemu '{new_disk}' || true")

        root = ET.fromstring(base_xml)

        name_node = root.find("name")
        if name_node is not None:
            name_node.text = new_vm

        uuid_node = root.find("uuid")
        if uuid_node is not None:
            uuid_node.text = str(uuid.uuid4())

        disk_source = root.find(".//devices/disk/source")
        if disk_source is not None:
            disk_source.set("file", new_disk)

        interfaces = root.findall(".//devices/interface")
        management_mac = None

        for index, intf in enumerate(interfaces):
            mac_node = intf.find("mac")
            if mac_node is not None:
                new_mac = generate_mac()
                mac_node.set("address", new_mac)

                if index == 0:
                    management_mac = new_mac

            if index == 0:
                intf.set("type", "network")

                source_node = intf.find("source")
                if source_node is None:
                    source_node = ET.SubElement(intf, "source")

                source_node.attrib.clear()
                source_node.set("network", libvirt_network)

        new_xml = ET.tostring(root, encoding="unicode")

        log(f"Uploading generated XML to {remote_xml}...")
        ssh_exec(ssh, f"cat > '{remote_xml}' << 'EOF'\n{new_xml}\nEOF")

        log(f"Defining VM {new_vm}...")
        ssh_exec(ssh, f"sudo virsh define '{remote_xml}'")

        log(f"Starting VM {new_vm}...")
        ssh_exec(ssh, f"sudo virsh start {new_vm}")

        found_ip = ""

        if management_mac:
            log(f"Waiting for DHCP lease for Gi1 MAC {management_mac}...")

            for attempt in range(60):
                progress_msg = f"Checking DHCP/ARP... ({attempt + 1}/60)"
                set_status(progress_msg, 0.95)

                if attempt == 0:
                    log(progress_msg)
                else:
                    update_last_log_line(progress_msg)

                leases = ssh_exec(ssh, f"sudo virsh net-dhcp-leases {libvirt_network} || true")

                for line in leases.splitlines():
                    if management_mac.lower() in line.lower():
                        for part in line.split():
                            if "/" in part and "." in part:
                                found_ip = part.split("/")[0]
                                break

                if found_ip:
                    update_last_log_line(f"Management IP found for Gi1: {found_ip}")
                    log(f"DHCP IP found: {found_ip}")
                    break

                time.sleep(2)

        return found_ip

    finally:
        if ssh:
            ssh.close()