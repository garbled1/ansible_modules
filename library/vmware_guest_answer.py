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
module: vmware_guest_answer
short_description: Check for and answer questions blocking a guest
description:
- Check for questions that may be blocking a vm from operating
- Answer questions that may be blocking a vm from operating
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
  question:
    description:
    - A string matching the question to be answered
    required: True
  answer:
    description:
    - A string matching the answer you wish to provide to the virtual machine
    required: True
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
from ansible.module_utils.vmware import PyVmomi, vmware_argument_spec, wait_for_task


def answer_vm(vm, question, answer):
    task = None
    try:
        task = vm.AnswerVM(question, answer)
    except vim.fault.ConcurentAccess, vim.fault.RuntimeFault as ex:
        self.module_fail_json(msg="Failed to answer: %s" % to_native(ex.msg))
    except vim.fault.InvalidArgument:
        self.module.exit_json(changed=False, msg='Question already answered')
    except Exception as ex:
        self.module.fail_json(msg="Failed to answer due to %s" % to_native(ex.msg))

    result = dict()
    if task:
        try:
            tr, result = wait_for_task(task)
        except Exception as ex:
            self.module.fail_json(msg="Failed to answer due to %s" % to_native(ex.msg))

    return result


def main():
    argument_spec = vmware_argument_spec()
    argument_spec.update(
        name=dict(type='str'),
        name_match=dict(type='str', choices=['first', 'last'], default='first'),
        uuid=dict(type='str'),
        folder=dict(type='str', default='/vm'),
        question=dict(type='str', required=True),
        answer=dict(type='str', required=True),
    )

    module = AnsibleModule(argument_spec=argument_spec,
                           supports_check_mode=False,
                           mutually_exclusive=[
                               ['name', 'uuid'],
                           ],
                           )

    result = dict(changed=True,)

    pyv = PyVmomi(module)

    # Check if the VM exists before continuing
    vm = pyv.get_vm()

    if vm:
        # VM exists
        result['answer'] = answer_vm(vm=vm, question=module.params['question'], answer=module.params['answer'])
    else:
        module.fail_json(msg="Unable to answer non-existing virtual machine : '%s'" % (module.params.get('uuid') or module.params.get('name')))

    module.exit_json(**result)


if __name__ == '__main__':
    main()
