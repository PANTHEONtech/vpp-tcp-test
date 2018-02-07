#!/usr/bin/env bash
if [ ! -e ./vcl_iperf3_preload/libvcl_ldpreload.so.0.0.0 ]
    then
    if [ -z $1 ]
        then
        echo "Provide location of vcl library (libvcl_ldpreload.so.0.0.0)"
        exit 1
    else
        cp $1 ./vcl_iperf3_preload
    fi
fi

# Get iperf3
wget -P vcl_iperf3 https://iperf.fr/download/ubuntu/iperf3_3.1.3-1_amd64.deb
wget -P vcl_iperf3 https://iperf.fr/download/ubuntu/libiperf0_3.1.3-1_amd64.deb

# Generate docker images
docker build ./vcl_iperf3 -t vcl_iperf3
docker build ./vcl_iperf3_preload -t vcl_iperf3_preload
