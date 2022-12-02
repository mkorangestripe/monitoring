'''
Collect system metrics
'''

import json
import logging
import os
from pprint import pprint
import re
import sys
from datetime import datetime
from urllib import request
import yaml

import psutil

# Ansible creates this log file and chown's to the user:
LOG_FILE = "/var/log/linux_monitor.log"
CONFIG_FILE = "linux_monitor_config.yml"

FORMAT = '%(asctime)-15s %(levelname)s %(message)s'
logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format=FORMAT)

try:
    with open(CONFIG_FILE, "r", encoding="utf-8") as yaml_in_file:
        metrics_config = yaml.safe_load(yaml_in_file)
except:
    logging.critical("Could not open %s, exiting", CONFIG_FILE)
    sys.exit(1)

locals().update(metrics_config['settings'])
fs_config_file = config_dir + fs_config_file_name
fs_config_file_max_age_hours = fs_config_file_max_age / 3600
fs_config_url = fs_config_base_url + fs_config_file_name
hostname = os.uname().nodename

starttime = datetime.now().timestamp()
logging.info("Starting metrics collection")

def get_json(json_url, json_file, json_required=True):
    '''Get the json config file, write to file, return content'''
    logging.info("Getting update for %s", json_file)
    request_for_json = request.Request(json_url)
    json_bytes = ''

    try:
        with request.urlopen(request_for_json) as response:
            json_bytes = response.read()
    except (request.URLError, request.HTTPError) as error:
        logging.error("%s | %s", error, json_url)

    if json_bytes != '':
        with open(json_file, 'wb') as out_file:
            out_file.write(json_bytes)
    elif json_required is True:
        logging.critical("Cannot get %s, exiting", json_url)
        exit_gracefully()

    return json_bytes

def read_json_file_on_disk(json_file):
    '''Read in file and return raw content'''
    with open(json_file, 'r', encoding="utf-8") as json_in_file:
        file_content = json_in_file.read()

    return file_content

def exit_gracefully():
    '''Exit gracefully'''
    endtime = datetime.now().timestamp()
    runtime = endtime - starttime
    logging.info("Finished, metrics collection run time: %.2f seconds" % runtime)
    sys.exit()

