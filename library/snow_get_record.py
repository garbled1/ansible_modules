#!/usr/bin/python
# Copyright (c) 2017 Tim Rightnour <thegarbledone@gmail.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

ANSIBLE_METADATA = {
    'metadata_version': '1.0',
    'status': ['preview'],
    'supported_by': 'community'
}

DOCUMENTATION = '''
---
module: snow_get_record

short_description: Get a single record from ServiceNow

version_added: "2.4"

description:
    - Gets a single record of a specified type from ServiceNow denoted
      by number (record number)

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
            - Table to query for record
        required: false
        default: incident
    number:
	description:
            - Record number to find, ex: INC01234
        required: true
    return_fields:
	description:
	    - Fields of the record to return in the json
        required: false
        default: all fields

requirements:
    - python pysnow (pysnow)

author:
    - Tim Rightnour (@garbled1)
'''

EXAMPLES = '''
- name: Get an incident, return all fields
  snow_get_record:
    username: ansible_test
    password: my_password
    instance: dev99999
    number: INC0000055
    table: incident

'''

RETURN = '''
    record:
	record: The full contents of the ServiceNow record
        type: dict
'''

from ansible.module_utils.basic import AnsibleModule

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
        number=dict(default=None, type='str', required=True),
        return_fields=dict(default=None, type='list', required=False)
    )

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True
    )
    # check for pysnow
    if not HAS_PYSNOW:
        module.fail_json(msg='pysnow module required')

    result = dict(
        changed=False,
        instance=module.params['instance'],
        table=module.params['table'],
        number=module.params['number'],
    )

    # do the lookup
    try:
        conn = pysnow.Client(instance=module.params['instance'],
                             user=module.params['username'],
                             password=module.params['password'])
    except:
        module.fail_json(msg='Could not connect to ServiceNow', **result)

    try:
        record = conn.query(table=module.params['table'],
                            query={ 'number' : module.params['number'] })
        if module.params['return_fields'] is None:
            res = record.get_one()
        else:
            res = record.get_one(module.params['return_fields'])
        result['record'] = res
    except:
        module.fail_json(msg='Failed to find record', **result)

    module.exit_json(**result)

def main():
    run_module()

if __name__ == '__main__':
    main()
