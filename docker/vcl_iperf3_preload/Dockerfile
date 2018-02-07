FROM vcl_iperf3

ADD ./libvcl_ldpreload.so.0.0.0 /libs/

ENV LD_PRELOAD=/libs/libvcl_ldpreload.so.0.0.0

ENTRYPOINT ["iperf3"]
