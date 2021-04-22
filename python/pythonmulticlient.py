#!/usr/bin/env python3
import argparse
import grpc  # type: ignore
import helloworld_pb2
import helloworld_pb2_grpc
import logging
import random
import threading
import time
import typing
import typing_extensions


_CONNECTIVITY_CODE_MAP = {
    grpc.ChannelConnectivity.IDLE.value[0]: grpc.ChannelConnectivity.IDLE,
    grpc.ChannelConnectivity.CONNECTING.value[0]: grpc.ChannelConnectivity.CONNECTING,
    grpc.ChannelConnectivity.READY.value[0]: grpc.ChannelConnectivity.READY,
    grpc.ChannelConnectivity.TRANSIENT_FAILURE.value[0]: grpc.ChannelConnectivity.TRANSIENT_FAILURE,
    grpc.ChannelConnectivity.SHUTDOWN.value[0]: grpc.ChannelConnectivity.SHUTDOWN,
}


def _connectivity_code_to_object(code: int) -> grpc.ChannelConnectivity:
    # return a failure code if we see an unhandled code
    return _CONNECTIVITY_CODE_MAP.get(code, grpc.ChannelConnectivity.TRANSIENT_FAILURE)


# see channel arguments:
# https://grpc.github.io/grpc/python/glossary.html#term-channel_arguments
# https://github.com/grpc/grpc/blob/v1.37.x/include/grpc/impl/codegen/grpc_types.h
_ROUND_ROBIN_OPTION = ("grpc.lb_policy_name", "round_robin")
_EMPTY_GRPC_OPTIONS = ()


StubType = typing.TypeVar("StubType", covariant=True)


class NamedChannel(typing.Generic[StubType]):
    """Holds a gRPC channel, an address, and optionally a gRPC stub."""

    def __init__(self, addr: str, grpc_channel: grpc.Channel, stub: StubType) -> None:
        self.addr = addr
        self.grpc_channel = grpc_channel
        self.stub = stub


class RoundRobinMultiStub(typing.Generic[StubType]):
    """Select a ready stub from a set of addresses, using a round-robin policy."""

    def __init__(
        self,
        addrs: typing.Iterable[str],
        stub_type: typing.Callable[[grpc.Channel], StubType],
        grpc_options: typing.Iterable[typing.Tuple[str, str]] = _EMPTY_GRPC_OPTIONS,
    ):
        """Create a new RoundRobinMultiStub.
        This adds the grpc.lb_policy_name=round_robin gRPC channel option to grpc_options.
        """

        # shuffle so separate instances have different orders
        addrs = list(addrs)
        random.shuffle(addrs)

        grpc_options = tuple(grpc_options) + (_ROUND_ROBIN_OPTION,)

        # connect to all the channels
        named_channels: typing.List[NamedChannel[StubType]] = []
        for addr in addrs:
            grpc_channel = grpc.insecure_channel(addr, grpc_options)
            stub = stub_type(grpc_channel)
            named_channel = NamedChannel(addr, grpc_channel, stub)
            named_channels.append(named_channel)

        self.rr_named = RoundRobinNamedChannels(named_channels)

    def get(self) -> StubType:
        named_channel = self.rr_named.get()
        return named_channel.stub

    def close(self) -> None:
        self.rr_named.close()


