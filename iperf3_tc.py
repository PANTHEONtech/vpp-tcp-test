import psutil
import subprocess
import os
import json
import time
from itertools import cycle
import ipaddress

from base_tc import TestInfo, check_wait_kill, docker_cleanup, VPPInstance,\
    TCPStackBaseTestCase


class Iperf3TestCase(TCPStackBaseTestCase):

    def __init__(self, test_config, use_vpp=True, use_docker=False,
                 corelist=None, corelist_client=None):
        super(Iperf3TestCase, self).__init__(test_config, use_vpp)

        self.server_log_file = "{0}/iperf3/iperf_server_log.txt".format(
            self.test_config['global']['log_dir'])
        self.client_log_file = "{0}/iperf3/iperf_client_log.txt".format(
            self.test_config['global']['log_dir'])
        self.server_mem_log_file = "{0}/iperf3/iperf_server_mem_log.txt".format(
            self.test_config['global']['log_dir'])
        self.client_mem_log_file = "{0}/iperf3/iperf_client_mem_log.txt".format(
            self.test_config['global']['log_dir'])
        self.use_vpp = use_vpp
        self.corelist = corelist
        self.corelist_client = corelist_client if corelist_client else corelist
        self.use_docker = use_docker

    def setUp(self):
        super(Iperf3TestCase, self).setUp()

    def tearDown(self):
        super(Iperf3TestCase, self).tearDown()

    def runTest(self):
        """ Testing TCP stack using iperf3 """
        test_result_file = self.test_result_dir + "/iperf3_test.txt"
        self.test_info = TestInfo(test_result_file)

        self.test_info.printt("=======================================")
        self.test_info.printt("Testing TCP stack using iperf3\n")
        iperf_env = None
        iperf_server_list = []
        iperf_client_list = []
        port_in_use = []
        iperf_output_file_list = []

# set test configuration

        iperf_host = self.test_config['global']['host'] if self.use_vpp\
            or self.use_docker else "localhost"
        default_port = self.test_config['iperf3']['default_port']
        iperf_sessions = self.test_config['iperf3']['sessions']
        iperf_connections =\
            self.test_config['iperf3']['connections_per_session']
        iperf_message_size = self.test_config["iperf3"]["message_size"]
        iperf_time = self.test_config['iperf3']['test_duration']
        add_to = self.test_config['iperf3']['additional_timeout']

        for i in range(iperf_sessions):
            iperf_output_file_list.append(
                '{0}/iperf3/iperf_session_{1}.txt'.format(
                    self.test_config["global"]["log_dir"], i))
            try:
                os.remove(iperf_output_file_list[i])
            except OSError:
                pass

        if self.use_docker:
            iperf_path = "docker run -i --net vcl_docker_net --rm " \
                         "{0} {1} {2}".format(
                            "-v /dev/shm:/dev/shm",
                            "-v {0}:{0}".format(
                                self.test_config["global"]["log_dir"]),
                            "vcl_iperf3_preload" if self.use_vpp
                            else "vcl_iperf3")

        else:
            iperf_path = "/usr/local/bin/iperf3"

        iperf_server_cmd = "{0}" \
                           " -s -B {1} -4 -1 -V -i 0".format(iperf_path,
                                                             iperf_host)
        iperf_client_cmd = "{iperf_path}" \
                           " -c {host} -4 -P {connections} -t {time}" \
                           " -O 10 -V -i 0 -l {length} --json".format(
                            iperf_path=iperf_path,
                            host=iperf_host,
                            connections=iperf_connections,
                            time=iperf_time,
                            length=iperf_message_size)

        if self.use_vpp:
            # start vpp and set env var
            for x in range(3):
                self.vpp_instance = VPPInstance(
                    self.test_config['vpp']['binary'],
                    self.test_config['vpp']['startup_conf'],
                    self.test_config['global']['log_dir'],
                    self.test_info)
                self.vpp_instance._start_vpp()
                if self.vpp_instance.vpp_process.returncode:
                    continue
                try:
                    self.vpp_instance._configure_interface(
                        self.test_config['global']['host'])
                except RuntimeError:
                    self.vpp_instance._stop_vpp()
                    # Cleanup and restart VPP
                    continue
                if self.use_vpp and not self.use_docker:
                    iperf_env = {"LD_PRELOAD": self.vcllib}
                else:
                    iperf_env = None
                self.test_info.printt(
                    "Using vcllib_ldpreload: {}".format(iperf_env))
                self.vpp_instance._write_memory()
                break
            else:
                self.test_info.printt("VPP startup/configuration failed after "
                                      "retrying.")

        if self.use_docker:
            self.test_info.printt("Configuring docker network.")
            proc = subprocess.Popen(("docker", "network", "create",
                                     "--subnet=192.168.0.0/16",
                                     "vcl_docker_net"),
                                    stdout=subprocess.PIPE)
            for x in range(3):
                if proc.poll() is not None:
                    break
                else:
                    time.sleep(1)
            else:
                raise RuntimeError("Timeout creating docker network.")
            self.test_info.printt(proc.stdout.read())

        # get ports in use
        if iperf_host == "localhost":
            for sconn in psutil.net_connections():
                # If any port that was going to be used with iperf is already
                # in use, store it in a list. These ports will be skipped.
                if (sconn.laddr[1] >= default_port)\
                        and (sconn.laddr[1] <= default_port + iperf_sessions):
                    port_in_use.append(sconn.laddr[1])
                    self.test_info.printt(
                        "Port in use: {}".format(sconn.laddr[1]))

        def ip_address(address_str):
            """Wrapper fr ipaddress.ip_address(). Handles localhost
            and allows using non-unicode strings."""
            if address_str == "localhost":
                address_str = "127.0.0.1"
            return ipaddress.ip_address(unicode(address_str))

        def ip_generator(start_ip):
            """Returns incrementing IPv4 addresses, starting with
            the one provided."""
            ip_addr = ip_address(unicode(start_ip))
            last_ip = ip_address(u"255.255.255.255")
            while ip_addr <= last_ip:
                yield ip_addr
                ip_addr += 1

