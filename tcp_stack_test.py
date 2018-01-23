#!/usr/bin/env python

import unittest
import os
import argparse
import yaml
from iperf3_tc import Iperf3TestCase
from tcpkali_tc import tcpkali_TestCase
from multiprocessing import cpu_count

ATTR_NO_VPP = '--no-vpp'
USE_VPP = True
logdir = "/tmp"
corelist = range(cpu_count())

logfiles = {
    "vpp": {
        "log": "vpp_log.txt",
        "memory_log": "vpp_mem_log.txt"
    },
    "iperf3": {
        "server_log": "iperf3_server_log.txt",
        "server_mem_log": "iperf3_server_mem_log.txt",
        "client_log": "iperf3_client_log.txt",
        "client_mem_log": "iperf3_client_mem_log.txt",
        "client_json_out": ""
    }
}


def build_suite(config):
    suite = unittest.TestSuite()
    if config['iperf3']['enable']:
        suite.addTest(Iperf3TestCase(
            config,
            use_vpp=USE_VPP,
            corelist=corelist))
    if config['tcpkali']['enable']:
        suite.addTest(tcpkali_TestCase(config))
    return suite


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="VCL test script.")
    parser.add_argument("--no_vpp", action='store_true',
                        help="*NOT IMPLEMENTED* Run test without VCL preload.")
    parser.add_argument("--logdir", type=str, metavar="path",
                        help="Override default location for log files.")
    parser.add_argument("--cores", type=str, metavar="2-16",
                        help="Range of CPU cores to use for client and server"
                             " processes.")
    args = parser.parse_args()
    if args.no_vpp:
        USE_VPP = False
    if args.logdir:
        logdir = args.logdir
    if args.cores:
        try:
            lowcore, highcore = args.cores.split("-")
            lowcore = int(lowcore)
            highcore = int(highcore)
        except ValueError:
            raise ValueError("Invalid value for 'cores' argument, must be "
                             "in format:\nlowcore-highcore")
        if int(highcore) >= cpu_count():
            raise ValueError(
                "Python only detects {0} CPU cores (0-{1}) but 'cores' argument"
                " specified {2} as last core.".format(
                    cpu_count(),
                    cpu_count() - 1,
                    highcore))
        corelist = [x for x in range(int(lowcore), int(highcore) + 1)]

    test_config_file = os.getcwd() + "/config.yml"

    with open(test_config_file, 'r') as ymlf:
        test_config = yaml.load(ymlf)

    test_config["global"]["test_result_dir"] = logdir
    for log in logfiles["vpp"].keys():
        test_config["vpp"][log] = "{0}/{1}".format(
            logdir, logfiles["vpp"][log])
    for log in logfiles["iperf3"].keys():
        test_config["iperf3"][log] = "{0}/{1}".format(
            logdir, logfiles["iperf3"][log])

    runner = unittest.TextTestRunner()
    test_suite = build_suite(test_config)
    runner.run(test_suite)