class RoundRobinNamedChannels(typing.Generic[StubType]):
    """Select a ready gRPC channel from a set of addresses, using a round-robin policy."""

    # time to wait for idle/connecting channels before checking other channels
    _CONNECT_TIMEOUT_S = 0.05

    def __init__(self, named_channels: typing.List[NamedChannel[StubType]]) -> None:
        if len(named_channels) == 0:
            raise ValueError("channels cannot be empty")
        for named_channel in named_channels:
            assert named_channel is not None

        self.lock = threading.Lock()
        self.next_index = 0
        self.named_channels = named_channels

    def get(self) -> NamedChannel[StubType]:
        """Returns a ready NamedChannel from the set, or a random channel if none are ready."""

        with self.lock:
            # check each channel in the round-robin order
            channels = (
                self.named_channels[self.next_index :] + self.named_channels[0 : self.next_index]
            )
            assert len(channels) == len(self.named_channels)
            for i, named_channel in enumerate(channels):
                # call a private grpc channel method to see if the channel is working
                # TODO: use the public subscribe API, but that is more complicated
                try_to_connect = True
                state_code = named_channel.grpc_channel._channel.check_connectivity_state(
                    try_to_connect
                )
                state = _connectivity_code_to_object(state_code)
                if state is grpc.ChannelConnectivity.READY:
                    self.next_index = (self.next_index + 1 + i) % len(self.named_channels)
                    return named_channel

                # for idle channels: the call to check_connectivity_state(try_to_connect=True)
                # causes it to start connecting, so wait for IDLE or CONNECTING channels for a bit.
                if state in (grpc.ChannelConnectivity.IDLE, grpc.ChannelConnectivity.CONNECTING):
                    # wait to see if it manages to connect
                    connected_future = grpc.channel_ready_future(named_channel.grpc_channel)
                    try:
                        connected_future.result(timeout=RoundRobinNamedChannels._CONNECT_TIMEOUT_S)

                        # connected!
                        self.next_index = (self.next_index + 1 + i) % len(self.named_channels)
                        return named_channel
                    except grpc.FutureTimeoutError as e:
                        logging.debug(
                            "failed to connect to channel=%s within timeout=%fs; message=%s",
                            named_channel.addr,
                            RoundRobinNamedChannels._CONNECT_TIMEOUT_S,
                            str(e),
                        )

                # not ready: check the other channels
                logging.debug("skipping channel=%s in state=%s", named_channel.addr, state.name)

            # we did not find any ready channel. Select one at random
            # TODO: prefer CONNECTING over others
            return random.choice(self.named_channels)

    def close(self) -> None:
        """Closes all gRPC channels. Only close if you really are finished with the channels."""

        with self.lock:
            for named_channel in self.named_channels:
                if named_channel.grpc_channel is not None:
                    named_channel.grpc_channel.close()


class StubHolder(typing.Generic[StubType]):
    def __init__(self, stub: StubType) -> None:
        assert stub is not None
        self.stub = stub

    def get(self) -> StubType:
        return self.stub


class StubGetter(typing_extensions.Protocol[StubType]):
    def get(self) -> StubType:
        # explicitly empty: this is a mypy protocol
        # https://mypy.readthedocs.io/en/stable/protocols.html#simple-user-defined-protocols
        ...


def main() -> None:
    parser = argparse.ArgumentParser(description="Connect to some gRPC servers!")
    parser.add_argument(
        "--addrs",
        type=str,
        default="localhost:8001",
        help="comma-separated list of addresses to connect to",
    )
    parser.add_argument(
        "--force_multi",
        default=False,
        action="store_true",
        help="use the RoundRobinMultiChannel even with a single address",
    )
    args = parser.parse_args()
    if args.addrs == "":
        raise ValueError("--addrs is required")

    addrs = args.addrs.split(",")
    logging.info("connecting to %d addresses = %r ...", len(addrs), addrs)

    if len(addrs) == 1 and not args.force_multi:
        logging.warning("using single gRPC channel with single address with round_robin")
        channel = grpc.insecure_channel(addrs[0], grpc_options=(_ROUND_ROBIN_OPTION))
        stub = helloworld_pb2_grpc.GreeterStub(channel)
        channel_getter: StubGetter[helloworld_pb2_grpc.GreeterStub] = StubHolder(stub)
    else:
        logging.info("using RoundRobinMultiStub with %d addresses = %r ...", len(addrs), addrs)
        channel_getter = RoundRobinMultiStub(addrs, helloworld_pb2_grpc.GreeterStub)

    while True:
        channel = channel_getter.get()
        client = helloworld_pb2_grpc.GreeterStub(channel)

        req = helloworld_pb2.HelloRequest(name="errLength=1")
        try:
            resp = client.SayHello(req)
            logging.info("successful request message=%s", resp.message)
        except grpc.RpcError as e:
            logging.info("failed request code=%s details=%s", e.code(), e.details())

        time.sleep(2)


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    main()