# start iperf servers

        for i, cpu, ip in zip(range(iperf_sessions),
                              cycle(self.corelist),
                              ip_generator(iperf_host)):
            self.test_info.printt("Starting: IPERF-SERVER-{}".format(i))
            # check if next port is in use
            if port_in_use:
                while True:
                    if (default_port + i) in port_in_use:
                        default_port += 1
                    else:
                        break
            iperf_server_cmd_tmp = "{} -p {} -A {}".format(
                iperf_server_cmd,
                default_port + i,
                cpu)
            if self.use_docker and not self.use_vpp:
                iperf_server_cmd_tmp = iperf_server_cmd_tmp.replace(
                    "docker run", "docker run --ip {0}".format(ip))
                iperf_server_cmd_tmp = iperf_server_cmd_tmp.replace(
                    "-B {0}".format(iperf_host), "-B {0}".format(ip))
            self.test_info.printt(iperf_server_cmd_tmp)
            iperf_server_list.append(
                [
                    subprocess.Popen(
                        iperf_server_cmd_tmp.split(' '),
                        env=iperf_env,
                        stdin=subprocess.PIPE,
                        stdout=self.server_log),
                    i])
            # time.sleep(0.1)
        self.test_info.printt("IPERF-SERVER(s) running...")

        time.sleep(1)

# start iperf clients

        # reset default port (in case some ports were skipped)
        default_port = self.test_config['iperf3']['default_port']

        for i, cpu, server_ip, client_ip in zip(
                range(iperf_sessions),
                cycle(self.corelist_client),
                ip_generator(iperf_host),
                ip_generator(
                    str(ip_address(
                        unicode(iperf_host)) + iperf_sessions))):
            self.test_info.printt("Starting: IPERF-CLIENT-{}".format(i))
            # check if next port is in use
            if port_in_use:
                while True:
                    if (default_port + i) in port_in_use:
                        default_port += 1
                    else:
                        break
            iperf_client_cmd_tmp = "{} -p {} -A {} --logfile {}".format(
                iperf_client_cmd,
                default_port + i,
                cpu,
                iperf_output_file_list[i])
            if self.use_docker and not self.use_vpp:
                iperf_client_cmd_tmp = iperf_client_cmd_tmp.replace(
                    "docker run", "docker run --ip {0}".format(client_ip))
                iperf_client_cmd_tmp = iperf_client_cmd_tmp.replace(
                    "-c {0}".format(iperf_host), "-c {0}".format(server_ip))
            self.test_info.printt(iperf_client_cmd_tmp)
            iperf_client_list.append(
                [
                    subprocess.Popen(
                        iperf_client_cmd_tmp.split(' '),
                        env=iperf_env,
                        stdin=subprocess.PIPE,
                        stdout=self.client_log),
                    i])
            # time.sleep(0.1)
        self.test_info.printt("IPERF-CLIENT(s) running...")

        self.test_info.printt("IPERF-TEST is running... timeout: {} seconds"
                              .format(iperf_time + add_to))

