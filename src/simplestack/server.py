# Copyright 2012 Locaweb.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License");
#    you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.
#
# @author: Francisco Freire, Locaweb.
# @author: Thiago Morello (morellon), Locaweb.
# @author: Willian Molinari (PotHix), Locaweb.

import os
import json
import time
import base64
import syslog
import ConfigParser

import bottle
from bottle import delete, put, get, post, redirect, run, debug
from bottle import abort, request, ServerAdapter, response, static_file

from gevent import monkey
monkey.patch_all()

syslog.openlog("simplestack", 0, syslog.LOG_DAEMON)
app = bottle.app()


@get('/:hypervisor/:host')
def pool_info(hypervisor, host):
    """
    ::

      GET /:hypervisor/:host

    Get pool information
    """
    response.content_type = "application/json"
    manager = create_manager(hypervisor, host)

    return json.dumps(manager.pool_info())


@get('/:hypervisor/:host/guests')
def pool_guests(hypervisor, host):
    """
    ::

      GET /:hypervisor/:host/guests

    Get guests for a given pool
    """
    response.content_type = "application/json"
    manager = create_manager(hypervisor, host)
    return json.dumps(manager.guest_list())


@post('/:hypervisor/:host/guests')
def guest_create(hypervisor, host):
    """
    ::

      POST /:hypervisor/:host/guests

    Create a new guest
    """
    response.content_type = "application/json"
    manager = create_manager(hypervisor, host)
    data = request.body.readline()
    if not data:
        abort(400, 'No data received')
    data = json.loads(data)
    guest = manager.guest_create(data)
    guest_url = "/%s/%s/guests/%s" % (hypervisor, host, guest["id"])
    response.set_header("Location", guest_url)
    return json.dumps(guest)


@get('/:hypervisor/:host/guests/:guest_id')
def guest_info(hypervisor, host, guest_id):
    """
    ::

      GET /:hypervisor/:host/guests/:guest_id

    Get guest informations
    """
    response.content_type = "application/json"
    manager = create_manager(hypervisor, host)
    return json.dumps(manager.guest_info(guest_id))


@put('/:hypervisor/:host/guests/:guest_id')
def guest_update(hypervisor, host, guest_id):
    """
    ::

      PUT /:hypervisor/:host

    Update guest informations
    """
    response.content_type = "application/json"
    manager = create_manager(hypervisor, host)
    data = request.body.readline()
    if not data:
        abort(400, 'No data received')
    data = json.loads(data)
    return json.dumps(manager.guest_update(guest_id, data))


@get('/:hypervisor/:host/guests/:guest_id/export')
def guest_export(hypervisor, host, guest_id):
    """
    ::

      GET /:hypervisor/:host/guests/:guest_id/export

    Export guest file
    """
    manager = create_manager(hypervisor, host)
    export_response, export_length = manager.guest_export(guest_id)
    response_part = export_response.read(1024)
    while response_part:
        yield response_part
        response_part = export_response.read(1024)


@delete('/:hypervisor/:host/guests/:guest_id')
def guest_delete(hypervisor, host, guest_id):
    """
    ::

      DELETE /:hypervisor/:host/guests/:guest_id

    Deletes guest
    """
    response.content_type = "application/json"
    manager = create_manager(hypervisor, host)
    return json.dumps(manager.guest_delete(guest_id))


@put('/:hypervisor/:host/guests/:guest_id/media_device')
def media_mount(hypervisor, host, guest_id):
    """
    ::

      PUT /:hypervisor/:host/guests/:guest_id/media_device

    Mounts an ISO to a CD/DVD drive

    Deletes guest
    """
    response.content_type = "application/json"
    manager = create_manager(hypervisor, host)
    data = request.body.readline()
    if not data:
        abort(400, 'No data received')
    data = json.loads(data)
    manager.media_mount(guest_id, data)


