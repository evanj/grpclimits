#!/usr/bin/env python3
import argparse
import grpc  # type: ignore
import helloworld_pb2
import helloworld_pb2_grpc
import logging
import time


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
        help="time to sleep between requests",
    )
    args = parser.parse_args()

    print("creating channel for addr={} ...".format(args.addr))
    channel = grpc.insecure_channel(args.addr)
    client = helloworld_pb2_grpc.GreeterStub(channel)

    for i in range(args.count):
        if i > 0:
            time.sleep(args.interRequestSleep)

        print("sending request")
        req = helloworld_pb2.HelloRequest(
            name="errLength={}".format(args.errLength),
        )
        try:
            resp = client.SayHello(req)
            print("SUCCESS")
        except grpc.RpcError as e:
            msg = e.details()
            msg_truncated = msg
            LIMIT = 70
            if len(msg_truncated) > LIMIT:
                msg_truncated = msg[:LIMIT] + "...TRUNCATED"
            print("EXCEPTION! code={} len(msg)={} msg={}".format(e.code(), len(msg), msg_truncated))


if __name__ == "__main__":
    logging.basicConfig()
    main()
