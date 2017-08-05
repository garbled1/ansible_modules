#!/usr/bin/python
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

ANSIBLE_METADATA = {
    'metadata_version': '1.0',
    'status': ['preview'],
    'supported_by': 'community'
}

DOCUMENTATION = '''
---
module: snow_get_record

short_description: Search records from ServiceNow

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
            - Table to query for records
        required: false
        default: incident
    query_field:
	description:
            - Field to query for records
        required: true
    query_string:
        description:
            - String to query in query_field
        required: true
    max_records:
        description:
            - Maximum number of records to return
        required: false
        default: 20
    order_by:
        description:
            - Field to sort the results on.  Can prefix with "-" or "+" to
              change decending or ascending sort order.
        default: "-created_on"
        required: false
    return_fields:
	description:
	    - Fields of the record to return in the json
        required: false
        default: all fields

author:
    - Tim Rightnour (@garbled1)
'''

EXAMPLES = '''
- name: Search for incident assigned to group, return specific fields
  snow_search_records:
    username: ansible_test
    password: my_password
    instance: dev99999
    table: incident
    query_field: assignment_group
    query_string: d625dccec0a8016700a222a0f7900d06
    return_fields:
      - number
      - opened_at

'''

RETURN = '''
    record:
	record: The full contents of the matching ServiceNow records
		as a list of records.
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
        query_field=dict(default=None, type='str', required=True),
        query_string=dict(default=None, type='str', required=True),
        max_records=dict(default=20, type='int', required=False),
        order_by=dict(default='-created_on', type='str', required=False),
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
        query_field=module.params['query_field'],
        query_string=module.params['query_string'],
        max_records=module.params['max_records'],
        return_fields=module.params['return_fields']
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
                            query={ module.params['query_field'] : module.params['query_string'] })
        if module.params['return_fields'] is not None:
            res = record.get_multiple(fields=module.params['return_fields'],
                                      limit=module.params['max_records'],
                                      order_by=[module.params['order_by']])
        else:
            res = record.get_multiple(limit=module.params['max_records'],
                                      order_by=[module.params['order_by']])
        result['record'] = list(res)
    except:
        module.fail_json(msg='Failed to find record', **result)

    module.exit_json(**result)

def main():
    run_module()

if __name__ == '__main__':
    main()
