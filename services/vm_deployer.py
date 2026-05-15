import os
import time
import uuid
import random
import xml.etree.ElementTree as ET

import paramiko


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
        random.randint(0x00, 0xFF)
    )


def deploy_router_vm(
    kvm_host,
    kvm_user,
    kvm_password,
    base_vm,
    new_vm,
    source_qcow,
    libvirt_network,
    log,
    set_status=None
):
    ssh = None

    try:
        if set_status:
            set_status("Deploying router VM...", 0.10)

        if not all([kvm_host, kvm_user, kvm_password, base_vm, new_vm, source_qcow, libvirt_network]):
            raise ValueError("All VM deployment fields are required.")

        log(f"Connecting to KVM host {kvm_host}...")

        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(
            hostname=kvm_host,
            username=kvm_user,
            password=kvm_password,
            timeout=15,
            look_for_keys=False,
            allow_agent=False
        )

        log(f"Reading XML from base VM: {base_vm}")
        if set_status:
            set_status("Reading base VM XML...", 0.20)

        base_xml = ssh_exec(ssh, f"sudo virsh dumpxml {base_vm}")

        source_dir = os.path.dirname(source_qcow)
        new_disk = f"{source_dir}/{new_vm}.qcow2"
        remote_xml = f"/tmp/{new_vm}.xml"

        log(f"Cloning disk:")
        log(f"Source: {source_qcow}")
        log(f"Target: {new_disk}")

        if set_status:
            set_status("Cloning QCOW2 disk...", 0.35)

        ssh_exec(ssh, f"sudo cp '{source_qcow}' '{new_disk}'")
        ssh_exec(ssh, f"sudo chown libvirt-qemu:libvirt-qemu '{new_disk}' || true")
        ssh_exec(ssh, f"sudo chmod 644 '{new_disk}' || true")

        log("Generating new VM XML...")
        if set_status:
            set_status("Generating VM XML...", 0.50)

        root = ET.fromstring(base_xml)

        cpu_node = root.find("cpu")
        if cpu_node is not None:
            log("Changing CPU mode to host-model...")
            cpu_node.attrib.clear()
            cpu_node.set("mode", "host-model")        

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

            # Force all interfaces to libvirt NAT/default network
            intf.set("type", "network")

            source_node = intf.find("source")
            if source_node is None:
                source_node = ET.SubElement(intf, "source")

            source_node.attrib.clear()
            source_node.set("network", libvirt_network)

        new_xml = ET.tostring(root, encoding="unicode")

        log(f"Uploading generated XML to {remote_xml}...")
        if set_status:
            set_status("Uploading VM XML...", 0.60)

        ssh_exec(ssh, f"cat > '{remote_xml}' << 'EOF'\n{new_xml}\nEOF")

        log(f"Defining VM {new_vm}...")
        if set_status:
            set_status("Defining VM...", 0.70)

        ssh_exec(ssh, f"sudo virsh define '{remote_xml}'")

        log(f"Starting VM {new_vm}...")
        if set_status:
            set_status("Starting VM...", 0.80)

        ssh_exec(ssh, f"sudo virsh start {new_vm}")

        found_ip = ""

        if management_mac:
            log(f"Waiting for DHCP lease for management MAC {management_mac}...")

            max_attempts = 60

            for attempt in range(max_attempts):
                if set_status:
                    set_status(f"Checking DHCP lease... ({attempt + 1}/{max_attempts})", 0.85)

                leases = ssh_exec(
                    ssh,
                    f"sudo virsh net-dhcp-leases {libvirt_network} || true"
                )

                for line in leases.splitlines():
                    if management_mac.lower() in line.lower():
                        parts = line.split()

                        for part in parts:
                            if "/" in part and "." in part:
                                found_ip = part.split("/")[0]
                                break

                if found_ip:
                    log(f"DHCP IP found: {found_ip}")
                    break

                # Fallback via ARP/neigh
                arp_output = ssh_exec(
                    ssh,
                    f"ip neigh | grep -i '{management_mac}' || true"
                )

                for line in arp_output.splitlines():
                    parts = line.split()

                    if parts and "." in parts[0]:
                        found_ip = parts[0]
                        break

                if found_ip:
                    log(f"ARP IP found: {found_ip}")
                    break

                time.sleep(2)

        if found_ip:
            log(f"VM {new_vm} deployed successfully.")
            log(f"Management IP: {found_ip}")
        else:
            log(f"VM {new_vm} deployed successfully, but no DHCP lease found yet.")

        if set_status:
            set_status("Router VM deployed.", 1.0)

        return {
            "vm_name": new_vm,
            "disk": new_disk,
            "xml": remote_xml,
            "management_mac": management_mac,
            "ip": found_ip
        }

    finally:
        if ssh:
            ssh.close()