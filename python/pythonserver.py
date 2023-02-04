#!/usr/bin/env python3
import grpc
import helloworld_pb2
import helloworld_pb2_grpc
import logging
import concurrent.futures


class ErrorGreeter(helloworld_pb2_grpc.GreeterServicer):
    def SayHello(
        self, request: helloworld_pb2.HelloRequest, context: grpc.ServicerContext
    ) -> helloworld_pb2.HelloReply:
        parts = request.name.split("=")
        err_length = int(parts[1])
        err_msg = "x" * err_length
        context.set_code(grpc.StatusCode.FAILED_PRECONDITION)
        context.set_details(err_msg)
        logging.info("returning message length = %d", len(err_msg))
        return helloworld_pb2.HelloReply()


def main() -> None:
    addr = "localhost:8001"

    server = grpc.server(concurrent.futures.ThreadPoolExecutor(max_workers=10))
    helloworld_pb2_grpc.add_GreeterServicer_to_server(ErrorGreeter(), server)
    print("listening for gRPC on {} ...".format(addr))
    server.add_insecure_port(addr)
    server.start()
    server.wait_for_termination()


if __name__ == "__main__":
    logging.basicConfig()
    main()
