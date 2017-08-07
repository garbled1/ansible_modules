#!/usr/bin/python
# Copyright (c) 2017 Tim Rightnour <thegarbledone@gmail.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function
__metaclass__ = type

ANSIBLE_METADATA = {
    'metadata_version': '1.0',
    'status': ['preview'],
    'supported_by': 'community'
}

DOCUMENTATION = '''
---
module: snow_record

short_description: Create/Delete/Update records in ServiceNow

version_added: "2.4"

description:
    - Creates/Deletes/Updates a single record in ServiceNow

options:
    instance:
        description:
            - The service now instance name
        required: true
    username:
        description:
            - User to connect to ServiceNow as
        required: true
    password:
        description:
            - Password for username
        required: true
    table:
        description:
            - Table to query for records
        required: false
        default: incident
    state:
        description:
            - If C(present) or C(updated) is supplied with a C(number)
              argument, the module will attempt to update the record with
              the supplied data.  If no such record exists, a new one will
              be created.  C(absent) will delete a record.
        choices: [ present, absent, updated ]
        default: updated
        required: true
    data:
        description:
            - key, value pairs of data to load into the record.
              See Examples. Required for
              C(state:updated) or C(state:present)
    number:
        description:
            - Record number to update. Required for
              C(state:updated) or C(state:absent)
        required: false
    lookup_field:
        description:
            - Changes the field that C(number) uses to find records
        required: false
        default: number
    attachment:
        description:
            - Attach a file to the record
        required: false

requirements:
    - python pysnow (pysnow)

author:
    - Tim Rightnour (@garbled1)
'''

EXAMPLES = '''
- name: Create an incident
  snow_record:
    username: ansible_test
    password: my_password
    instance: dev99999
    state: present
    data:
      short_description: "This is a test incident opened by Ansible"
      severity: 3
      priority: 2
  register: new_incident

- name: Delete the record we just made
  snow_record:
    username: admin
    password: XXXXXXX
    instance: dev99999
    state: absent
    number: "{{new_incident['record']['number']}}"

- name: Update an incident
  snow_record:
    username: ansible_test
    password: my_password
    instance: dev99999
    state: updated
    number: INC0000055
    data:
      work_notes : "Been working all day on this thing."

'''

RETURN = '''
record:
   description: Record data from Service Now
   type: dict
'''

import os

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils._text import to_bytes, to_native

# Pull in pysnow
HAS_PYSNOW=False
try:
    import pysnow
    HAS_PYSNOW=True

except ImportError:
    pass


def run_module():
    # define the available arguments/parameters that a user can pass to
    # the module
    module_args = dict(
        instance=dict(default=None, type='str', required=True),
        username=dict(default=None, type='str', required=True, no_log=True),
        password=dict(default=None, type='str', required=True, no_log=True),
        table=dict(type='str', required=False, default='incident'),
        state=dict(choices=['updated', 'present', 'absent'],
                   type='str', required=True),
        number=dict(default=None, required=False, type='str'),
        data=dict(default=None, requried=False, type='dict'),
        lookup_field=dict(default='number', required=False, type='str'),
        attachment=dict(default=None, required=False, type='str')
    )
    module_required_if=[
        ['state', 'updated', ['number']],
        ['state', 'absent', ['number']],
    ]

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True,
        required_if=module_required_if
    )

    # check for pysnow
    if not HAS_PYSNOW:
        module.fail_json(msg='pysnow module required')

    params = module.params
    instance = params['instance']
    username = params['username']
    password = params['password']
    table=params['table']
    state=params['state']
    number=params['number']
    data=params['data']
    lookup_field=params['lookup_field']

    result = dict(
        changed=False,
        instance=instance,
        table=table,
        number=number,
        lookup_field=lookup_field
    )

    # check for attachments
    if params['attachment'] is not None:
        attach = params['attachment']
        b_attach = to_bytes(attach, errors='surrogate_or_strict')
        if not os.path.exists(b_attach):
            module.fail_json(msg="Attachment %s not found" % (attach))
        result['attachment'] = attach

    # Connect to ServiceNow
    try:
        conn = pysnow.Client(instance=instance, user=username,
                             password=password)
    except:
        module.fail_json(msg='Could not connect to ServiceNow', **result)

    # Deal with check mode
    if module.check_mode:

        # if we are in check mode and have no number, we would have created
        # a record.  We can only partially simulate this
        if number is None:
            result['record'] = dict(data)
            result['changed'] = True

        # do we want to check if the record is non-existent?
        elif state == 'absent':
            try:
                record = conn.query(table=table, query={lookup_field: number})
                res = record.get_one()
                result['record'] = dict(Success=True)
                result['changed'] = True
            except pysnow.exceptions.NoResults:
                result['record'] = None
            except:
                module.fail_json(msg="Unknown failure in query record",
                                 **result)

        # Let's simulate modification
        else:
            try:
                record = conn.query(table=table, query={lookup_field: number})
                res = record.get_one()
                for key, value in data.items():
                    res[key] = value
                    result['changed'] = True
                result['record'] = res
            except pysnow.exceptions.NoResults:
                snow_error = "Record does not exist"
                module.fail_json(msg=snow_error, **result)
            except:
                module.fail_json(msg="Unknown failure in query record",
                                 **result)
        module.exit_json(**result)


    # now for the real thing: (non-check mode)
        
    # are we creating a new record? 
    if state == 'present' and number is None:
        try:
            record = conn.insert(table=table, payload=dict(data))
        except pysnow.UnexpectedResponse as e:
            snow_error = "Failed to create record: %s, details: %s" % (e.error_summary, e.error_details)
            module.fail_json(msg=snow_error, **result)
        result['record'] = record
        result['changed'] = True

    # we are deleting a record
    elif state == 'absent':
        try:
            record = conn.query(table=table, query={lookup_field: number})
            res = record.delete()
        except pysnow.exceptions.NoResults:
            res = dict(Success=True)
        except pysnow.exceptions.MultipleResults:
            snow_error = "Multiple record match"
            module.fail_json(msg=snow_error, **result)
        except pysnow.UnexpectedResponse as e:
            snow_error = "Failed to delete record: %s, details: %s" % (e.error_summary, e.error_details)
            module.fail_json(msg=snow_error, **result)
        except:
            snow_error = "Failed to delete record"
            module.fail_json(msg=snow_error, **result)
        result['record'] = res
        result['changed'] = True

    # We want to update a record
    else:
        try:
            record = conn.query(table=table, query={lookup_field: number})
            if data is not None:
                res = record.update(dict(data))
                result['record'] = res
                result['changed'] = True
            else:
                res = record.get_one()
                result['record'] = res
            if attach is not None:
                res = record.attach(b_attach)
                result['changed'] = True

        except pysnow.exceptions.MultipleResults:
            snow_error = "Multiple record match"
            module.fail_json(msg=snow_error, **result)
        except pysnow.exceptions.NoResults:
            snow_error = "Record does not exist"
            module.fail_json(msg=snow_error, **result)
        except pysnow.UnexpectedResponse as e:
            snow_error = "Failed to update record: %s, details: %s" % (e.error_summary, e.error_details)
            module.fail_json(msg=snow_error, **result)
        except:
            snow_error = "Failed to update record"
            module.fail_json(msg=snow_error, **result)
        
    module.exit_json(**result)

def main():
    run_module()

if __name__ == '__main__':
    main()
