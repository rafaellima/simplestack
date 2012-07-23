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

from simplestack.utils import XenAPI
from simplestack.exceptions import FeatureNotImplemented, EntityNotFound
from simplestack.hypervisors.base import SimpleStack
from simplestack.views.format_view import FormatView

import re
import httplib
import logging

LOG = logging.getLogger('simplestack.server')


class Stack(SimpleStack):

    state_translation = {
        "Running": "STARTED",
        "Halted": "STOPPED",
        "Suspended": "PAUSED"
    }

    def __init__(self, poolinfo):
        self.connection = False
        self.poolinfo = poolinfo
        self.format_for = FormatView()
        self.connect()

    def connect(self):
        self.connection = XenAPI.Session(
            "https://%s/" % self.poolinfo.get("api_server")
        )
        try:
            self.connection.xenapi.login_with_password(
                self.poolinfo.get("username"),
                self.poolinfo.get("password")
            )
        except Exception, error:
            # If host is slave, connect to master
            if 'HOST_IS_SLAVE' in str(error):
                self.connection = XenAPI.Session(
                    "https://%s/" % str(error).split("'")[3]
                )
                self.connection.xenapi.login_with_password(
                    self.poolinfo.get("username"),
                    self.poolinfo.get("password")
                )
            else:
                raise error
        return

    def pool_info(self):
        used_memory = 0
        for vm_rec in self.connection.xenapi.VM.get_all_records().values():
            if not vm_rec['is_a_template'] and not vm_rec['is_a_snapshot']:
                used_memory += int(vm_rec['memory_dynamic_max'])

        total_memory = 0
        for host_ref in self.connection.xenapi.host.get_all():
            met_ref = self.connection.xenapi.host.get_metrics(host_ref)
            m_rec = self.connection.xenapi.host_metrics.get_record(met_ref)
            total_memory += int(m_rec['memory_total'])

        pool_rec = self.connection.xenapi.pool.get_all_records().values()[0]
        master_rec = self.connection.xenapi.host.get_record(pool_rec["master"])

        return (
            self.format_for.pool(
                used_memory / (1024 * 1024),
                total_memory / (1024 * 1024),
                master_rec["address"]
            )
        )

    def guest_list(self):
        guests = []
        for vm in self.connection.xenapi.VM.get_all_records().values():
            if (not vm.get('is_a_snapshot')) and (not vm.get('is_a_template')):
                guests.append({'id': vm.get('uuid')})

        return guests

    def guest_info(self, guest_id):
        vm = self._vm_ref(guest_id)
        return self._vm_info(vm)

    def guest_shutdown(self, guest_id, force=False):
        if force:
            return self.connection.xenapi.VM.hard_shutdown(
                self._vm_ref(guest_id)
            )
        else:
            return self.connection.xenapi.VM.clean_shutdown(
                self._vm_ref(guest_id)
            )

    def guest_start(self, guest_id):
        return self.connection.xenapi.VM.start(
            self._vm_ref(guest_id), False, False
        )

    def guest_reboot(self, guest_id, force=False):
        vm_ref = self._vm_ref(guest_id)
        if force:
            return self.connection.xenapi.VM.hard_reboot(vm_ref)
        else:
            return self.connection.xenapi.VM.clean_reboot(vm_ref)

    def guest_suspend(self, guest_id):
        return self.connection.xenapi.VM.suspend(self._vm_ref(guest_id))

    def guest_resume(self, guest_id):
        return self.connection.xenapi.VM.resume(
            self._vm_ref(guest_id), False, False
        )

    def guest_update(self, guest_id, guestdata):
        vm_ref = self._vm_ref(guest_id)
        if guestdata.get("name"):
            self.connection.xenapi.VM.set_name_label(vm_ref, guestdata["name"])
        if guestdata.get("memory"):
            memory = str(int(guestdata["memory"]) * 1024 * 1024)
            self.connection.xenapi.VM.set_memory_limits(
                vm_ref, memory, memory, memory, memory
            )
        if guestdata.get("cpus"):
            max_cpus = self.connection.xenapi.VM.get_VCPUs_max(vm_ref)
            cpus = str(guestdata["cpus"])
            if int(cpus) > int(max_cpus):
                self.connection.xenapi.VM.set_VCPUs_max(vm_ref, cpus)
                self.connection.xenapi.VM.set_VCPUs_at_startup(vm_ref, cpus)
            else:
                self.connection.xenapi.VM.set_VCPUs_at_startup(vm_ref, cpus)
                self.connection.xenapi.VM.set_VCPUs_max(vm_ref, cpus)
        if guestdata.get("vcpu_settings"):
            parameters = self.connection.xenapi.VM.get_VCPUs_params(vm_ref)
            parameters.update(guestdata["vcpu_settings"])
            self.connection.xenapi.VM.set_VCPUs_params(vm_ref, parameters)
        if guestdata.get("ha_enabled") != None:
            if guestdata["ha_enabled"]:
                self.connection.xenapi.VM.set_ha_restart_priority(
                    vm_ref, "best-effort"
                )
            else:
                self.connection.xenapi.VM.set_ha_restart_priority(vm_ref, "")
        if guestdata.get("template") != None:
            self.connection.xenapi.VM.set_is_a_template(
                vm_ref, guestdata["template"]
            )
        if guestdata.get("hdd"):
            disk = self.get_disks(vm_ref)[-1]
            disks_size = self.get_disks_size(vm_ref)
            hdd = guestdata.get("hdd") * 1024 * 1024 * 1024
            new_disk_size = hdd - disks_size + int(disk["virtual_size"])
            self.connection.xenapi.VDI.resize(disk["ref"], str(new_disk_size))

        return self._vm_info(self._vm_ref(guest_id))

    def guest_delete(self, guest_id):
        self._delete_vm(guest_id)

    def guest_import(self, vm_stream, vm_size):
        session_ref = self.connection._session
        # FIXME: get real master
        master = self.poolinfo.get("api_server")
        task_ref = self.connection.xenapi.task.create(
            "import vm", "import job"
        )
        path = "/import?session_id=%s&task_id=%s" % (
            session_ref, task_ref
        )

        conn = httplib.HTTPConnection(master)
        conn.request(
            "PUT", path, vm_stream, {"Content-Length": vm_size}
        )
        response = conn.getresponse()
        response.status
        response.read()

        task_rec = self.connection.xenapi.task.get_record(task_ref)
        vm_ref = re.sub(r'<.*?>', "", task_rec["result"])
        return self._vm_info(self._vm_ref(guest_id))

    def guest_export(self, guest_id):
        vm_ref = self._vm_ref(guest_id)
        session_ref = self.connection._session
        # FIXME: get real master
        master = self.poolinfo.get("api_server")
        task_ref = self.connection.xenapi.task.create(
            "export vm %s" % guest_id, "export job"
        )
        path = "/export?session_id=%s&task_id=%s&ref=%s" % (
            session_ref, task_ref, vm_ref
        )
        conn = httplib.HTTPConnection(master)
        conn.request("GET", path)
        response = conn.getresponse()
        response_size = response.getheader("Content-Length")

        return (response, response_size)

    def disk_list(self, guest_id):
        vm_ref = self._vm_ref(guest_id)
        disks = self.get_disks(vm_ref)
        return [self._disk_info(d) for d in disks]

    def disk_create(self, guest_id, data):
        vm_ref = self._vm_ref(guest_id)

        devices = []
        for vbd in self.connection.xenapi.VM.get_VBDs(vm_ref):
            devices.append(int(self.connection.xenapi.VBD.get_userdevice(vbd)))
        next_device = max(devices) + 1
        for device in range(next_device):
            if device not in devices:
                next_device = device
                break

        vbd_rec = {
            "VM": vm_ref,
            "userdevice": str(next_device),
            "bootable": False,
            "mode": "RW",
            "type": "Disk",
            "unpluggable": False,
            "empty": False,
            "other_config": {},
            "qos_algorithm_type": "",
            "qos_algorithm_params": {}
        }

        vdi_rec = ({
            "virtual_size": str(data["size"] * 1024 * 1024 * 1024),
            "type": "system",
            "sharable": False,
            "read_only": False,
            "other_config": {},
            "xenstore_data": {},
            "sm_config": {},
            "tags": []
        })

        if data.get("storage_id"):
            raise FeatureNotImplemented()
        else:
            disks = self.get_disks(vm_ref)
            vdi_rec["SR"] = disks[0]["SR"]

        if data.get("name"):
            vdi_rec["name_label"] = data["name"]
            vdi_rec["name_description"] = data["name"]

        vdi_ref = self.connection.xenapi.VDI.create(vdi_rec)
        vbd_rec["VDI"] = vdi_ref
        self.connection.xenapi.VBD.create(vbd_rec)

        disk_rec = self._disk_rec(vm_ref, next_device)
        return self._disk_info(disk_rec)


    def disk_info(self, guest_id, disk_id):
        vm_ref = self._vm_ref(guest_id)
        disk_rec = self._disk_rec(vm_ref, disk_id)
        return self._disk_info(disk_rec)

    def disk_update(self, guest_id, disk_id, data):
        vm_ref = self._vm_ref(guest_id)
        disk_rec = self._disk_rec(vm_ref, disk_id)

        if data.get("name"):
            self.connection.xenapi.VDI.set_name_label(
                disk_rec["ref"], data["name"]
            )
            self.connection.xenapi.VDI.set_name_description(
                disk_rec["ref"], data["name"]
            )

        disk_rec = self._disk_rec(vm_ref, disk_id)
        return self._disk_info(disk_rec)

    def media_mount(self, guest_id, media_data):
        vm_ref = self._vm_ref(guest_id)
        cd_ref = self._cd_ref(vm_ref)
        if media_data.get("name") and media_data["name"] != "":
            self.media_unmount(guest_id)
            iso_ref = self.connection.xenapi.VDI.get_by_name_label(
                media_data["name"]
            )[0]
            self.connection.xenapi.VBD.set_bootable(
                cd_ref, media_data.get("bootable") == True
            )
            self.connection.xenapi.VBD.insert(cd_ref, iso_ref)
        else:
            self.media_unmount(guest_id)

    def media_unmount(self, guest_id):
        vm_ref = self._vm_ref(guest_id)
        cd_ref = self._cd_ref(vm_ref)
        null_ref = 'OpaqueRef:NULL'
        if self.connection.xenapi.VBD.get_record(cd_ref)["VDI"] != null_ref:
            self.connection.xenapi.VBD.eject(cd_ref)

    def media_info(self, guest_id):
        vm_ref = self._vm_ref(guest_id)
        cd_ref = self._cd_ref(vm_ref)
        iso_ref = self.connection.xenapi.VBD.get_record(cd_ref)["VDI"]

        if iso_ref == 'OpaqueRef:NULL':
            return {"name": None}
        else:
            name = self.connection.xenapi.VDI.get_record(iso_ref)["name_label"]
            return {"name": name}

    def network_interface_list(self, guest_id):
        vm_ref = self._vm_ref(guest_id)
        vif_refs = self.connection.xenapi.VM.get_VIFs(vm_ref)
        return [self._network_interface_info(n) for n in vif_refs]

    def network_interface_create(self, guest_id, data):
        vm_ref = self._vm_ref(guest_id)

        devices = []
        for vif in self.connection.xenapi.VM.get_VIFs(vm_ref):
            devices.append(int(self.connection.xenapi.VIF.get_device(vif)))
        next_device = max(devices) + 1
        for device in range(next_device):
            if device not in devices:
                next_device = device
                break

        vif_record = {
          "VM": vm_ref,
          "device": str(next_device),
          "MAC_autogenerated": True,
          "MAC": "",
          "MTU": "0",
          "other_config": {},
          "qos_algorithm_type": "",
          "qos_algorithm_params": {}
        }

        if data.get("network"):
            net_refs = self.connection.xenapi.network.\
                                    get_by_name_label(data["network"])
            if len(net_refs) == 0:
                raise Exception("Unknown network: %s" % data["network"])
            vif_record["network"] = net_refs[0]

        vif_ref = self.connection.xenapi.VIF.create(vif_record)
        return self._network_interface_info(vif_ref)

    def network_interface_info(self, guest_id, network_interface_id):
        vm_ref = self._vm_ref(guest_id)
        vif_ref = self._network_interface_ref(vm_ref, network_interface_id)
        return self._network_interface_info(vif_ref)

    def network_interface_update(self, guest_id, network_interface_id, data):
        vm_ref = self._vm_ref(guest_id)
        vif_ref = self._network_interface_ref(vm_ref, network_interface_id)
        vif_record = self.connection.xenapi.VIF.get_record(vif_ref)

        if data.get("network"):
            vif_record["network"] = self.connection.xenapi.pool\
                                    .network_by_name_label(data["network"])
        self.connection.xenapi.VIF.destroy(vif_ref)
        vif_ref = self.connection.xenapi.VIF.create(vif_record)
        return self._network_interface_info(vif_ref)

    def network_interface_delete(self, guest_id, network_interface_id):
        vm_ref = self._vm_ref(guest_id)
        vif_ref = self._network_interface_ref(vm_ref, network_interface_id)
        try:
            self.connection.xenapi.VIF.unplug(vif_ref)
        except:
            pass
        self.connection.xenapi.VIF.destroy(vif_ref)

    def snapshot_list(self, guest_id):
        snaps = [
            self._snapshot_info(s)
            for s in self.connection.xenapi.VM.get_snapshots(
                self._vm_ref(guest_id)
            )
        ]
        return snaps

    def snapshot_create(self, guest_id, snapshot_name=None):
        if not snapshot_name:
            snapshot_name = str(datetime.datetime.now())
        snap = self.connection.xenapi.VM.snapshot(
            self._vm_ref(guest_id), snapshot_name
        )
        return self._snapshot_info(snap)

    def snapshot_info(self, guest_id, snapshot_id):
        snap = self._vm_ref(snapshot_id)
        return self._snapshot_info(snap)

    def snapshot_revert(self, guest_id, snapshot_id):
        self.connection.xenapi.VM.revert(self._vm_ref(snapshot_id))

    def snapshot_delete(self, guest_id, snapshot_id):
        self._delete_vm(snapshot_id)

    def tag_list(self, guest_id):
        return self.connection.xenapi.VM.get_tags(self._vm_ref(guest_id))

    def tag_create(self, guest_id, tag_name):
        vm_ref = self._vm_ref(guest_id)
        self.connection.xenapi.VM.add_tags(vm_ref, tag_name)
        return self.tag_list(guest_id)

    def tag_delete(self, guest_id, tag_name):
        vm_ref = self._vm_ref(guest_id)
        self.connection.xenapi.VM.remove_tags(vm_ref, tag_name)

    def get_disks(self, vm_ref):
        disks = []
        vm = self.connection.xenapi.VM.get_record(vm_ref)
        for vbd_ref in vm['VBDs']:
            vbd = self.connection.xenapi.VBD.get_record(vbd_ref)
            if vbd["type"] == "Disk":
                vdi = self.connection.xenapi.VDI.get_record(vbd['VDI'])
                vdi['userdevice'] = vbd['userdevice']
                vdi['ref'] = vbd['VDI']
                disks.append(vdi)
        return sorted(disks, key=lambda vdi: int(vdi['userdevice']))

    def get_disks_size(self, vm_ref):
        size = 0
        for vdi in self.get_disks(vm_ref):
            size += int(vdi["virtual_size"])
        return size

    def _disk_rec(self, vm_ref, disk_id):
        disk_id = str(disk_id)
        for disk in self.get_disks(vm_ref):
            if disk["userdevice"] == disk_id:
                return disk

        entity_info = "%s - on Guest" % (disk_id)
        raise EntityNotFound("Disk", entity_info)

    def _network_interface_ref(self, vm_ref, network_interface_id):
        vif_refs = self.connection.xenapi.VM.get_VIFs(vm_ref)

        for vif_ref in vif_refs:
            vif_rec = self.connection.xenapi.VIF.get_record(vif_ref)
            if vif_rec["MAC"] == network_interface_id:
                return vif_ref

        entity_info = "%s - on Guest" % (network_interface_id)
        raise EntityNotFound("NetworkInterface", entity_info)

    def _vm_ref(self, uuid):
        try:
            return self.connection.xenapi.VM.get_by_uuid(uuid)
        except:
            LOG.warning("uuid=%s action=not_found" % uuid)
            return None

    def _vm_info(self, vm_ref):
        vm = self.connection.xenapi.VM.get_record(vm_ref)

        tools_up_to_date = None
        if vm["guest_metrics"] != "OpaqueRef:NULL":
            tools_up_to_date = self.connection.xenapi.VM_guest_metrics.get_PV_drivers_up_to_date(vm["guest_metrics"])

        return(
            self.format_for.guest(
                vm.get('uuid'),
                vm.get('name_label'),
                int(vm.get('VCPUs_at_startup')),
                int(vm.get('memory_static_max')) / (1024 * 1024),
                self.get_disks_size(vm_ref) / (1024 * 1024 * 1024),
                tools_up_to_date,
                self.state_translation[vm.get('power_state')]
            )
        )

    def _disk_info(self, disk_rec):
        return(
            self.format_for.disk(
                disk_rec.get('userdevice'),
                disk_rec.get('name_label'),
                disk_rec.get('userdevice'),
                int(disk_rec.get('virtual_size')) / (1024 * 1024 * 1024),
                disk_rec.get("uuid")
            )
        )

    def _snapshot_info(self, snapshot_ref):
        snapshot = self.connection.xenapi.VM.get_record(snapshot_ref)

        return(
            self.format_for.snapshot(
                snapshot.get('uuid'),
                snapshot.get('name_label')
            )
        )

    def _network_interface_info(self, vif_ref):
        vif_rec = self.connection.xenapi.VIF.get_record(vif_ref)
        network_rec = self.connection.xenapi.network.get_record(
            vif_rec["network"]
        )

        return(
            self.format_for.network_interface(
                vif_rec["MAC"],
                vif_rec["device"],
                vif_rec["MAC"],
                network_rec["name_label"]
            )
        )

    def _delete_vm(self, vm_id):
        vm_ref = self._vm_ref(vm_id)

        if not vm_ref:
            return

        for snap_ref in self.connection.xenapi.VM.get_snapshots(vm_ref):
            snap = self.connection.xenapi.VM.get_record(snap_ref)
            self._delete_vm(snap["uuid"])
        self._delete_disks(vm_ref)
        self.connection.xenapi.VM.destroy(vm_ref)

    def _cd_ref(self, vm_ref):
        vm = self.connection.xenapi.VM.get_record(vm_ref)
        for vbd_ref in vm['VBDs']:
            vbd = self.connection.xenapi.VBD.get_record(vbd_ref)
            if vbd["type"] == "CD":
                return vbd_ref

    def _delete_disks(self, vm_ref):
        for vdi in self.get_disks(vm_ref):
            self.connection.xenapi.VDI.destroy(vdi['ref'])
