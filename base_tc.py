import unittest
import os
import time
import subprocess
import psutil


class TestInfo:

    def __init__(self, test_result_file):
        try:
            os.remove(test_result_file)
        except OSError:
            pass
        try:
            self.test_result = open(test_result_file, 'w+')
        except OSError as e:
            print "Failed to open test result file. Error {}".format(e)
            self.test_result = None

    def __del__(self):
        if self.test_result:
            self.test_result.close()

    # print given "string" to test result file and console...
    def printt(self, s):
        if self.test_result:
            self.test_result.write("{}\n".format(s))
        print s


def check_wait_kill(name, process, timeout_seconds, test_info):
    timeout = 0
    process.poll()

    test_info.printt("{}: Process is running, timeout: {} seconds".format(
        name, timeout_seconds))

    while None is process.returncode:
        if timeout >= timeout_seconds:
            break
        time.sleep(1)
        timeout += 1
        process.poll()

    if None is process.returncode:
        test_info.printt(
            "{}: Process is still running, will be terminated".format(name))
        process.terminate()

        terminate_timeout = 3  # seconds
        timeout = 0
        test_info.printt(
            "{}: Waiting for process till terminates, timeout: {} seconds"
            .format(name, terminate_timeout))
        while None is process.returncode:
            if timeout >= terminate_timeout:
                break
            time.sleep(1)
            timeout += 1
            process.poll()

        test_info.printt("{}: Process is still running, will be killed".format(
            name))
        if None is process.returncode:
            test_info.printt("{}: Killing the process".format(name))
            process.kill()

    test_info.printt("{}: Process stopped".format(name))


def docker_cleanup(network, test_info, timeout_seconds=3):
    test_info.printt("Stopping containers that didn't exit:")
    timeout = 0
    devnull = open(os.devnull, "wb")
    process = subprocess.Popen("docker kill $(docker ps -q)",
                               shell=True,
                               stderr=devnull,
                               close_fds=True)
    while None is process.returncode:
        if timeout >= timeout_seconds:
            break
        time.sleep(1)
        timeout += 1
        process.poll()

    test_info.printt("Removing docker network.")
    process = subprocess.Popen(("docker", "network", "remove", network),
                               stdout=subprocess.PIPE)
    while None is process.returncode:
        if timeout >= timeout_seconds:
            break
        time.sleep(1)
        timeout += 1
        process.poll()


