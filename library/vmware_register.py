#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# This module is also sponsored by E.T.A.I. (www.etai.fr)
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function
__metaclass__ = type


ANSIBLE_METADATA = {'metadata_version': '1.1',
                    'status': ['preview'],
                    'supported_by': 'community'}

import time

HAS_PYVMOMI = False
try:
    import pyVmomi
    from pyVmomi import vim

    HAS_PYVMOMI = True
except ImportError:
    pass

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils._text import to_text
# from ansible.module_utils.vmware import (connect_to_api, gather_vm_facts, get_all_objs,
#                                          compile_folder_path_for_object, serialize_spec,
#                                          find_vm_by_id, vmware_argument_spec)
from ansible.module_utils.vmware import (connect_to_api, gather_vm_facts, get_all_objs,
                                         find_vm_by_name, vmware_argument_spec, wait_for_task)


def find_obj(content, vimtype, name, first=True):
    container = content.viewManager.CreateContainerView(container=content.rootFolder, recursive=True, type=vimtype)
    obj_list = container.view
    container.Destroy()

    # Backward compatible with former get_obj() function
    if name is None:
        if obj_list:
            return obj_list[0]
        return None

    # Select the first match
    if first is True:
        for obj in obj_list:
            if obj.name == name:
                return obj

        # If no object found, return None
        return None

    # Return all matching objects if needed
    return [obj for obj in obj_list if obj.name == name]


class PyVmomiCache(object):
    """ This class caches references to objects which are requested multiples times but not modified """
    def __init__(self, content, dc_name=None):
        self.content = content
        self.dc_name = dc_name
        self.networks = {}
        self.clusters = {}
        self.esx_hosts = {}
        self.parent_datacenters = {}

    def find_obj(self, content, types, name, confine_to_datacenter=True):
        """ Wrapper around find_obj to set datacenter context """
        result = find_obj(content, types, name)
        if result and confine_to_datacenter:
            if self.get_parent_datacenter(result).name != self.dc_name:
                result = None
                objects = self.get_all_objs(content, types, confine_to_datacenter=True)
                for obj in objects:
                    if name is None or obj.name == name:
                        return obj
        return result

    def get_all_objs(self, content, types, confine_to_datacenter=True):
        """ Wrapper around get_all_objs to set datacenter context """
        objects = get_all_objs(content, types)
        if confine_to_datacenter:
            if hasattr(objects, 'items'):
                # resource pools come back as a dictionary
                for k, v in objects.items():
                    parent_dc = self.get_parent_datacenter(k)
                    if parent_dc.name != self.dc_name:
                        objects.pop(k, None)
            else:
                # everything else should be a list
                objects = [x for x in objects if self.get_parent_datacenter(x).name == self.dc_name]

        return objects

    def get_cluster(self, cluster):
        if cluster not in self.clusters:
            self.clusters[cluster] = self.find_obj(self.content, [vim.ClusterComputeResource], cluster)

        return self.clusters[cluster]

    def get_esx_host(self, host):
        if host not in self.esx_hosts:
            self.esx_hosts[host] = self.find_obj(self.content, [vim.HostSystem], host)

        return self.esx_hosts[host]

    def get_parent_datacenter(self, obj):
        """ Walk the parent tree to find the objects datacenter """
        if isinstance(obj, vim.Datacenter):
            return obj
        if obj in self.parent_datacenters:
            return self.parent_datacenters[obj]
        datacenter = None
        while True:
            if not hasattr(obj, 'parent'):
                break
            obj = obj.parent
            if isinstance(obj, vim.Datacenter):
                datacenter = obj
                break
        self.parent_datacenters[obj] = datacenter
        return datacenter