@get('/:hypervisor/:host/guests/:guest_id/media_device')
def media_info(hypervisor, host, guest_id):
    """
    ::

      GET /:hypervisor/:host/guests/:guest_id/media_device

    Gets the mounted media device name

    Deletes guest
    """
    response.content_type = "application/json"
    manager = create_manager(hypervisor, host)
    return json.dumps(manager.media_info(guest_id))


@get('/:hypervisor/:host/guests/:guest_id/network_interfaces')
def network_interface_list(hypervisor, host, guest_id):
    """
    ::

      GET /:hypervisor/:host/guests/:guest_id/network_interfaces

    Get all network interfaces for a given guest
    """
    response.content_type = "application/json"
    manager = create_manager(hypervisor, host)
    return json.dumps(manager.network_interface_list(guest_id))


@get('/:hypervisor/:host/guests/:guest_id/network_interfaces/:interface_id')
def network_interface_info(hypervisor, host, guest_id, interface_id):
    """
    ::

      GET /:hypervisor/:host/guests/:guest_id/network_interfaces/:interface_id

    Get a network interfaces in a given guest
    """
    response.content_type = "application/json"
    manager = create_manager(hypervisor, host)
    return json.dumps(manager.network_interface_info(guest_id))


@get('/:hypervisor/:host/guests/:guest_id/tags')
def tag_list(hypervisor, host, guest_id):
    """
    ::

      GET /:hypervisor/:host/guests/:guest_id/tags

    Get all tags for a given guest
    """
    response.content_type = "application/json"
    manager = create_manager(hypervisor, host)
    return json.dumps(manager.tag_list(guest_id))


@post('/:hypervisor/:host/guests/:guest_id/tags')
def tag_create(hypervisor, host, guest_id):
    """
    ::

      POST /:hypervisor/:host/guests/:guest_id/tags

    Create a new tag for a given guest
    """
    response.content_type = "application/json"
    manager = create_manager(hypervisor, host)
    data = request.body.readline()
    if not data:
        abort(400, 'No data received')
    data = json.loads(data)
    tag = manager.tag_create(guest_id, data.get('name'))
    #TODO: Should we return the Location for the first tag?
    tag_url = "/%s/%s/guests/%s/tags/%s" % (hypervisor, host, guest_id, tag[0])
    response.set_header("Location", tag_url)
    return json.dumps(tag)


@delete('/:hypervisor/:host/guests/:guest_id/tags/:tag_name')
def tag_delete(hypervisor, host, guest_id, tag_name):
    """
    ::

      DELETE /:hypervisor/:host/guests/:guest_id/tags

    Delete a given tag for a given guest
    """
    response.content_type = "application/json"
    manager = create_manager(hypervisor, host)
    return json.dumps(manager.tag_delete(guest_id, tag_name))


@get('/:hypervisor/:host/guests/:guest_id/snapshots')
def snapshot_list(hypervisor, host, guest_id):
    """
    ::

      GET /:hypervisor/:host/guests/:guest_id/snapshots

    Get all snapshots for a given guest
    """
    response.content_type = "application/json"
    manager = create_manager(hypervisor, host)
    return json.dumps(manager.snapshot_list(guest_id))


@post('/:hypervisor/:host/guests/:guest_id/snapshots')
def snapshot_create(hypervisor, host, guest_id):
    """
    ::

      POST /:hypervisor/:host/guests/:guest_id/snapshots

    Create a snapshot for a given guest
    """
    response.content_type = "application/json"
    manager = create_manager(hypervisor, host)
    data = request.body.readline()
    if not data:
        abort(400, 'No data received')
    data = json.loads(data)
    snapshot = manager.snapshot_create(guest_id, data.get('name'))
    snapshot_url = "/%s/%s/guests/%s/snapshots/%s" % (
        hypervisor, host, guest_id, snapshot["id"]
    )
    response.set_header("Location", snapshot_url)
    return json.dumps(snapshot)