# wait until test is done

        timeout = 0
        while iperf_client_list or iperf_server_list:
            if timeout >= (iperf_time + add_to):
                break
            for iperf_client in iperf_client_list:
                iperf_client[0].poll()
                if iperf_client[0].returncode is not None:
                    self.test_info.printt("IPERF-CLIENT-{}: Stopped".format(
                        iperf_client[1]))
                    iperf_client_list.remove(iperf_client) 
            for iperf_server in iperf_server_list:
                iperf_server[0].poll()
                if iperf_server[0].returncode is not None:
                    self.test_info.printt("IPERF-SERVER-{}: Stopped".format(
                        iperf_server[1]))
                    iperf_server_list.remove(iperf_server)
            time.sleep(1)
            timeout += 1

# terminate/kill all processes

        for iperf_client in iperf_client_list:
            check_wait_kill(
                "IPERF-CLIENT-{}".format(iperf_client[1]),
                iperf_client[0],
                1,
                self.test_info)
        for iperf_server in iperf_server_list:
            check_wait_kill(
                "IPERF-SERVER-{}".format(iperf_server[1]),
                iperf_server[0],
                1,
                self.test_info)

        if self.vpp_instance:
            self.vpp_instance._stop_vpp()

        if self.use_docker:
            docker_cleanup("vcl_docker_net", self.test_info)

# load test results

        results_json_list = []
        for iperf_output_file in iperf_output_file_list:
            output = open(iperf_output_file, 'r')
            out = output.read()
            try:
                results_json_list.append(json.loads(out))
            except ValueError as e:
                self.test_info.printt("{}: {}".format(e, iperf_output_file))

        self.test_info.printt("\nTest results:")

# print per session test results

        thp = 0
        i = -1
        failed_sessions = 0
        ok_sessions = 0
        for results_json in results_json_list:
            i += 1
            try:
                thp_tmp = float(
                    results_json['end']['sum_received']['bits_per_second']
                ) / 1024 / 1024 / 1024
                self.test_info.printt(
                    "IPERF-SESSION-%d Throughput: %0.3f Gb/sec" % (i, thp_tmp))
                if thp_tmp == 0:
                    failed_sessions += 1
                else:
                    ok_sessions += 1
                thp += thp_tmp
            except KeyError:
                try:
                    error = results_json['error']
                    self.test_info.printt(
                        "IPERF_SESSION-{}: {}".format(i, error))
                except KeyError:
                    self.test_info.printt(
                        "IPERF_SESSION-{}: something wrong in output file... {}"
                        .format(i, results_json))

# print test results

        self.test_info.printt(
            "\nTotal sessions: {}".format(iperf_sessions))
        self.test_info.printt(
            "Connections per session: {}".format(iperf_connections))
        self.test_info.printt(
            "Succesful sessions: {}".format(ok_sessions))
        self.test_info.printt(
            "Failed to connect sessions: {}".format(iperf_sessions - (
                ok_sessions + failed_sessions)))
        self.test_info.printt(
            "Throughput error (0 b/s): {}".format(failed_sessions))
        if ok_sessions != 0:                                                                     
            self.test_info.printt(
                "Throughput: %0.3f Gb/sec" % thp)
            self.test_info.printt(
                "Average throughput per session: %0.3f Gb/sec" % (
                    thp / ok_sessions))
        self.test_info.printt("=======================================")
