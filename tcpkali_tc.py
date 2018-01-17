import unittest
import psutil
import subprocess
import os
import json
import sys
import time
import resource

from base_tc import TestInfo, check_wait_kill, VPPInstance, TCPStackBaseTestCase

class tcpkali_TestCase(TCPStackBaseTestCase):

    def __init__(self, test_config, USE_VPP=None):
        super(tcpkali_TestCase, self).__init__(test_config, USE_VPP)

        self.server_log_file = self.test_config['tcpkali']['server_log']
        self.client_log_file = self.test_config['tcpkali']['client_log']
        self.server_mem_log_file = self.test_config['tcpkali']['server_mem_log']
        self.client_mem_log_file = self.test_config['tcpkali']['client_mem_log']

    def setUp(self):
        super(tcpkali_TestCase, self).setUp()

    def tearDown(self):
        super(tcpkali_TestCase, self).tearDown()

    def runTest(self):
        """ Testing TCP stack using tcpkali """
        test_result_file = self.test_result_dir + "/tcpk_test.txt"
        self.test_info = TestInfo(test_result_file)

        self.test_info.printt("=======================================")
        self.test_info.printt("Testing TCP stack using tcpkali\n")
        tcpk_env = {"TERM": 'xterm-256color'}

        tcpk_host = self.test_config['tcpkali']['host']
        tcpk_port = self.test_config['tcpkali']['port']
        tcpk_connections = self.test_config['tcpkali']['connections']
        tcpk_conn_rate = self.test_config['tcpkali']['connect_rate']
        tcpk_server_time = self.test_config['tcpkali']['test_duration_server']
        tcpk_client_time = self.test_config['tcpkali']['test_duration_client']
        tcpk_msg = self.test_config['tcpkali']['message']
        tcpk_latency_marker = self.test_config['tcpkali']['latency_marker']
        tcpk_msg_rate = self.test_config['tcpkali']['message_rate']
        tcpk_server_worker_num = self.test_config['tcpkali']['server_workers']
        tcpk_client_worker_num = self.test_config['tcpkali']['client_workers']

        if tcpk_latency_marker != '':
            tcpk_latency_marker = "--latency-marker \"{}\"".format(tcpk_latency_marker)

        if tcpk_server_worker_num != 0:
            tcpk_server_worker = '-w {}'.format(tcpk_server_worker_num)
        if tcpk_client_worker_num != 0:
            tcpk_client_worker = '-w {}'.format(tcpk_server_worker_num)

        tcpk_server_cmd = "/usr/local/bin/tcpkali -l {} {} --listen-mode=active -T{}s".format(tcpk_port, tcpk_server_worker, tcpk_server_time).split(' ')
        tcpk_client_cmd = "/usr/local/bin/tcpkali {}:{} {} -c {} {} -r {} --connect-rate={} -m \"{}\" -T{}s".format(tcpk_host, tcpk_port, tcpk_client_worker, tcpk_connections, tcpk_latency_marker, tcpk_msg_rate, tcpk_conn_rate, tcpk_msg, tcpk_client_time).split(' ')

        if self.USE_VPP:
            self.vpp_instance = VPPInstance(self.test_config['vpp']['binary'], self.test_config['vpp']['startup_conf'], self.test_config['vpp']['log'], self.test_config['vpp']['memory_log'], self.test_info)
            self.vpp_instance._startVPP()
            if self.vpp_instance.vpp_process.returncode:
                self._test_info("Exiting...")
                return None
            tcpk_env = {"LD_PRELOAD": self.vcllib, "TERM": 'xterm-256color'}

        # increase open files limit (at least twice connection_num & pow of 2)
        resource.setrlimit (resource.RLIMIT_NOFILE, [32768, 32768])
        
        self.test_info.printt(tcpk_server_cmd)
        tcpk_server_process = subprocess.Popen(tcpk_server_cmd, env=tcpk_env, stdin=subprocess.PIPE, stdout=self.server_log)

        time.sleep(1)
        
        self.test_info.printt(tcpk_client_cmd)
        tcpk_client_process = subprocess.Popen(tcpk_client_cmd, env=tcpk_env, stdin=subprocess.PIPE)

        tcpk_server = (tcpk_server_process, tcpk_server_time + 30 + (tcpk_connections / tcpk_conn_rate), "TCPKALI-SERVER");
        tcpk_client = (tcpk_client_process, tcpk_client_time + 30 + (tcpk_connections / tcpk_conn_rate), "TCPKALI-CLIENT");

        tcpk_process_list = [tcpk_server, tcpk_client]

        if self.USE_VPP:
            self.server_mem_log.write("Using vcllib_ldpreload\n")
            self.client_mem_log.write("Using vcllib_ldpreload\n")

        self.server_mem_log.write("{}\n".format(tcpk_server_cmd))
        self.client_mem_log.write("{}\n".format(tcpk_client_cmd))

        timeout = 0 # termination timeout
        kill_timeout = 0
        while tcpk_process_list:
            for tcpk_process in tcpk_process_list:
                tcpk_process[0].poll()
                # check if process is running
                if tcpk_process[0].returncode is not None:
                    self.test_info.printt("{}: Process stopped".format(tcpk_process[2]))
                    tcpk_process_list.remove(tcpk_process)
                    continue
                # check timeout
                if timeout >= tcpk_process[1]:                                                   
                    self.test_info.printt("{}: Process is still running, will be terminated".format(tcpk_process[2]))
                    tcpk_process[0].terminate()
                    time.sleep(0.1)
                    tcpk_process[0].poll()
                    # wait for termination (3 sec then kill)
                    while tcpk_process[0].returncode is None:
                        if kill_timeout >= 3:
                            self.test_info.printt("{}: Killing the process".format(name))
                            tcpk_process[0].kill()
                            kill_timeout = 0
                            break 
                        tcpk_process[0].poll()
                        time.sleep(1)
                        kill_timeout += 1
                    continue
                # write memory usage (if process is running)
                try:
                    psu_proc = psutil.Process(tcpk_process[0].pid)
                    psu_mem = psu_proc.memory_info()
                    if tcpk_process[2] == "TCPKALI-SERVER":
                        self.server_mem_log.write("{}: NAME {} RES {}B VIRT {}B SHR {}B TIME {}\n".format(tcpk_process[2], psu_proc.name(), psu_mem[0], psu_mem[1], psu_mem[2], time.ctime()))
                    else:
                        self.client_mem_log.write("{}: NAME {} RES {}B VIRT {}B SHR {}B TIME {}\n".format(tcpk_process[2], psu_proc.name(), psu_mem[0], psu_mem[1], psu_mem[2], time.ctime()))
                except psutil.NoSuchProcess:
                    pass
                if self.vpp_instance:
                    self.vpp_instance._write_memory()
            # update timeout
            time.sleep(1)
            timeout += 1

        tcpk_client_process = None
        tcpk_server_process = None

        if self.vpp_instance:
            self.vpp_instance._stop_vpp()

        self.test_info.printt("\nTest results:")
        output = open(self.server_log_file, 'r')
        out = output.read()
        self.test_info.printt(out)
        self.test_info.printt("=======================================")