class PyVmomiHelper(object):
    def __init__(self, module):
        if not HAS_PYVMOMI:
            module.fail_json(msg='pyvmomi module required')

        self.module = module
        self.params = module.params
        self.si = None
        self.content = connect_to_api(self.module)
        self.configspec = None
        self.change_detected = False
        self.customspec = None
        self.current_vm_obj = None
        self.cache = PyVmomiCache(self.content, dc_name=self.params['datacenter'])

    def getvm(self, name=None, folder=None):
        vm = None
        vm = find_vm_by_name(self.content, vm_name=name, folder=folder)
        if vm:
            self.current_vm_obj = vm

        return vm

    def select_host(self, datastore_name):
        # given a datastore, find an attached host (just pick the first one)
        datastore = self.cache.find_obj(self.content, [vim.Datastore], datastore_name)
        for host_mount in datastore.host:
            return host_mount.key


    """  DELETEME!!! """
    def compile_folder_path_for_object(self, vobj):
        """ make a /vm/foo/bar/baz like folder path for an object """

        paths = []
        if isinstance(vobj, vim.Folder):
            paths.append(vobj.name)

        thisobj = vobj
        while hasattr(thisobj, 'parent'):
            thisobj = thisobj.parent
            if isinstance(thisobj, vim.Folder):
                paths.append(thisobj.name)
        paths.reverse()
        if paths[0] == 'Datacenters':
            paths.remove('Datacenters')
        return '/' + '/'.join(paths)

    def fobj_from_folder_path(self, dc, folder):
        datacenter = self.cache.find_obj(self.content, [vim.Datacenter], dc)
        if datacenter is None:
            self.module.fail_json(msg='No datacenter named %s was found' % dc)
        # Prepend / if it was missing from the folder path, also strip trailing slashes
        if not folder.startswith('/'):
            folder = '/%s' % folder
        folder = folder.rstrip('/')

        dcpath = self.compile_folder_path_for_object(datacenter)

        # Check for full path first in case it was already supplied
        if (folder.startswith(dcpath + dc + '/vm')):
            fullpath = folder
        elif (folder.startswith('/vm/') or folder == '/vm'):
            fullpath = "%s%s%s" % (dcpath, dc, folder)
        elif (folder.startswith('/')):
            fullpath = "%s%s/vm%s" % (dcpath, dc, folder)
        else:
            fullpath = "%s%s/vm/%s" % (dcpath, dc, folder)

        f_obj = self.content.searchIndex.FindByInventoryPath(fullpath)
        return f_obj

    def select_resource_pool_by_name(self, resource_pool_name):
        resource_pool = self.cache.find_obj(self.content, [vim.ResourcePool], resource_pool_name)
        if resource_pool is None:
            self.module.fail_json(msg='Could not find resource_pool "%s"' % resource_pool_name)
        return resource_pool

    def select_resource_pool_by_host(self, host):
        resource_pools = self.cache.get_all_objs(self.content, [vim.ResourcePool])
        for rp in resource_pools.items():
            if not rp[0]:
                continue

            if not hasattr(rp[0], 'parent') or not rp[0].parent:
                continue

            # Find resource pool on host
            if self.obj_has_parent(rp[0].parent, host.parent):
                # If no resource_pool selected or it's the selected pool, return it
                if self.module.params['resource_pool'] is None or rp[0].name == self.module.params['resource_pool']:
                    return rp[0]

        if self.module.params['resource_pool'] is not None:
            self.module.fail_json(msg="Could not find resource_pool %s for selected host %s"
                                  % (self.module.params['resource_pool'], host.name))
        else:
            self.module.fail_json(msg="Failed to find a resource group for %s" % host.name)

    def register_vm(self, template=False):

        result = dict(
            changed=False,
            failed=False,
        )

        f_obj = self.fobj_from_folder_path(dc=self.params['datacenter'], folder=self.params['folder'])
        # abort if no strategy was successful
        if f_obj is None:
            self.module.fail_json(msg='No folder matched the path: %(folder)s' % self.params)
        destfolder = f_obj

        if self.params['esxi_hostname'] is None:
            esxhost = self.select_host(self.params['datastore'])
        else:
            esxhost = self.cache.get_esx_host(self.params['esxi_hostname'])

        if template:
            task = destfolder.RegisterVM_Task("[%s] %s" % (self.params['datastore'], self.params['path']), self.params['name'], asTemplate=True, host=esxhost)
        else:
            # Now we need a resource pool
            if self.params['esxi_hostname']:
                resource_pool = self.select_resource_pool_by_host(esxhost)
            elif self.params['resource_pool_cluster_root']:
                if self.params['cluster'] is None:
                    self.module.fail_json(msg='resource_pool_cluster_root requires a cluster name')
                else:
                    rp_cluster = self.cache.get_cluster(self.params['cluster'])
                    if not rp_cluster:
                        self.module.fail_json(msg="Failed to find a cluster named %(cluster)s" % self.params)
                    resource_pool = rp_cluster.resourcePool
            else:
                resource_pool = self.select_resource_pool_by_name(self.params['resource_pool'])

            if resource_pool is None:
                self.module.fail_json(msg='Unable to find resource pool, need esxi_hostname, resource_pool, or cluster and resource_pool_cluster_root')
            # Now finally register the VM
            task = destfolder.RegisterVM_Task("[%s] %s" % (self.params['datastore'], self.params['path']), self.params['name'], asTemplate=False, host=esxhost, pool=resource_pool)
                                       
        if task:
            wait_for_task(task)
            if task.info.state == 'error':
                result['failed'] = True
                result['msg'] = str(task.info.error.msg)
            else:
                result['changed'] = True

        return result

    
