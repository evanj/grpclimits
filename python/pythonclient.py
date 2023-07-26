#!/usr/bin/env python3
import argparse
import grpc
import helloworld_pb2
import helloworld_pb2_grpc
import logging
import time
import typing

# see channel arguments:
# https://grpc.github.io/grpc/python/glossary.html#term-channel_arguments
# https://github.com/grpc/grpc/blob/v1.37.x/include/grpc/impl/codegen/grpc_types.h
_LB_POLICY_OPTION = "grpc.lb_policy_name"
_KEEPALIVE_TIME_MS_OPTION = "grpc.keepalive_time_ms"
_KEEPALIVE_TIMEOUT_MS_OPTION = "grpc.keepalive_timeout_ms"
_KEEPALIVE_PERMIT_WITHOUT_CALLS_OPTION = "grpc.keepalive_permit_without_calls"
_MAX_METADATA_SIZE_OPTION = "grpc.max_metadata_size"


def main() -> None:
    parser = argparse.ArgumentParser(description="Send a request for a large error message")
    parser.add_argument(
        "--addr",
        type=str,
        default="localhost:8001",
        help="address for server to connect to",
    )
    parser.add_argument(
        "--errLength",
        type=int,
        default=100,
        help="length of the error to return",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=1,
        help="number of requests to make",
    )
    parser.add_argument(
        "--interRequestSleep",
        type=float,
        default=0.0,
        help="seconds to sleep between requests (fractions supported)",
    )
    parser.add_argument(
        "--lbPolicy",
        type=str,
        default="",
        help="gRPC load balancer policy; default=pick_first; set to round_robin to change",
    )
    parser.add_argument(
        "--keepaliveTime",
        type=float,
        default=0.0,
        help="seconds to set keepalive_time_ms: time to wait before sending a keepalive ping",
    )
    parser.add_argument(
        "--keepaliveTimeout",
        type=float,
        default=0.0,
        help="seconds to set keepalive_timeout_ms: time to wait for ping response",
    )
    parser.add_argument(
        "--keepaliveWithoutCalls",
        type=bool,
        default=False,
        help="send keepalives even without calls; default=false",
    )
    parser.add_argument(
        "--maxHeaderSize",
        type=int,
        default=0,
        help="set grpc.max_metadata_size to change the maximum header sizes",
    )
    args = parser.parse_args()

    grpc_options: typing.Tuple[typing.Tuple[str, int], ...] = ()
    if args.lbPolicy != "":
        grpc_options += ((_LB_POLICY_OPTION, args.lbPolicy),)
    if args.keepaliveTime > 0:
        grpc_options += ((_KEEPALIVE_TIME_MS_OPTION, int(args.keepaliveTime * 1000)),)
    if args.keepaliveTimeout > 0:
        grpc_options += ((_KEEPALIVE_TIMEOUT_MS_OPTION, int(args.keepaliveTimeout * 1000)),)
    if args.keepaliveWithoutCalls:
        grpc_options += ((_KEEPALIVE_PERMIT_WITHOUT_CALLS_OPTION, 1),)
    if args.maxHeaderSize:
        grpc_options += ((_MAX_METADATA_SIZE_OPTION, args.maxHeaderSize),)

    logging.info("creating channel for addr={}; options={} ...".format(args.addr, grpc_options))
    channel = grpc.insecure_channel(args.addr, options=grpc_options)
    client = helloworld_pb2_grpc.GreeterStub(channel)

    for i in range(args.count):
        if i > 0:
            time.sleep(args.interRequestSleep)

        logging.info("sending request")
        req = helloworld_pb2.HelloRequest(
            name="errLength={}".format(args.errLength),
        )
        try:
            resp = client.SayHello(req)
            logging.info("SUCCESS")
        except grpc.RpcError as e:
            # The raised RpcError will also be a Call
            if not isinstance(e, grpc.Call):
                raise Exception("BUG: grpc.RpcError should be an instance of grpc.Call")

            msg = e.details()
            msg_truncated = msg
            LIMIT = 70
            if len(msg_truncated) > LIMIT:
                msg_truncated = msg[:LIMIT] + "...TRUNCATED"
            logging.info(
                "EXCEPTION! code={} len(msg)={} msg={}".format(e.code(), len(msg), msg_truncated)
            )


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, format="%(asctime)s %(levelname)s %(message)s")
    main()
