#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2022 Håvard Moen <post@haavard.name>
#
# SPDX-License-Identifier: GPL-3.0-or-later

import argparse
from functools import cache
import json
from os import environ
import subprocess
import sys
from tempfile import NamedTemporaryFile

import requests


def boundary_authenticate(session):
    resp = session.get(f"{environ['BOUNDARY_ADDR']}/v1/auth-methods?scope_id=global")
    resp.raise_for_status()
    for item in resp.json()["items"]:
        if item["is_primary"]:
            try:
                subprocess.run(
                    [
                        "boundary",
                        "authenticate",
                        item["type"],
                        f"-auth-method-id={item['id']}",
                    ],
                    check=True,
                    stderr=subprocess.PIPE,
                )
                break
            except subprocess.CalledProcessError as e:
                raise Exception(f"Unable to authenticate: {e.stderr.read()}")
    else:
        raise Exception("Unable to authenticate, no auth methods found")


def boundary_get_auth_token(session):
    ret = subprocess.run(
        ["boundary", "config", "get-token"],
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if not ret.returncode == 0:
        boundary_authenticate(session)
    session.headers.update({"Authorization": f"Bearer {ret.stdout.strip()}"})


@cache
def boundary_get_host(session, host_id):
    resp = session.get(
        f"{environ['BOUNDARY_ADDR']}/v1/hosts/{host_id}",
    )
    if resp.status_code in (401, 403):
        boundary_authenticate(session)
        boundary_get_auth_token(session)
        return boundary_get_host(session, host_id)
    elif not resp.ok:
        raise Exception(f"Error getting host from boundary: {resp.text}")
    return resp.json()


@cache
def boundary_get_hosts(session, host_set_id):
    resp = session.get(
        f"{environ['BOUNDARY_ADDR']}/v1/host-sets/{host_set_id}",
    )
    if resp.status_code in (401, 403):
        boundary_authenticate(session)
        boundary_get_auth_token(session)
        return boundary_get_hosts(session, host_set_id)
    elif not resp.ok:
        raise Exception(f"Error getting host set from boundary: {resp.text}")
    return [
        boundary_get_host(session, host_id)
        for host_id in resp.json().get("host_ids", [])
    ]


def boundary_get_host_and_target(session, hostname, target):
    resp = session.get(
        f"{environ['BOUNDARY_ADDR']}/v1/targets",
        params={
            "scope_id": "global",
            "recursive": "true",
        },
    )
    if resp.status_code in (401, 403):
        boundary_authenticate(session)
        boundary_get_auth_token(session)
        return boundary_get_host_and_target(session, hostname)
    elif not resp.ok:
        raise Exception(f"Error getting targets from boundary: {resp.text}")
    for item in resp.json()["items"]:
        if not item["name"] == target:
            continue
        target = boundary_get_target(session, item["id"])
        for host_source in target["host_sources"]:
            hosts = boundary_get_hosts(session, host_source["id"])
            for host in hosts:
                if host["name"] == hostname:
                    return (host["id"], target["id"])
    return (None, None)


def boundary_get_target(session, target_id):
    resp = session.get(
        f"{environ['BOUNDARY_ADDR']}/v1/targets/{target_id}",
    )
    if resp.status_code in (401, 403):
        boundary_authenticate(session)
        boundary_get_auth_token(session)
        return boundary_get_target(session, target_id)
    elif not resp.ok:
        raise Exception(f"Error getting target from boundary: {resp.text}")
    return resp.json()


def boundary_proxy_command():
    parser = argparse.ArgumentParser(description="boundary proxy command")
    parser.add_argument("--hostname", required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument(
        "--listen_port",
        required=False,
        help="optional port for boundary connect to listen to",
        type=int,
    )
    parser.add_argument("command", nargs="+")
    args = parser.parse_args()

    session = requests.Session()
    session.headers.update(
        {"Accept": "applicaton/json", "Content-Type": "application/json"}
    )
    session.verify = True
    boundary_get_auth_token(session)
    host_id, target_id = boundary_get_host_and_target(
        session, args.hostname, args.target
    )
    if target_id is None or host_id is None:
        raise Exception(f"Could not find host {args.hostname} or target {args.target}")
    boundary_args = [
        "boundary",
        "connect",
        f"-target-id={target_id}",
        f"-host-id={host_id}",
        "-format",
        "json",
    ]
    if args.listen_port is not None:
        boundary_args.append(f"--listen-port={args.listen_port}")
    with subprocess.Popen(
        boundary_args, stdout=subprocess.PIPE
    ) as boundary_connect_proc:
        connect_params = json.loads(boundary_connect_proc.stdout.readline())
        tmp_hosts = create_temp_hostfile(args.hostname)
        wrapper_script = []
        wrapper_script.append(f'mount --bind "{tmp_hosts.name}" /etc/hosts')
        wrapper_script.append(f"export BOUNDARY_LISTEN_PORT={connect_params['port']}")
        wrapper_script.append(" ".join(args.command))

        with subprocess.Popen(
            ["unshare", "-mr", "/bin/sh", "-c", "\n".join(wrapper_script)],
            pass_fds=set([0, 1, 2]),
        ) as cmd:
            cmd.wait()

        boundary_connect_proc.terminate()


def create_temp_hostfile(hostname):
    tmp_hosts = NamedTemporaryFile(mode="w")

    with open("/etc/hosts", "r") as hosts:
        for line in hosts:
            if not hostname in line:
                tmp_hosts.write(line)

    tmp_hosts.write(f"127.0.0.1 {hostname}\n")
    tmp_hosts.flush()

    return tmp_hosts


if __name__ == "__main__":
    try:
        boundary_proxy_command()
    except Exception as e:
        sys.stderr.write(f"Error connecting: {e}")
