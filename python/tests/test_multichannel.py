import grpc
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
        return "localhost:" + str(self.listen_port)

    def close(self) -> None:
        self.server.stop(grace=0)


_EMPTY_GRPC_OPTIONS = ()


class TestRoundRobinMultiStub(unittest.TestCase):
    def test_no_backend(self) -> None:
        # calling get with an invalid name should still return a channel
        multi_stub = pythonmulticlient.RoundRobinMultiStub(
            ["doesnotexist.example.com:12345"],
            helloworld_pb2_grpc.GreeterStub,
        )
        stub1 = multi_stub.get()
        self.assertIsNotNone(stub1)

        # calling get again will return the same channel
        stub2 = multi_stub.get()
        self.assertEqual(stub1, stub2)

        # a fake gRPC call will fail with a message about DNS resolution
        with self.assertRaisesRegex(grpc.RpcError, "DNS resolution") as cm:
            stub1.SayHello(helloworld_pb2.HelloRequest(name="test"))
        self.assertEqual(cm.exception.code(), grpc.StatusCode.UNAVAILABLE)

        # after close, a call fails with closed message; multiple close calls are permitted
        multi_stub.close()
        multi_stub.close()
        with self.assertRaisesRegex(ValueError, "closed channel"):
            stub1.SayHello(helloworld_pb2.HelloRequest(name="test"))

    def _make_test_backend(self) -> Backend:
        server = grpc.server(concurrent.futures.ThreadPoolExecutor(max_workers=2))
        backend = HelloWorldServicer()
        helloworld_pb2_grpc.add_GreeterServicer_to_server(backend, server)
        listen_port = server.add_insecure_port("localhost:0")
        server.start()

        return Backend(server, backend, listen_port)

    def test_local_backends(self) -> None:
        backend_a = self._make_test_backend()
        backend_b = self._make_test_backend()

        multi_stub = pythonmulticlient.RoundRobinMultiStub(
            [backend_a.addr(), backend_b.addr()],
            helloworld_pb2_grpc.GreeterStub,
        )

        try:
            # 4 requests should execute correctly
            for _ in range(4):
                resp = multi_stub.get().SayHello(helloworld_pb2.HelloRequest(name="test"))
                self.assertEqual(resp.message, "message")

            # the requests should have been evenly distributed across the backends
            self.assertEqual(2, backend_a.backend._request_count)
            self.assertEqual(2, backend_b.backend._request_count)

            # calling close multiple times is fine, but requests should fail
            multi_stub.close()
            multi_stub.close()
            with self.assertRaisesRegex(ValueError, "closed"):
                multi_stub.get().SayHello(helloworld_pb2.HelloRequest(name="test"))

            # create a stub with 1 working and 1 broken backend: requests should work
            partial_stubs = pythonmulticlient.RoundRobinMultiStub(
                [backend_a.addr(), "localhost:1"], helloworld_pb2_grpc.GreeterStub
            )
            for _ in range(4):
                resp = partial_stubs.get().SayHello(helloworld_pb2.HelloRequest(name="test"))
                self.assertEqual(resp.message, "message")
            self.assertEqual(6, backend_a.backend._request_count)

        finally:
            multi_stub.close()
            backend_b.close()
            backend_a.close()