class SystemMetrics:
    """Collect system metrics"""

    def __init__(self):
        self.fs_config = ''
        self.mountpoint_ignore_regex = ''
        self.filesystem_ignore_regex = ''
        self.filtered_filesystems = {}
        self.metrics = {}
        self.metrics['filesystems'] = {}

    def get_load_avg(self):
        """Get system load averages"""
        logging.info("Collecting system load metrics")
        system_load_avg = {}
        system_load_1, system_load_5, system_load_15 = os.getloadavg()
        system_load_avg["system.load.1"] = system_load_1
        system_load_avg["system.load.5"] = system_load_5
        system_load_avg["system.load.15"] = system_load_15
        self.metrics["system_load_avg"] = system_load_avg

    def get_uptime(self):
        """Get system uptime"""
        logging.info("Getting system uptime")
        system_timestamp = int(datetime.now().timestamp())
        try:
            boot_time = psutil.boot_time()
        except:
            logging.error("Could not collect system uptime")
        else:
            system_uptime = system_timestamp - boot_time
            self.metrics["system.uptime"] = system_uptime

    def get_cpu_metrics(self):
        """Get CPU metrics"""
        logging.info("Collecting CPU metrics")
        cpu_metrics = {}
        try:
            cpu_times_percent = psutil.cpu_times_percent()
        except:
            logging.error("Could not collect CPU metrics")
        else:
            cpu_metrics["system.cpu.user"] = cpu_times_percent.user
            cpu_metrics["system.cpu.system"] = cpu_times_percent.system
            cpu_metrics["system.cpu.idle"] = cpu_times_percent.idle
            # iowait not defined on macOS:
            cpu_metrics["system.cpu.iowait"] = cpu_times_percent.iowait
            self.metrics["system_cpu"] = cpu_metrics

    def get_mem_metrics(self):
        """Get memory metrics"""
        logging.info("Collecting memory metrics")
        memory_metrics = {}
        try:
            system_mem = psutil.virtual_memory()
        except:
            logging.error("Could not collect memory metrics")
        else:
            memory_metrics["system.mem.total"] = system_mem.total
            memory_metrics["system.mem.available"] = system_mem.available
            mem_pct_usable = system_mem.available / system_mem.total * 100
            memory_metrics["mem.pct.usable"] = round(mem_pct_usable, 5)
            self.metrics["system_mem"] = memory_metrics

    def get_swap_metrics(self):
        """Get swap space metrics"""
        logging.info("Collecting swap space metrics")
        swap_metrics = {}
        try:
            swap_memory = psutil.swap_memory()
        except:
            logging.error("Could not collect swap space metrics")
        else:
            swap_metrics["system.swap.free"] = swap_memory.free
            swap_metrics["system.swap.used"] = swap_memory.used
            self.metrics["swap_memory"] = swap_metrics

    def get_filesystem_ignore_patterns(self):
        """Get filesystem and mountpoint ignore patterns"""
        if not os.path.exists(config_dir):
            logging.info("%s not found, creating it now", config_dir)
            os.makedirs(config_dir)

        if not os.path.exists(fs_config_file):
            self.fs_config = json.loads(get_json(fs_config_url, fs_config_file))
        elif (datetime.now().timestamp() - os.stat(fs_config_file).st_mtime) >= fs_config_file_max_age:
            logging.info("%s >= %s hours", fs_config_file_name, fs_config_file_max_age_hours)
            ret_json_bytes = get_json(fs_config_url, fs_config_file, False)
            if ret_json_bytes == '':
                logging.warning("Could not retrieve new config file, using existing")
            self.fs_config = json.loads(read_json_file_on_disk(fs_config_file))
        else:
            self.fs_config = json.loads(read_json_file_on_disk(fs_config_file))

    def compile_filesystem_ignore_regex(self):
        """Compile regex patterns to ignore some filesystems and mountpoints"""
        mountpoint_ignore_patterns = self.fs_config["mountpoint_ignore_patterns"]
        try:
            self.mountpoint_ignore_regex = re.compile(mountpoint_ignore_patterns, re.I)
        except:
            logging.critical("Regex %s did not compile, exiting", mountpoint_ignore_patterns)
            exit_gracefully()

        filesystem_ignore_patterns = self.fs_config["filesystem_ignore_patterns"]
        try:
            self.filesystem_ignore_regex = re.compile(filesystem_ignore_patterns, re.I)
        except:
            logging.critical("Regex %s did not compile, exiting", filesystem_ignore_patterns)
            exit_gracefully()

    def get_filesystem_metrics(self):
        '''Collect filesystem and inode usage metrics'''

        for filesystem in self.filtered_filesystems:
            logging.info("Checking filesystem mounted at %s", self.filtered_filesystems[filesystem])
            self.metrics['filesystems'][filesystem] = {}

            try:
                disk_pct_used = psutil.disk_usage(self.filtered_filesystems[filesystem]).percent
            except:
                logging.error("Could not check disk usage on filesystem mounted at %s", self.filtered_filesystems[filesystem])
            else:
                self.metrics['filesystems'][filesystem]['system.disk.pct_used'] = disk_pct_used

            try:
                statvfs = os.statvfs(self.filtered_filesystems[filesystem])
            except:
                logging.error("Could not check inode usage on filesystem mounted at %s", self.filtered_filesystems[filesystem])
            else:
                total_inode = statvfs.f_files
                if total_inode != 0:
                    free_inode = statvfs.f_ffree
                    inodes_pct_used = (total_inode - free_inode) / total_inode * 100
                    inodes_pct_used = round(inodes_pct_used, 5)
                    self.metrics['filesystems'][filesystem]['system.fs.inodes.pct_used'] = inodes_pct_used

    def get_filesystems(self):
        """Get filesystems, filter out unwanted filesystems, and call get_filesystem_metrics()"""
        self.get_filesystem_ignore_patterns()
        self.compile_filesystem_ignore_regex()
        logging.info("Getting filesystems on machine")
        ignore_fstype = ['autofs','binfmt_misc','cgroup','configfs','debugfs','devpts','efivarfs','fusectl',
                         'hugetlbfs','mqueue','proc','pstore','securityfs','selinuxfs','sysfs']
        try:
            filesystems = psutil.disk_partitions(True)
        except:
            logging.error("Could not get filesystems on machine")
        else:
            for filesystem in filesystems:
                if filesystem.fstype not in ignore_fstype:
                    mountpoint_match = self.mountpoint_ignore_regex.match(filesystem.mountpoint)
                    filesystem_match = self.filesystem_ignore_regex.match(filesystem.device)
                    if bool(mountpoint_match) is False and bool(filesystem_match) is False:
                        self.filtered_filesystems[filesystem.device] = filesystem.mountpoint

            logging.info("Collecting filesystem metrics")
            self.get_filesystem_metrics()


system_metrics = SystemMetrics()

for method in metrics_config['metrics']:
    if method in dir(system_metrics):
        method = "system_metrics." + method
        eval(method)()

pprint(system_metrics.metrics)

exit_gracefully()
