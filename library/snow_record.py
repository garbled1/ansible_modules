#!/usr/bin/python
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

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
        state=dict(choices=['updated', 'present', 'absent'],
                   type='str', required=True),
        number=dict(default=None, required=False, type='str'),
        data=dict(default=None, requried=False, type='dict'),
    )
    module_required_if = [
        [ 'state', 'updated', [ 'number', 'data' ] ],
        [ 'state', 'absent', [ 'number' ] ],
        [ 'state', 'present', [ 'data' ] ]
    ]
   
    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True,
        required_if=module_required_if
    )

    # check for pysnow
    if not HAS_PYSNOW:
        module.fail_json(msg='pysnow module required')

    result = dict(
        changed=False,
        instance=module.params['instance'],
        table=module.params['table'],
        state=module.params['state'],
        number=module.params['number'],
        data=module.params['data'],
    )

    # Connect to ServiceNow
    try:
        conn = pysnow.Client(instance=module.params['instance'],
                             user=module.params['username'],
                             password=module.params['password'])
    except:
        module.fail_json(msg='Could not connect to ServiceNow', **result)

    # are we creating a new record? 
    if module.params['state'] == 'present' and module.params['number'] is None:
        try:
            record = conn.insert(table=module.params['table'],
                                 payload=dict(module.params['data']))
        except pysnow.UnexpectedResponse as e:
            snow_error = "Failed to create record: %s, details: %s" % (e.error_summary, e.error_details)
            module.fail_json(msg=snow_error, **result)
        result['record'] = record

    # we are deleting a record
    elif module.params['state'] == 'absent':
        try:
            record = conn.query(table=module.params['table'],
                                query={'number' : module.params['number']})
            res = record.delete()
        except pysnow.exceptions.NoResults:
            snow_error = "Record does not exist"
            module.fail_json(msg=snow_error, **result)
        except pysnow.UnexpectedResponse as e:
            snow_error = "Failed to delete record: %s, details: %s" % (e.error_summary, e.error_details)
            module.fail_json(msg=snow_error, **result)
        except:
            snow_error = "Failed to delete record"
            module.fail_json(msg=snow_error, **result)
        result['record'] = res

    # We want to update a record
    else:
        try:
            record = conn.query(table=module.params['table'],
                                query={'number' : module.params['number']})
            res = record.update(dict(module.params['data']))
            result['record'] = res
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