def main():
    argument_spec = vmware_argument_spec()
    argument_spec.update(
        state=dict(type='str', default='present', choices=['present', 'absent']),
        annotation=dict(type='str', aliases=['notes']),
        name=dict(type='str', required=True),
        is_template=dict(type='bool', default=False),
        path=dict(type='str', required=True),
        folder=dict(type='str', required=True),
        datacenter=dict(type='str', required=True),
        datastore=dict(type='str', required=True),
        esxi_hostname=dict(type='str'),
        cluster=dict(type='str'),
        resource_pool=dict(type='str'),
        resource_pool_cluster_root=dict(type='bool'),
    )

    module = AnsibleModule(argument_spec=argument_spec,
                           supports_check_mode=True,
                           mutually_exclusive=[
                               ['cluster', 'esxi_hostname'],
                           ],
                           required_together=[
                               ['cluster', 'resource_pool_cluster_root']
                           ],
                           )

    result = {'failed': False, 'changed': False}

    # FindByInventoryPath() does not require an absolute path
    # so we should leave the input folder path unmodified
    module.params['folder'] = module.params['folder'].rstrip('/')

    pyv = PyVmomiHelper(module)

    # Check if the VM exists before continuing

    f_obj = pyv.fobj_from_folder_path(dc=module.params['datacenter'], folder=module.params['folder'])
    if f_obj is None:
        module.fail_json(msg='No folder matched the path: %(folder)s' % module.params)

    vm = pyv.getvm(name=module.params['name'], folder=f_obj)
    # The object exists
    if vm:
        if module.params['state'] == 'absent':
            # Unregister the vm
            try:
                vm.UnregisterVM()
            except vim.fault.TaskInProgress:
                module.fail_json(msg="vm is busy, cannot unregister")
            except vim.fault.InvalidPowerState:
                module.fail_json(msg="Cannot unregister a VM which is powered on")
            except Exception as e:
                module.fail_json(msg=to_native(e))
            result['changed']=True
            module.exit_json(**result)
        else:
            module.exit_json(**result)            
    else:
        result = pyv.register_vm(template=module.params['is_template'])
                              
    if result['failed']:
        module.fail_json(**result)
    else:
        module.exit_json(**result)


if __name__ == '__main__':
    main()
