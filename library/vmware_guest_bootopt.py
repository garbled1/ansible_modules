#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# Copyright: (c) 2017, Tim Rightnour (thegarbledone@gmail.com)
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function
__metaclass__ = type


ANSIBLE_METADATA = {'metadata_version': '1.1',
                    'status': ['preview'],
                    'supported_by': 'community'}

DOCUMENTATION = r'''
---
module: vmware_guest_screenshot
short_description: Takes a screenshot of a virtual machine
description:
- Take a screenshot from a virtual machine
version_added: '2.5'
author:
- Tim Rightnour (@garbled1) <thegarbledone@gmail.com>
requirements:
- python >= 2.6
- PyVmomi
options:
  name:
    description:
    - Name of the virtual machine to work with.
    - Virtual machine names in vCenter are not necessarily unique, which may be problematic, see C(name_match).
  name_match:
    description:
    - If multiple virtual machines matching the name, use the first or last found.
    default: first
    choices: [ first, last ]
  uuid:
    description:
    - UUID of the instance to manage if known, this is VMware's unique identifier.
    - This is required if name is not supplied.
  folder:
    description:
    - Destination folder, absolute or relative path to find an existing guest.
    - The folder should include the datacenter. ESX's datacenter is ha-datacenter
    - 'Examples:'
    - '   folder: /ha-datacenter/vm'
    - '   folder: ha-datacenter/vm'
    - '   folder: /datacenter1/vm'
    - '   folder: datacenter1/vm'
    - '   folder: /datacenter1/vm/folder1'
    - '   folder: datacenter1/vm/folder1'
    - '   folder: /folder1/datacenter1/vm'
    - '   folder: folder1/datacenter1/vm'
    - '   folder: /folder1/datacenter1/vm/folder2'
    - '   folder: vm/folder2'
    - '   folder: folder2'
    default: /vm
extends_documentation_fragment: vmware.documentation
'''

EXAMPLES = r'''
- name: Take a screenshot of a vm
  vmware_guest_screenshot:
    hostname: 192.0.2.44
    username: administrator@vsphere.local
    password: vmware
    validate_certs: no
    folder: /testvms
    name: testvm_2
  delegate_to: localhost
  register: screenshot
'''

RETURN = r''' # '''

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.vmware import PyVmomi, vim, vmware_argument_spec, wait_for_task


def get_boot_options_vm(vm):
    result = dict(changed=False,)

    if not vm.config.bootOptions:
        return None

    bootopts = vm.config.bootOptions

    result['bootopts']['bootdelay'] = bootopts.bootDelay
    result['bootopts']['bootorder'] = bootopts.bootOrder
    result['bootopts']['bootretrydelay'] = bootopts.bootRetryDelay
    result['bootopts']['bootretry'] = bootopts.bootRetryEnabled
    result['bootopts']['enterbios'] = bootopts.enterBIOSSetup

    return result


def compare_boot_options(vim, result, params):
    changed = 0
    configspec = vim.vm.ConfigSpec()


def build_hardware_map(vm, vim):
    devices = vm.config.hardware.device
    hwmap = dict()

    for dev in devices:
        if type(dev) is vim.vm.device.VirtualCdrom:
            dname = "cdrom"
        else:
            dname = dev.deviceInfo.label
        hwmap[dname] = {
            'label': dev.deviceInfo.label,
            'key': dev.key,
            'type': str(type(dev)),
        }
    return hwmap


def main():
    argument_spec = vmware_argument_spec()
    argument_spec.update(
        name=dict(type='str'),
        name_match=dict(type='str', choices=['first', 'last'], default='first'),
        uuid=dict(type='str'),
        folder=dict(type='str', default='/vm'),
        bootdelay=dict(type='int'),
        bootorder=dict(type='list'),
        bootretrydelay=dict(type='int'),
        bootretry=dict(type='bool'),
        enterbios=dict(type='bool'),
    )

    module = AnsibleModule(argument_spec=argument_spec,
                           supports_check_mode=False,
                           mutually_exclusive=[
                               ['name', 'uuid'],
                           ],
                           )


    pyv = PyVmomi(module)

    # Check if the VM exists before continuing
    vm = pyv.get_vm()
    
    if vm:
        result = build_hardware_map(vm, vim)
        #result = get_boot_options_vm(vm=vm)

        #changed, configspec = compare_boot_options(vim, result, module.params)



        
    else:
        module.fail_json(msg="Unable to set boot options on non-existing virtual machine : '%s'" % (module.params.get('uuid') or module.params.get('name')))

    module.exit_json(**result)


if __name__ == '__main__':
    main()
