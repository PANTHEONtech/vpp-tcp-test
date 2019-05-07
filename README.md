# VPP TCP Stack Test: Performance testing tool

Performance testing of VPP TCP host stack. VPP claims to provide a major 
improvement over stardard Linux bridge for inter-container communication,
by passing packets through [shared memory](https://docs.fd.io/vpp/17.10/libmemif_doc.html).

Using LD_PRELOAD the VCL library is preloaded for use with 
[iperf3](https://github.com/esnet/iperf), a bandwidth measurement tool. 

The main component is a Python script which configures the test environment,
and then generates pairs of iperf3 client and server processes. Processes
are pinned to specific CPUs with regards to NUMA topology and Hyperthreading,
allowing multiple configurations.

### Requirements
```
VPP >= 18.01, earlier versions not tested
iperf3 >= 3.1.3
(Optional)
Docker
```

### Installation

[Build VPP](https://wiki.fd.io/view/VPP/Build,_install,_and_test_images#Build_A_VPP_Package)

Obtain the VCL library from VPP build.
```
<vpp-dir>/build-root/install-vpp-native/vpp/lib64/libvcl_ldpreload.so.0.0.0
```
Edit config.yml to set path to the VCL library.
```
vcllib:
    path: <dir>/libvcl_ldpreload.so.0.0.0
```

Tests can be performed on baremetal or using Docker containers. If you intend
to use Docker, run the image builder script in docker/ and pass it the location
of your VCL library.
 ```
 docker/build_images.sh <dir>/libvcl_ldpreload.so.0.0.0
 ```

### Running the test

Individual tests may be run directly with the tcp_stack_test.py script. Pass
-h to see help information. Most arguments use default values from config.yml
unless explicitly specified.

NOTE: Configuring VPP, as well as using the VCL library requires superuser
privileges.
```
sudo python tcp_stack_test.py -s 5 --docker --logdir /tmp/vcl_test
```
The above example will start up and configure VPP, spin up 5 pairs of Docker 
containers running iperf3 with LD_PRELOADed VCL library, and place all test logs
into /tmp/vcl_test.

### Batch execution

The test_runner.py script automates execution of a large number of test runs, 
with varying numbers of sessions, connections per session, etc. 
```
sudo python test_runner.py
```
Configure the script in test_runner_config.py
```
sessions = [1, 5, 10, 20]
connections = [1, 2, 4, 8, 16]
message_sizes = [60, 300, 900, 1500]
```
Test results are written into a .csv file, ready for import into your 
favorite data processor.

