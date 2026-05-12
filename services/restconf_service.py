import json
from urllib.parse import quote
import requests

from constants import RESTCONF_HEADERS

requests.packages.urllib3.disable_warnings()


def pretty_json(data):
    try:
        if isinstance(data, str):
            data = json.loads(data)
        return json.dumps(data, indent=4)
    except Exception:
        return str(data)


def log_restconf_request(method, url, payload, log):
    log("RESTCONF planned change:")
    log("------------------------------------------------")
    log(f"Method: {method}")
    log(f"URL: {url}")

    if payload is not None:
        log("Payload:")
        log(pretty_json(payload))
    else:
        log("Payload: <none>")

    log("------------------------------------------------")


def check_response(resp, action, log):
    log(f"{action} status: {resp.status_code}")

    if resp.text:
        log(f"{action} response body:")
        log(resp.text)
    else:
        log(f"{action} response body: <empty>")

    if resp.status_code in [200, 201, 204]:
        log(f"{action} successful.")
        return

    log(f"{action} failed.")
    resp.raise_for_status()


def get_running_config_restconf(router, log):
    url = f"{router['restconf_base_url']}/restconf/data/Cisco-IOS-XE-native:native"

    log_restconf_request("GET", url, None, log)

    response = requests.get(
        url,
        auth=(router["username"], router["password"]),
        headers={"Accept": "application/yang-data+json"},
        verify=False,
        timeout=30,
    )

    check_response(response, "Retrieve running config", log)

    try:
        return json.dumps(response.json(), indent=4)
    except Exception:
        return response.text


def test_restconf(router, log):
    try:
        log(f"Testing RESTCONF on {router['restconf_base_url']}...")

        url = f"{router['restconf_base_url']}/restconf/data/Cisco-IOS-XE-native:native"

        log_restconf_request("GET", url, None, log)

        response = requests.get(
            url,
            auth=(router["username"], router["password"]),
            headers={"Accept": "application/yang-data+json"},
            verify=False,
            timeout=10,
        )

        check_response(response, "RESTCONF test", log)

    except Exception as error:
        log(f"RESTCONF test failed: {error}")


def patch_hostname(hostname, router, log, set_status):
    set_status(f"Configuring hostname {hostname}...", 0.45)

    url = f"{router['restconf_base_url']}/restconf/data/Cisco-IOS-XE-native:native"

    payload = {
        "Cisco-IOS-XE-native:native": {
            "hostname": hostname
        }
    }

    log_restconf_request("PATCH", url, payload, log)

    resp = requests.patch(
        url,
        auth=(router["username"], router["password"]),
        headers=RESTCONF_HEADERS,
        json=payload,
        verify=False,
        timeout=30,
    )

    check_response(resp, f"Configure hostname {hostname}", log)


def put_interface(interface, router, log, set_status):
    set_status(f"Configuring interface {interface['name']}...", 0.60)

    encoded_name = quote(interface["name"], safe="")
    url = f"{router['restconf_base_url']}/restconf/data/ietf-interfaces:interfaces/interface={encoded_name}"

    payload = {
        "ietf-interfaces:interface": {
            "name": interface["name"],
            "description": interface["description"],
            "type": "iana-if-type:ethernetCsmacd",
            "enabled": True,
            "ietf-ip:ipv4": {
                "address": [
                    {
                        "ip": interface["ip"],
                        "netmask": interface["netmask"],
                    }
                ]
            },
        }
    }

    log_restconf_request("PUT", url, payload, log)

    resp = requests.put(
        url,
        auth=(router["username"], router["password"]),
        headers=RESTCONF_HEADERS,
        json=payload,
        verify=False,
        timeout=30,
    )

    check_response(resp, f"Configure interface {interface['name']}", log)


def delete_ospf(ospf, router, log, set_status):
    set_status(f"Deleting old OSPF process {ospf['process_id']}...", 0.75)

    url = (
        f"{router['restconf_base_url']}/restconf/data/"
        f"Cisco-IOS-XE-native:native/router/"
        f"Cisco-IOS-XE-ospf:router-ospf/ospf/process-id={ospf['process_id']}"
    )

    log_restconf_request("DELETE", url, None, log)

    resp = requests.delete(
        url,
        auth=(router["username"], router["password"]),
        headers=RESTCONF_HEADERS,
        verify=False,
        timeout=30,
    )

    if resp.status_code == 404:
        log(f"No existing OSPF process {ospf['process_id']} found, skipping delete.")
        if resp.text:
            log(f"Delete OSPF response body: {resp.text}")
        return

    check_response(resp, f"Delete OSPF process {ospf['process_id']}", log)


def post_ospf_process(ospf, router, log, set_status):
    set_status(f"Configuring OSPF process {ospf['process_id']}...", 0.85)

    url = f"{router['restconf_base_url']}/restconf/data/Cisco-IOS-XE-native:native/router"

    payload = {
        "Cisco-IOS-XE-native:router": {
            "Cisco-IOS-XE-ospf:router-ospf": {
                "ospf": {
                    "process-id": [
                        {
                            "id": ospf["process_id"],
                            "router-id": ospf["router_id"],
                            "network": [
                                {
                                    "ip": net["ip"],
                                    "wildcard": net["mask"],
                                    "area": net["area"],
                                }
                                for net in ospf["networks"]
                            ],
                        }
                    ]
                }
            }
        }
    }

    log_restconf_request("PATCH", url, payload, log)

    resp = requests.patch(
        url,
        auth=(router["username"], router["password"]),
        headers=RESTCONF_HEADERS,
        json=payload,
        verify=False,
        timeout=30,
    )

    check_response(resp, f"Configure OSPF process {ospf['process_id']}", log)


def verify_running_config(router, log, set_status):
    set_status("Verifying running config...", 0.95)

    url = f"{router['restconf_base_url']}/restconf/data/Cisco-IOS-XE-native:native"

    log_restconf_request("GET", url, None, log)

    resp = requests.get(
        url,
        auth=(router["username"], router["password"]),
        headers={"Accept": "application/yang-data+json"},
        verify=False,
        timeout=30,
    )

    check_response(resp, "Retrieve running config", log)


def deploy_restconf(config_json_text, router, log, set_status):
    log("Parsing JSON config...")
    set_status("Parsing JSON config...", 0.35)

    config = json.loads(config_json_text)

    log("Full RESTCONF config file content:")
    log("------------------------------------------------")
    log(pretty_json(config))
    log("------------------------------------------------")

    patch_hostname(config["hostname"], router, log, set_status)

    for interface in config["interfaces"]:
        put_interface(interface, router, log, set_status)

    delete_ospf(config["ospf"], router, log, set_status)
    post_ospf_process(config["ospf"], router, log, set_status)
    verify_running_config(router, log, set_status)

    log("RESTCONF deployment successful.")
    set_status("RESTCONF deployment successful.", 1.0)