@get('/:hypervisor/:host/guests/:guest_id/snapshots/:snapshot_id')
def snapshot_info(hypervisor, host, guest_id, snapshot_id):
    """
    ::

      GET /:hypervisor/:host/guests/:guest_id/snapshots/:snapshot_id

    Get snapshot informations for a given guest_id and snapshot_id
    """
    response.content_type = "application/json"
    manager = create_manager(hypervisor, host)
    return json.dumps(manager.snapshot_info(guest_id, snapshot_id))


@put('/:hypervisor/:host/guests/:guest_id/snapshots/:snapshot_id/revert')
def snapshot_revert(hypervisor, host, guest_id, snapshot_id):
    """
    ::

      PUT /:hypervisor/:host/guests/:guest_id/snapshots/:snapshot_id/revert

    Remove a snapshot for a given guest_id and snapshot_id
    """
    response.content_type = "application/json"
    manager = create_manager(hypervisor, host)
    return json.dumps(manager.snapshot_revert(guest_id, snapshot_id))


@delete('/:hypervisor/:host/guests/:guest_id/snapshots/:snapshot_id')
def snapshot_delete(hypervisor, host, guest_id, snapshot_id):
    """
    ::

      DELETE /:hypervisor/:host/guests/:guest_id/snapshots/:snapshot_id

    Remove a snapshot for a given guest_id and snapshot_id
    """
    response.content_type = "application/json"
    manager = create_manager(hypervisor, host)
    return json.dumps(manager.snapshot_delete(guest_id, snapshot_id))


@put('/:hypervisor/:host/guests/:guest_id/reboot')
def reboot_guest(hypervisor, host, guest_id):
    """
    ::

      PUT /:hypervisor/:host/guests/:guest_id/reboot

    Reboot a guest based on the given guest_id
    """
    response.content_type = "application/json"
    manager = create_manager(hypervisor, host)

    data = request.body.readline()
    force = False

    if data:
        data = json.loads(data)
        force = data.get('force')

    manager.guest_reboot(guest_id, force=force)

    return json.dumps({"action": "reboot", "message": "ok"})


@put('/:hypervisor/:host/guests/:guest_id/power')
def power_guest(hypervisor, host, guest_id):
    """
    ::

      PUT /:hypervisor/:host/guests/:guest_id/power

    Turn a guest on/off based on a given guest_id
    """
    response.content_type = "application/json"
    manager = create_manager(hypervisor, host)
    data = request.body.readline()
    if not data:
        abort(400, 'No data received')
    data = json.loads(data)
    state = data['state']
    if state == "force_stop":
        manager.guest_shutdown(guest_id, force=True)
    elif state == "start":
        manager.guest_start(guest_id)
    elif state == "stop":
        manager.guest_shutdown(guest_id, force=False)
    elif state == "pause":
        manager.guest_suspend(guest_id)
    elif state == "resume":
        manager.guest_resume(guest_id)
    return json.dumps({"action": state, "message": "ok"})


def parse_token(token):
    decoded_token = base64.b64decode(token).split(':')
    username = decoded_token.pop(0)
    password = ':'.join(decoded_token)
    return (username, password)


def create_manager(hypervisor, host):
    hypervisor_token = request.headers.get("x-simplestack-hypervisor-token")
    if not hypervisor_token:
        abort(401, 'No x-simplestack-hypervisor-token header provided')

    username, password = parse_token(hypervisor_token)

    module = __import__("simplestack.hypervisors.%s" % hypervisor)
    module = getattr(module.hypervisors, hypervisor)

    return module.Stack({
        "api_server": host,
        "username": username,
        "password": password
    })


def main():
    config = ConfigParser.ConfigParser()
    config_file = "/etc/simplestack.cfg"
    port = 8081
    bind_addr = "0.0.0.0"
    if os.path.isfile:
        config.read("/etc/simplestack.cfg")
        debug(config.getboolean("server", "debug"))
        port = config.getint("server", "port")
        bind_addr = config.get("server", "bind_addr")

    run(host=bind_addr, port=port, server="gevent")
