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

from simplestack.exceptions import FeatureNotImplemented


class SimpleStack(object):

    def __init__(self):
        self.connection = False

    def connect(self):
        raise FeatureNotImplemented()

    def pool_info(self):
        raise FeatureNotImplemented()

    def guest_list(self):
        raise FeatureNotImplemented()

    def guest_create(self, guestdata):
        raise FeatureNotImplemented()

    def guest_info(self, guest_id):
        raise FeatureNotImplemented()

    def guest_shutdown(self, guest_id, force=False):
        raise FeatureNotImplemented()

    def guest_start(self, guest_id):
        raise FeatureNotImplemented()

    def guest_suspend(self, guest_id):
        raise FeatureNotImplemented()

    def guest_resume(self, guest_id):
        raise FeatureNotImplemented()

    def guest_reboot(self, guest_id):
        raise FeatureNotImplemented()

    def guest_update(self, guest_id, guestdata):
        raise FeatureNotImplemented()

    def guest_delete(self, guest_id):
        raise FeatureNotImplemented()

    def media_mount(self, guest_id, media_data):
        raise FeatureNotImplemented()

    def media_info(self, guest_id):
        raise FeatureNotImplemented()

    def network_interface_list(self, guest_id):
        raise FeatureNotImplemented()

    def network_interface_info(self, guest_id, network_interface_id):
        raise FeatureNotImplemented()

    def snapshot_list(self, guest_id):
        raise FeatureNotImplemented()

    def snapshot_create(self, guestname, name=None):
        raise FeatureNotImplemented()

    def snapshot_info(self, guestname, snapshot_name):
        raise FeatureNotImplemented()

    def snapshot_delete(self, guest_id, snapshot_id):
        raise FeatureNotImplemented()

    def snapshot_revert(self, guest_id, snapshot_id):
        raise FeatureNotImplemented()

    def tag_list(self, guest_id):
        raise FeatureNotImplemented()

    def tag_create(self, guest_id, tag_name):
        raise FeatureNotImplemented()

    def tag_delete(self, guest_id, tag_name):
        raise FeatureNotImplemented()
