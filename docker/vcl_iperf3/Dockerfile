FROM ubuntu:latest

ADD *.deb ./

RUN dpkg -i *.deb

ENTRYPOINT ["iperf3"]