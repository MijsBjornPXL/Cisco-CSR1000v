from ncclient import manager
from ncclient.operations import RPCError
import xml.dom.minidom


def pretty_xml(xml_text):
    try:
        parsed = xml.dom.minidom.parseString(xml_text)
        return parsed.toprettyxml(indent="  ")
    except Exception:
        return xml_text


def get_running_config_netconf(router):
    filter_xml = """
<filter xmlns="urn:ietf:params:xml:ns:netconf:base:1.0">
  <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native"/>
</filter>
"""

    with manager.connect(
        host=router["host"],
        port=router["netconf_port"],
        username=router["username"],
        password=router["password"],
        hostkey_verify=False,
        device_params={"name": "csr"},
        look_for_keys=False,
        allow_agent=False,
        timeout=30,
    ) as m:
        result = m.get_config(source="running", filter=filter_xml)
        return result.xml


def test_netconf(router, log):
    try:
        log(f"Testing NETCONF on {router['host']}:{router['netconf_port']}...")

        with manager.connect(
            host=router["host"],
            port=router["netconf_port"],
            username=router["username"],
            password=router["password"],
            hostkey_verify=False,
            device_params={"name": "csr"},
            look_for_keys=False,
            allow_agent=False,
            timeout=10,
        ) as m:
            capabilities = list(m.server_capabilities)

            log("NETCONF test successful.")
            log(f"NETCONF capabilities found: {len(capabilities)}")

            candidate_supported = any("candidate" in str(cap) for cap in capabilities)
            validate_supported = any("validate" in str(cap) for cap in capabilities)

            log(f"Candidate datastore supported: {candidate_supported}")
            log(f"Validate capability supported: {validate_supported}")

    except Exception as error:
        log(f"NETCONF test failed: {error}")


def deploy_netconf(config_xml, router, log, set_status):
    if not config_xml.strip().startswith("<config"):
        raise ValueError("Selected XML file is not a valid NETCONF <config> file.")

    log("Planned NETCONF configuration payload:")
    log("------------------------------------------------")
    log(pretty_xml(config_xml))
    log("------------------------------------------------")

    log(f"Connecting via NETCONF to {router['host']}:{router['netconf_port']}...")
    set_status("Connecting via NETCONF...", 0.35)

    with manager.connect(
        host=router["host"],
        port=router["netconf_port"],
        username=router["username"],
        password=router["password"],
        hostkey_verify=False,
        device_params={"name": "csr"},
        look_for_keys=False,
        allow_agent=False,
        timeout=30,
    ) as m:
        caps = [str(cap) for cap in m.server_capabilities]

        candidate_supported = any("candidate" in cap for cap in caps)
        validate_supported = any("validate" in cap for cap in caps)

        log(f"Candidate datastore supported: {candidate_supported}")
        log(f"Validate capability supported: {validate_supported}")

        if candidate_supported:
            candidate_locked = False

            try:
                log("Candidate datastore supported. Using candidate + commit.")
                log("Locking candidate datastore...")
                set_status("Locking candidate datastore...", 0.45)

                lock_reply = m.lock(target="candidate")
                candidate_locked = True

                log("NETCONF lock reply:")
                log(str(lock_reply))

                log("Loading config into candidate...")
                set_status("Loading config into candidate...", 0.60)

                edit_reply = m.edit_config(
                    target="candidate",
                    config=config_xml,
                    error_option="stop-on-error"
                )

                log("NETCONF edit-config reply:")
                log(str(edit_reply))

                if validate_supported:
                    log("Validating candidate configuration...")
                    set_status("Validating candidate configuration...", 0.75)

                    validate_reply = m.validate(source="candidate")

                    log("NETCONF validate reply:")
                    log(str(validate_reply))
                else:
                    log("Validate capability not supported. Skipping validation.")

                log("Committing candidate to running...")
                set_status("Committing candidate to running...", 0.90)

                commit_reply = m.commit()

                log("NETCONF commit reply:")
                log(str(commit_reply))

                log("NETCONF deployment successful.")
                set_status("NETCONF deployment successful.", 1.0)

            except RPCError as err:
                log("NETCONF RPCError:")
                log(f"Severity: {getattr(err, 'severity', 'unknown')}")
                log(f"Tag: {getattr(err, 'tag', 'unknown')}")
                log(f"Message: {getattr(err, 'message', 'unknown')}")
                log(str(err))

                if candidate_locked:
                    try:
                        log("Discarding candidate changes...")
                        discard_reply = m.discard_changes()
                        log("NETCONF discard-changes reply:")
                        log(str(discard_reply))
                    except Exception as discard_error:
                        log(f"Could not discard candidate changes: {discard_error}")

                raise

            except Exception as error:
                log(f"NETCONF deployment failed: {error}")

                if candidate_locked:
                    try:
                        log("Discarding candidate changes...")
                        discard_reply = m.discard_changes()
                        log("NETCONF discard-changes reply:")
                        log(str(discard_reply))
                    except Exception as discard_error:
                        log(f"Could not discard candidate changes: {discard_error}")

                raise

            finally:
                if candidate_locked:
                    try:
                        log("Unlocking candidate datastore...")
                        unlock_reply = m.unlock(target="candidate")
                        log("NETCONF unlock reply:")
                        log(str(unlock_reply))
                    except Exception as unlock_error:
                        log(f"Could not unlock candidate datastore: {unlock_error}")

        else:
            log("Candidate datastore not supported. Using running datastore directly.")
            set_status("Editing running datastore...", 0.70)

            edit_reply = m.edit_config(
                target="running",
                config=config_xml,
                error_option="stop-on-error"
            )

            log("NETCONF edit-config reply:")
            log(str(edit_reply))

            log("NETCONF deployment successful.")
            set_status("NETCONF deployment successful.", 1.0)