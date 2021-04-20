import unittest
import grpc  # type: ignore

import pythonmulticlient


class TestMultiNameChannel(unittest.TestCase):
    def test_no_backend(self) -> None:
        # calling get with an invalid name should still return a channel
        empty_grpc_options = ()
        multi_channel = pythonmulticlient.MultiNameChannel(
            ["doesnotexist.example.com:12345"], empty_grpc_options
        )
        channel1 = multi_channel.get()
        self.assertIsNotNone(channel1)

        # calling get again will return the same channel
        channel2 = multi_channel.get()
        self.assertEqual(channel1, channel2)

        # a fake gRPC call will fail with a message about DNS resolution
        unary_callable = channel1.unary_unary("bad_method")
        with self.assertRaisesRegex(grpc.RpcError, "DNS resolution") as cm:
            resp = unary_callable(b"bad_request")
        self.assertEqual(cm.exception.code(), grpc.StatusCode.UNAVAILABLE)

        # after close, a call fails with closed message; multiple close calls are permitted
        multi_channel.close()
        multi_channel.close()
        with self.assertRaisesRegex(ValueError, "closed channel"):
            resp = unary_callable(b"bad_request")
