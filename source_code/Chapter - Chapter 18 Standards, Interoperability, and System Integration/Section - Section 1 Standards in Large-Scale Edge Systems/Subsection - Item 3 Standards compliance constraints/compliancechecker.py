#!/usr/bin/env python3
"""
Production-ready compliance scanner for edge nodes.
Checks: TLS server min version, MQTT/OPC-UA ports, TSN driver via SSH ethtool.
"""
import ssl
import socket
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
import paramiko  # SSH client; install with `pip install paramiko`
from typing import Dict

logging.basicConfig(level=logging.INFO)
TIMEOUT = 5.0

def check_tls_min_version(host: str, port: int = 443, min_version=ssl.TLSVersion.TLSv1_2) -> bool:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    try:
        with socket.create_connection((host, port), timeout=TIMEOUT) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as ssock:
                return ssock.version() >= min_version
    except Exception as e:
        logging.debug("TLS check failed %s:%d -> %s", host, port, e)
        return False

def check_port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=TIMEOUT):
            return True
    except Exception:
        return False

def check_tsn_driver_via_ssh(host: str, username: str, key_path: str, ifname: str = "eth0") -> bool:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        ssh.connect(hostname=host, username=username, key_filename=key_path, timeout=TIMEOUT)
        # ethtool -T or ethtool -k can reveal driver capability; read link/driver info as heuristic
        cmd = f"ethtool -i {ifname} || true"
        stdin, stdout, stderr = ssh.exec_command(cmd, timeout=TIMEOUT)
        out = stdout.read().decode()
        return "tsn" in out.lower() or "time" in out.lower()  # heuristic
    except Exception as e:
        logging.debug("SSH check failed %s -> %s", host, e)
        return False
    finally:
        ssh.close()

def scan_node(node: Dict) -> Dict:
    host = node["host"]
    res = {"host": host}
    res["tls_ok"] = check_tls_min_version(host, port=node.get("https_port", 443))
    res["mqtt_open"] = check_port_open(host, 1883)
    res["opcua_open"] = check_port_open(host, 4840)
    res["tsn_driver"] = check_tsn_driver_via_ssh(host, node["ssh_user"], node["ssh_key"])
    return res

def main(nodes):
    results = []
    with ThreadPoolExecutor(max_workers=32) as ex:
        futures = {ex.submit(scan_node, n): n for n in nodes}
        for fut in as_completed(futures):
            results.append(fut.result())
    for r in results:
        logging.info("Node %s compliance: %s", r["host"], r)
    return results

# Example invocation: supply nodes list with SSH creds in secure vault integration in production.