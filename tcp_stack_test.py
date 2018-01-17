#!/usr/bin/env python

import unittest
import os
import sys
import yaml
from iperf3_tc import Iperf3TestCase
from tcpkali_tc import tcpkali_TestCase

ATTR_NO_VPP = '--no-vpp'
USE_VPP = True


def build_suite(config):
    suite = unittest.TestSuite()
    if config['iperf3']['enable']:
        suite.addTest(Iperf3TestCase(config))
    if config['tcpkali']['enable']:
        suite.addTest(tcpkali_TestCase(config))
    return suite


if __name__ == "__main__":
    if sys.argv:
        if ATTR_NO_VPP in sys.argv:
            sys.argv.remove(ATTR_NO_VPP)
            USE_VPP = False

    test_config_file = os.getcwd() + "/config.yml"

    try:
        with open(test_config_file, 'r') as ymlf:
            test_config = yaml.load(ymlf)
    except Exception as e:
        print "Failed to open config file. Error: {}".format(e)
        print "Exiting."
        sys.exit(1)

    runner = unittest.TextTestRunner()
    test_suite = build_suite(test_config)
    runner.run(test_suite)
