"""Contains functions to determine CPU affinity for client and server
processes."""

import subprocess
from time import sleep


class Affinity(object):
    def __init__(self):
        pass

    @staticmethod
    def exec_shell(command):
        """Execute the specified command in unix shell and return stdout.

        :param command: Shell command to execute.
        :type command: str

        :return: Stdout returned from running the command.
        :rtype: str
        """

        proc = subprocess.Popen(
            command, shell=True, stdout=subprocess.PIPE)
        for x in range(3):
            if proc.poll() is not None:
                break
            else:
                sleep(1)
        else:
            raise RuntimeError("Timeout executing command.")
        return proc.stdout.read()

    @staticmethod
    def parse_cores(cores_str):
        """Parse string representation of CPUs in lscpu's format into a list.

        :param cores_str: String representation of cores.
        Distinct values or ranges, separated by commas.
        Example: 1,2-3,5 == [1,2,3,5]
        :type cores_str: str

        :return: List of distinct CPUs.
        :rtype: List
        """

        cores = []
        for item in cores_str.split(","):
            if "-" in item:
                min_core, max_core = item.split("-")
                for x in range(int(min_core), int(max_core) + 1):
                    cores.append(x)
            else:
                cores.append(int(item))
        return cores

    @staticmethod
    def case_ls(ht_pairs, _numa_topology, reuse=False):
        """Client and server process pair shares a logical CPU.

        :param ht_pairs: Dictionary of Hyperthreading CPU pairs.
        :param _numa_topology: Not used.
        :param reuse: More aggressive affinity assignment, both Hyperthreading
        twins will be used for client/server pairs.

        :type ht_pairs: dict
        :type reuse: bool

        :return: Lists of CPUs
        :rtype: tuple of lists
        """

        corelist = []
        corelist_client = []
        for physcore, cores in ht_pairs.iteritems():
            corelist.append(cores[0])
            corelist_client.append(cores[0])
            if reuse:
                corelist.append(cores[1])
                corelist_client.append(cores[1])
        corelist.sort()
        corelist_client.sort()
        print "s -- c core layout"
        for x in range(len(corelist)):
            print "{0} -- {1}" .format(corelist[x], corelist_client[x])
        return corelist, corelist_client

    @staticmethod
    def case_ps(ht_pairs, _numa_topology, reuse=False):
        """Client and server process pair shares a physical (but not logical)
        CPU.

        :param ht_pairs: Dictionary of Hyperthreading CPU pairs.
        :param _numa_topology: Not used.
        :param reuse: More aggressive affinity assignment, each logical core
        will run a server from one pair and a client from another pair.

        :type ht_pairs: dict
        :type reuse: bool

        :return: Lists of CPUs
        :rtype: tuple of lists
        """

        corelist = []
        corelist_client = []
        for physcore, cores in ht_pairs.iteritems():
            corelist.append(cores[0])
            corelist_client.append(cores[1])
            if reuse:
                corelist.append(cores[1])
                corelist_client.append(cores[0])
        corelist.sort()
        corelist_client.sort()
        print "s -- c core layout"
        for x in range(len(corelist)):
            print "{0} -- {1}" .format(corelist[x], corelist_client[x])
        return corelist, corelist_client

    @staticmethod
    def case_ns(ht_pairs, numa_topology, reuse=False):
        """Client and server process pair runs on separate physical CPUs within
        the same NUMA node.

        :param ht_pairs: Dictionary of Hyperthreading CPU pairs.
        :param numa_topology: List of physical CPUs in each NUMA node.
        :param reuse: More aggressive affinity assignment, both Hyperthreading
        twins will be used for client/server pairs.

        :type ht_pairs: dict
        :type numa_topology: list of lists
        :type reuse: bool

        :return: Lists of CPUs
        :rtype: tuple of lists
        """

        corelist = []
        corelist_client = []
        if not numa_topology:
            # Fake NUMA to simplify processing
            numa_topology = [ht_pairs.keys()]
        for numa in numa_topology:
            for x in range(1, len(numa)):
                try:
                    corelist.append(ht_pairs[numa[x-1]][0])
                    corelist_client.append(ht_pairs[numa[x]][0])
                except (KeyError, IndexError):
                    break
                if reuse:
                    corelist.append(ht_pairs[numa[x-1]][1])
                    corelist_client.append(ht_pairs[numa[x]][1])
        corelist.sort()
        corelist_client.sort()
        print "s -- c core layout"
        for x in range(len(corelist)):
            print "{0} -- {1}".format(corelist[x], corelist_client[x])
        return corelist, corelist_client

    @staticmethod
    def case_nn(ht_pairs, numa_topology, reuse=False):
        """Client and server process pair runs in different NUMA nodes.

        :param ht_pairs: Dictionary of Hyperthreading CPU pairs.
        :param numa_topology: List of physical CPUs in each NUMA node.
        :param reuse: More aggressive affinity assignment, both Hyperthreading
        twins will be used for client/server pairs.

        :type ht_pairs: dict
        :type numa_topology: list of lists
        :type reuse: bool

        :return: Lists of CPUs
        :rtype: tuple of lists
        """

        corelist = []
        corelist_client = []
        for x, y in zip(numa_topology[0], numa_topology[1]):
            corelist.append(ht_pairs[x][0])
            corelist_client.append(ht_pairs[y][0])
            if reuse:
                corelist.append(ht_pairs[x][1])
                corelist_client.append(ht_pairs[y][1])
        corelist.sort()
        corelist_client.sort()
        print "s -- c core layout"
        for x in range(len(corelist)):
            print "{0} -- {1}".format(corelist[x], corelist_client[x])
        return corelist, corelist_client

    @staticmethod
    def get_ht_pairs(skip_cores=None):
        """Build dictionary of Hyperthreaded CPU pairs.

        :param skip_cores: Logical CPU cores which should not be used.
        :type skip_cores: list of int

        :return: Topology of HT pairs.
        :rtype: dict
        """

        cpuinfo = Affinity.exec_shell("lscpu -p").splitlines()
        ht_pairs = {}
        skip = []
        for line in cpuinfo:
            if line.startswith("#"):
                continue
            line = line.strip().split(",")
            cpu = int(line[0])
            phys = int(line[1])
            # numa = line[3]
            if skip_cores:
                if cpu in skip_cores:
                    skip.append(phys)
            try:
                ht_pairs[phys].append(cpu)
            except KeyError:
                ht_pairs[phys] = [cpu]
        print "Detected HyperThreading pairs:\n{0}".format(ht_pairs)
        for phycore in skip:
            lcores = ht_pairs.pop(phycore)
            print "Skipping physical core {0} == logical cores {1}.".format(
                phycore, lcores)

        return ht_pairs

    @staticmethod
    def get_numa_topo(ht_pairs):
        """Build list of NUMA nodes and associated physical CPUs.

        :param ht_pairs: Topology of HT pairs.
        :type ht_pairs: dict

        :return: List of NUMA nodes and their associated cores.
        :rtype: list of lists
        """

        numa_nodes = int(
            Affinity.exec_shell(
                "lscpu | grep 'NUMA node(s)'"
            ).strip().split(" ")[-1]
        )
        numa_topology = []
        if numa_nodes <= 1:
            print "NUMA architecture not present."
            numa_topology = None
        elif numa_nodes > 2:
            raise NotImplementedError
        else:
            for numa in range(numa_nodes):
                topo = Affinity.exec_shell(
                    "lscpu | grep 'NUMA node{0}'".format(numa))
                topo = topo.strip().split(" ")[-1]
                numa_cores = Affinity.parse_cores(topo)
                physcores = []
                for physcore, cores in ht_pairs.iteritems():
                    if cores[0] in numa_cores:
                        physcores.append(physcore)
                physcores.sort()
                numa_topology.append(physcores)

            print "Detected NUMA topology:\n{0}".format(numa_topology)

        return numa_topology
