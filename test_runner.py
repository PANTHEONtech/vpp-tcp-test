import os
import subprocess
from test_runner_config import *

with open("tcp_stack_results.csv", "w") as result_file:
    result_file.write(
        "Sessions;Connections/Session;Message size;Test Case;VPP;Docker;"
        "Total Throughput;Average per Session;Failed Sessions\n")
    for session_count in sessions:
        for connection_count in connections:
            for message_size in message_sizes:
                for test_case in test_cases:
                    for vpp_state in vpp:
                        for docker_state in docker:
                            # Retry once if test fails
                            for x in range(2):
                                testrun_name = "s[{0}]c[{1}]ms[{2}]" \
                                               "_{3}_vpp-{4}_docker-{5}".format(
                                                session_count,
                                                connection_count,
                                                message_size,
                                                test_case,
                                                vpp_state,
                                                docker_state
                                                )
                                command = (
                                    "python ./tcp_stack_test.py"
                                    " -s {sessions} -c {connections}"
                                    " -ms {message_size}"
                                    " --procdist {test_case}{vpp_state}{docker}"
                                    "{skip_cores}"
                                    " --logdir {logdir}".format(
                                        sessions=session_count,
                                        connections=connection_count,
                                        message_size=message_size,
                                        test_case=test_case,
                                        vpp_state="" if vpp_state
                                        else " --no_vpp",
                                        docker=" --docker" if docker_state
                                        else "",
                                        skip_cores=" --skip_cores {0}".format(
                                            skip_cores) if skip_cores else "",
                                        logdir="/tmp/" + testrun_name,
                                        ))
                                print "Running test case '{0}' with command:\n"\
                                      "{1}".format(testrun_name, command)
                                test = subprocess.Popen(
                                    command,
                                    shell=True,
                                    stdout=subprocess.PIPE)
                                test.poll()
                                result = test.stdout.readlines()
                                line = 0
                                try:
                                    while "Failed to connect sessions:" \
                                            not in result[line]:
                                        line += 1
                                    failed_sessions = int(
                                        result[line].split(" ")[4])
                                    if failed_sessions > session_count/10:
                                        print "More than 10% of sessions " \
                                              "failed to connect. " \
                                              "({0} out of {1})".format(
                                                failed_sessions, session_count)
                                    throughput = result[line+2].split(" ")[1]
                                    average = result[line+3].split(" ")[4]
                                except IndexError:
                                    print "Results not available. Test Failed."
                                    continue
                                else:
                                    result_file.write("{0};".format(
                                        session_count))
                                    result_file.write("{0};".format(
                                        connection_count))
                                    result_file.write("{0};".format(
                                        message_size))
                                    result_file.write("{0};".format(
                                        test_case))
                                    result_file.write("{0};".format(
                                        vpp_state))
                                    result_file.write("{0};".format(
                                        docker_state))
                                    result_file.write("{0};".format(
                                        throughput))
                                    result_file.write("{0};".format(
                                        average))
                                    result_file.write("{0}\n".format(
                                        failed_sessions))
                                    break
                            else:
                                print "Test failed after retrying."
                                result_file.write("{0};".format(
                                    session_count))
                                result_file.write("{0};".format(
                                    connection_count))
                                result_file.write("{0};".format(
                                    message_size))
                                result_file.write("{0};".format(
                                    test_case))
                                result_file.write("{0};".format(
                                    vpp_state))
                                result_file.write("{0};".format(
                                    docker_state))
                                result_file.write("N/A;" * 2)
                                result_file.write("N/A\n")
                            result_file.flush()
                            os.fsync(result_file.fileno())
