# Parameters for test_runner script.

# Number os client/server pairs
sessions = [1, 5, 10, 20, 50, 100]

# Number of connections between each client/server pair (iperf3 -N)
connections = [1, 2, 4, 8, 16]

# Size of transmitter messages, also size of send and receive buffer (iperf3 -l)
message_sizes = [60, 1600, "128KB"]

# CPU affinity distribution. See 'tcp_stack_test.py -h' for details.
test_cases = ["ls", "ps", "ns", "nn"]

# Use VPP+VCL LD_PRELOAD. "False" is useful for comparison with Unix TCP stack.
vpp = [False, True]

# Use Docker containers.
# Otherwise all servers and clients run in host global namespace
docker = [False, True]

# Do not use the specified CPU cores (and their Hyperthreading twins)
# List cores used by kernel tasks or by VPP(configured in /etc/vpp/startup.conf)
skip_cores = "0,1-3"
