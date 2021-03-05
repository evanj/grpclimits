#!/usr/bin/env python3

import grpc
import helloworld_pb2
import helloworld_pb2_grpc
import logging
#import grpc_status.rpc_status


def main():
    addr = 'localhost:8001'

    print('sending request to {} ...'.format(addr))
    channel = grpc.insecure_channel(addr)
    client = helloworld_pb2_grpc.GreeterStub(channel)

    req = helloworld_pb2.HelloRequest(
        name="errLength=8003",
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
        print("EXCEPTION! code={} len(msg)={} msg={}".format(
            e.code(), len(msg), msg_truncated))


if __name__ == '__main__':
    logging.basicConfig()
    main()
