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
        raise RuntimeError(
            f"Command failed:\n{command}\n\n{err}"
        )

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

        if not all([
            kvm_host,
            kvm_user,
            kvm_password,
            base_vm,
            new_vm,
            source_qcow,
            libvirt_network
        ]):
            raise ValueError("All VM deployment fields are required.")

        log(f"Connecting to KVM host {kvm_host}...")

        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        ssh.connect(
            hostname=kvm_host,
            username=kvm_user,
            password=kvm_password,
            timeout=20,
            look_for_keys=False,
            allow_agent=False
        )

        # =========================================================
        # READ BASE XML
        # =========================================================

        log(f"Reading XML from base VM: {base_vm}")

        if set_status:
            set_status("Reading base VM XML...", 0.20)

        base_xml = ssh_exec(
            ssh,
            f"sudo virsh dumpxml {base_vm}"
        )

        # =========================================================
        # CLONE DISK
        # =========================================================

        source_dir = os.path.dirname(source_qcow)

        new_disk = f"{source_dir}/{new_vm}.qcow2"
        remote_xml = f"/tmp/{new_vm}.xml"

        log("Cloning disk...")
        log(f"Source: {source_qcow}")
        log(f"Target: {new_disk}")

        if set_status:
            set_status("Cloning QCOW2 disk...", 0.35)

        ssh_exec(
            ssh,
            f"sudo cp '{source_qcow}' '{new_disk}'"
        )

        ssh_exec(
            ssh,
            f"sudo chown libvirt-qemu:kvm '{new_disk}' || true"
        )

        ssh_exec(
            ssh,
            f"sudo chmod 644 '{new_disk}' || true"
        )

        # =========================================================
        # GENERATE XML
        # =========================================================

        log("Generating new VM XML...")

        if set_status:
            set_status("Generating VM XML...", 0.50)

        root = ET.fromstring(base_xml)

        # ---------------------------------------------------------
        # DOMAIN TYPE
        # ---------------------------------------------------------

        root.set("type", "kvm")

        # ---------------------------------------------------------
        # VM NAME
        # ---------------------------------------------------------

        name_node = root.find("name")

        if name_node is not None:
            name_node.text = new_vm

        # ---------------------------------------------------------
        # UUID
        # ---------------------------------------------------------

        uuid_node = root.find("uuid")

        if uuid_node is not None:
            uuid_node.text = str(uuid.uuid4())

        # ---------------------------------------------------------
        # MACHINE TYPE
        # ---------------------------------------------------------

        os_node = root.find("os")

        if os_node is not None:
            type_node = os_node.find("type")

            if type_node is not None:
                type_node.set("machine", "pc-i440fx-7.2")

        # ---------------------------------------------------------
        # FEATURES
        # ---------------------------------------------------------

        features_node = root.find("features")

        if features_node is not None:
            vmport = features_node.find("vmport")

            if vmport is None:
                vmport = ET.SubElement(features_node, "vmport")

            vmport.set("state", "off")

        # ---------------------------------------------------------
        # CPU
        # ---------------------------------------------------------

        cpu_node = root.find("cpu")

        if cpu_node is not None:
            log("Changing CPU mode to host-passthrough...")

            cpu_node.attrib.clear()

            cpu_node.set("mode", "host-passthrough")
            cpu_node.set("check", "none")
            cpu_node.set("migratable", "on")

        # ---------------------------------------------------------
        # SMBIOS
        # ---------------------------------------------------------

        sysinfo_node = root.find("sysinfo")

        if sysinfo_node is None:
            sysinfo_node = ET.SubElement(root, "sysinfo")
            sysinfo_node.set("type", "smbios")

            system_node = ET.SubElement(sysinfo_node, "system")

            manufacturer = ET.SubElement(system_node, "entry")
            manufacturer.set("name", "manufacturer")
            manufacturer.text = "Cisco"

            product = ET.SubElement(system_node, "entry")
            product.set("name", "product")
            product.text = "CSR1000v"

            version = ET.SubElement(system_node, "entry")
            version.set("name", "version")
            version.text = "17.3"

        # ---------------------------------------------------------
        # DISK
        # ---------------------------------------------------------

        disk_source = root.find(".//devices/disk/source")

        if disk_source is not None:
            disk_source.set("file", new_disk)

        # ---------------------------------------------------------
        # REMOVE GRAPHICS
        # ---------------------------------------------------------

        devices_node = root.find("devices")

        if devices_node is not None:

            graphics_node = devices_node.find("graphics")

            if graphics_node is not None:
                devices_node.remove(graphics_node)

            video_node = devices_node.find("video")

            if video_node is not None:
                devices_node.remove(video_node)

            audio_node = devices_node.find("audio")

            if audio_node is not None:
                devices_node.remove(audio_node)

        # ---------------------------------------------------------
        # NETWORKS
        # ---------------------------------------------------------

        interfaces = root.findall(".//devices/interface")

        management_mac = None

        for index, intf in enumerate(interfaces):

            mac_node = intf.find("mac")

            if mac_node is not None:
                new_mac = generate_mac()
                mac_node.set("address", new_mac)

                if index == 0:
                    management_mac = new_mac

            intf.set("type", "network")

            source_node = intf.find("source")

            if source_node is None:
                source_node = ET.SubElement(intf, "source")

            source_node.attrib.clear()
            source_node.set("network", libvirt_network)

        # =========================================================
        # SAVE XML
        # =========================================================

        new_xml = ET.tostring(
            root,
            encoding="unicode"
        )

        log(f"Uploading generated XML to {remote_xml}...")

        if set_status:
            set_status("Uploading VM XML...", 0.60)

        ssh_exec(
            ssh,
            f"cat > '{remote_xml}' << 'EOF'\n{new_xml}\nEOF"
        )

        # =========================================================
        # DEFINE VM
        # =========================================================

        log(f"Defining VM {new_vm}...")

        if set_status:
            set_status("Defining VM...", 0.70)

        ssh_exec(
            ssh,
            f"sudo virsh define '{remote_xml}'"
        )

        # =========================================================
        # START VM
        # =========================================================

        log(f"Starting VM {new_vm}...")

        if set_status:
            set_status("Starting VM...", 0.80)

        ssh_exec(
            ssh,
            f"sudo virsh start {new_vm}"
        )

        # =========================================================
        # WAIT FOR DHCP / IP DISCOVERY
        # =========================================================

        found_ip = ""

        if management_mac:

            log(
                f"Waiting for DHCP lease for management MAC "
                f"{management_mac}..."
            )

            max_attempts = 100

            for attempt in range(max_attempts):

                if set_status:
                    set_status(
                        f"Checking DHCP/ARP... "
                        f"({attempt + 1}/{max_attempts})",
                        0.90
                    )

                # -------------------------------------------------
                # 1) Libvirt DHCP lease check
                # Works for libvirt networks like "default"
                # -------------------------------------------------

                leases = ssh_exec(
                    ssh,
                    f"sudo virsh net-dhcp-leases {libvirt_network} 2>/dev/null || true"
                )

                for line in leases.splitlines():
                    if management_mac.lower() in line.lower():
                        parts = line.split()

                        for part in parts:
                            if "/" in part and "." in part:
                                found_ip = part.split("/")[0]
                                break

                if found_ip:
                    log(f"DHCP IP found via libvirt leases: {found_ip}")
                    break

                # -------------------------------------------------
                # 2) ARP / neighbor table check
                # Works if host already learned the MAC
                # -------------------------------------------------

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

                # -------------------------------------------------
                # 3) Bridge subnet ping sweep
                # Works for Linux bridge networks like br0
                # Only every 10 attempts to avoid spamming network
                # -------------------------------------------------

                if attempt % 10 == 0:
                    log("No DHCP/ARP entry found yet. Running bridge subnet ping sweep...")

                    sweep_cmd = f"""
BRIDGE_IP=$(ip -4 -o addr show {libvirt_network} 2>/dev/null | awk '{{print $4}}' | cut -d/ -f1 | head -1);

if [ -n "$BRIDGE_IP" ]; then
    PREFIX=$(echo "$BRIDGE_IP" | cut -d. -f1-3);

    for i in $(seq 1 254); do
        ping -c1 -W1 $PREFIX.$i >/dev/null 2>&1 &
    done;

    wait;

    ip neigh | grep -i '{management_mac}' || true;
fi
"""

                    sweep_output = ssh_exec(ssh, sweep_cmd)

                    for line in sweep_output.splitlines():
                        parts = line.split()

                        if parts and "." in parts[0]:
                            found_ip = parts[0]
                            break

                    if found_ip:
                        log(f"Ping sweep IP found: {found_ip}")
                        break

                time.sleep(2)

        # =========================================================
        # DONE
        # =========================================================

        if found_ip:
            log(f"VM {new_vm} deployed successfully.")
            log(f"Management IP: {found_ip}")

        else:
            log(
                f"VM {new_vm} deployed successfully, "
                f"but no DHCP lease found yet."
            )

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