import grpc  # type: ignore
import helloworld_pb2
import helloworld_pb2_grpc
import pythonmulticlient
import unittest
import threading
import concurrent.futures


class HelloWorldServicer(helloworld_pb2_grpc.GreeterServicer):
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._request_count = 0

    def SayHello(
        self, request: helloworld_pb2.HelloRequest, context: grpc.ServicerContext
    ) -> helloworld_pb2.HelloReply:
        with self._lock:
            self._request_count += 1
        return helloworld_pb2.HelloReply(message="message")


class Backend(object):
    def __init__(self, server: grpc.Server, backend: HelloWorldServicer, listen_port: int):
        self.server = server
        self.backend = backend
        self.listen_port = listen_port

    def addr(self) -> str:
        return "[::1]:" + str(self.listen_port)

    def close(self) -> None:
        self.server.stop(grace=0)


_EMPTY_GRPC_OPTIONS = ()


class TestRoundRobinMultiChannel(unittest.TestCase):
    def test_no_backend(self) -> None:
        # calling get with an invalid name should still return a channel
        multi_channel = pythonmulticlient.RoundRobinMultiChannel(
            ["doesnotexist.example.com:12345"], _EMPTY_GRPC_OPTIONS
        )
        channel1 = multi_channel.get()
        self.assertIsNotNone(channel1)

        # calling get again will return the same channel
        channel2 = multi_channel.get()
        self.assertEqual(channel1, channel2)

        # a fake gRPC call will fail with a message about DNS resolution
        unary_callable = channel1.unary_unary("bad_method")
        with self.assertRaisesRegex(grpc.RpcError, "DNS resolution") as cm:
            unary_callable(b"bad_request")
        self.assertEqual(cm.exception.code(), grpc.StatusCode.UNAVAILABLE)

        # after close, a call fails with closed message; multiple close calls are permitted
        multi_channel.close()
        multi_channel.close()
        with self.assertRaisesRegex(ValueError, "closed channel"):
            unary_callable(b"bad_request")

    def _make_test_backend(self) -> Backend:
        server = grpc.server(concurrent.futures.ThreadPoolExecutor(max_workers=2))
        backend = HelloWorldServicer()
        helloworld_pb2_grpc.add_GreeterServicer_to_server(backend, server)
        listen_port = server.add_insecure_port("[::1]:0")
        server.start()

        return Backend(server, backend, listen_port)

    def test_local_backends(self) -> None:
        backend_a = self._make_test_backend()
        backend_b = self._make_test_backend()

        multi_channel = pythonmulticlient.RoundRobinMultiChannel(
            [backend_a.addr(), backend_b.addr()], _EMPTY_GRPC_OPTIONS
        )

        try:
            # 4 requests should work
            for _ in range(4):
                channel = multi_channel.get()
                stub = helloworld_pb2_grpc.GreeterStub(channel)
                resp = stub.SayHello(helloworld_pb2.HelloRequest(name="test"))
                self.assertEqual(resp.message, "message")

            # the requests should have been evenly distributed across the backends
            self.assertEqual(2, backend_a.backend._request_count)
            self.assertEqual(2, backend_b.backend._request_count)

        finally:
            multi_channel.close()
            backend_b.close()
            backend_a.close()