class VPPInstance:

    vpp_process = None
    startup_conf = None

    # TODO: cpu startup conf...
    def __init__(self, vpp_binary, startup_conf, log_dir, test_info):
        self.test_info = test_info
        self.vpp_binary = vpp_binary
        self.startup_conf = startup_conf
        log = "{0}/vpp/vpp_log.txt".format(log_dir)
        memory_log = "{0}/vpp/vpp_mem_log.txt".format(log_dir)

        if not os.path.isdir(os.path.dirname(log)):
            os.makedirs(os.path.dirname(log))
        try:
            self.log = open(log, 'w+')
        except OSError as e:
            self.test_info.printt(
                "Failed to open vpp log file. Error {}".format(e))
            self.log = None
        try:
            self.memory_log = open(memory_log, 'w+')
        except OSError as e:
            self.test_info.printt(
                "Failed to open vpp memory log file. Error {}".format(e))
            self.memory_log = None

    def __del__(self):
        if self.vpp_process:
            self._stop_vpp()
        if self.log:
            self.log.close()
        if self.memory_log:
            self.memory_log.close()

    def _start_vpp(self):

        self.test_info.printt("Cleaning out VPP from /dev/shm/")
        proc_vpe = subprocess.Popen(["rm", "/dev/shm/vpe-api"],
                                    stdin=subprocess.PIPE,
                                    stdout=self.log,
                                    stderr=self.log)
        proc_vm = subprocess.Popen(["rm", "/dev/shm/global_vm"],
                                   stdin=subprocess.PIPE,
                                   stdout=self.log,
                                   stderr=self.log)
        if proc_vpe.poll() is None or proc_vm.poll() is None:
            time.sleep(1)

        vpp_process = "VPP-PROCESS"

        self.test_info.printt("{}: Starting...".format(vpp_process))

        self.log.write("START {}\n".format(vpp_process))
        self.log.flush()

        self.test_info.printt(
            "{}: Starting the process with configuration:\n{}".format(
                vpp_process, self.startup_conf))

        self.vpp_process = subprocess.Popen(
            [self.vpp_binary, "-c", self.startup_conf],
            stdin=subprocess.PIPE, stdout=self.log, stderr=self.log)

        # TODO: check if VPP is ready (instead of using sleep)
        self.test_info.printt("{0}: Waiting for VPP startup".format(
            vpp_process))
        time.sleep(10)  # let the VPP startup

        self.vpp_process.poll()
        if None is not self.vpp_process.returncode:
            print "{}: Start failed, returncode: {}".format(
                vpp_process, self.vpp_process.returncode)
            return None

        self.test_info.printt("{}: Started".format(vpp_process))
        return self.vpp_process

    def _configure_interface(self, ip_address):
        def exec_vppctl(command):
            proc = subprocess.Popen(
                [
                    "vppctl",
                    command,
                ],
                stdin=subprocess.PIPE, stdout=self.log, stderr=self.log)
            for x in range(3):
                if proc.poll() is not None:
                    break
                else:
                    time.sleep(1)
            else:
                raise RuntimeError("vppctl command timed out.")

        exec_vppctl("create loopback interface")
        exec_vppctl("set int state loop0 up")
        exec_vppctl("set int ip address loop0 {0}/32".format(ip_address))
        self.test_info.printt(
            "Configured VPP loopback interface with address {0}/32"
            .format(ip_address))

    def _stop_vpp(self):
        if self.vpp_process is None:
            print "No VPP process on this instance."
            return None
        if self.vpp_process.returncode:
            print "No VPP process on this instance."
            return None
        vpp_process = "VPP-PROCESS"
        self.log.write("END {}\n".format(vpp_process))
        self.log.flush()
        self.vpp_process.terminate()
        check_wait_kill(vpp_process, self.vpp_process, 3, self.test_info)
        self.vpp_process = None

    def _write_memory(self):
        if self.vpp_process is None:
            print "No VPP process on this instance"
            return None
        if self.vpp_process.returncode:
            print "VPP process not running on this instance."
            return None

        self.vpp_process.poll()
        try:
            psu_proc = psutil.Process(self.vpp_process.pid)
            psu_mem = psu_proc.memory_info()
            self.memory_log.write(
                "VPP-PROCESS: NAME {} RES {}B VIRT {}B SHR {}B TIME {}\n"
                .format(psu_proc.name(), psu_mem[0], psu_mem[1], psu_mem[2],
                        time.ctime()))
        except psutil.NoSuchProcess:
            pass


class TCPStackBaseTestCase(unittest.TestCase):

    server_log = None
    client_log = None
    server_mem_log = None
    client_mem_log = None
    test_info = None
    vpp_instance = None
    client_log_file = None
    server_log_file = None
    client_mem_log_file = None
    server_mem_log_file = None

    def __init__(self, test_config, use_vpp=None):
        unittest.TestCase.__init__(self)
        self.test_config = test_config

        # global
        self.test_result_dir = self.test_config['global']['log_dir']

        # vpp
        if use_vpp:
            self.use_vpp = use_vpp
        else:
            self.use_vpp = self.test_config['vpp']['enable']

        # vcllib
        self.vcllib = self.test_config['vcllib']['path']

    def setUp(self):

        for logfile in (
                self.client_log_file,
                self.client_mem_log_file,
                self.server_log_file,
                self.server_mem_log_file):
            if not os.path.isdir(os.path.dirname(logfile)):
                os.makedirs(os.path.dirname(logfile))
            if not os.path.isdir(os.path.dirname(logfile)):
                os.makedirs(os.path.dirname(logfile))
        try:
            os.remove(self.client_log_file)
        except OSError:
            pass
        self.client_log = open(self.client_log_file, 'w+')

        try:
            os.remove(self.server_log_file)
        except OSError:
            pass
        self.server_log = open(self.server_log_file, 'w+')

        try:
            os.remove(self.client_mem_log_file)
        except OSError:
            pass
        self.client_mem_log = open(self.client_mem_log_file, 'w+')

        try:
            os.remove(self.server_mem_log_file)
        except OSError:
            pass
        self.server_mem_log = open(self.server_mem_log_file, 'w+')

    def tearDown(self):
        if self.client_log:
            self.client_log.close()

        if self.server_log:
            self.server_log.close()                                                   

        if self.client_mem_log:
            self.client_mem_log.close()

        if self.server_mem_log:
            self.server_mem_log.close()
