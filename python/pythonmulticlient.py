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


class NamedChannel(object):
    def __init__(self, name: str) -> None:
        # names must not be empty
        assert len(name) > 0
        self.name = name
        self.grpc_channel = None


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


class RoundRobinMultiChannel(object):
    """Select a ready gRPC channel from a set of addresses, using a round-robin policy.
    This set the gRPC channel option grpc.lb_policy_name=round_robin."""

    CONNECT_TIMEOUT_S = 0.1

    def __init__(
        self, names: typing.List[str], grpc_options: typing.Iterable[typing.Tuple[str, str]]
    ) -> None:
        if len(names) == 0:
            raise ValueError("names cannot be empty")

        # shuffle so separate instances must have a different order
        names = list(names)
        random.shuffle(names)
        self.named_channels = []
        for name in names:
            self.named_channels.append(NamedChannel(name))

        self.grpc_options = tuple(grpc_options) + (_ROUND_ROBIN_OPTION,)
        self.lock = threading.Lock()
        self.next_index = 0

    def get(self) -> grpc.Channel:
        """Returns a ready Channel from the set, or a random channel if none are ready."""

        with self.lock:
            # check each channel in the round-robin order
            first_checked_index = self.next_index
            while True:
                named_channel = self.named_channels[self.next_index]
                self.next_index = (self.next_index + 1) % len(self.named_channels)

                if named_channel.grpc_channel is not None:
                    # call a private grpc channel method to see if the channel is working
                    try_to_connect = True
                    state_code = named_channel.grpc_channel._channel.check_connectivity_state(
                        try_to_connect
                    )
                    state = _connectivity_code_to_object(state_code)
                    if state is grpc.ChannelConnectivity.READY:
                        return named_channel.grpc_channel

                    # not ready: check the other channels
                    logging.debug("skipping channel=%s in state=%s", named_channel.name, state.name)

                else:
                    # no channel yet: create it and wait the connect timeout
                    logging.debug("connecting to channel=%s", named_channel.name)
                    named_channel.grpc_channel = grpc.insecure_channel(
                        named_channel.name, self.grpc_options
                    )
                    connected_future = grpc.channel_ready_future(named_channel.grpc_channel)
                    try:
                        connected_future.result(timeout=RoundRobinMultiChannel.CONNECT_TIMEOUT_S)
                        return named_channel.grpc_channel
                    except grpc.FutureTimeoutError:
                        logging.debug(
                            "failed to connect to channel=%s with timeout=%fs",
                            named_channel.name,
                            RoundRobinMultiChannel.CONNECT_TIMEOUT_S,
                        )

                if first_checked_index == self.next_index:
                    break

            # we did not find any ready channel. Select one at random.
            # gRPC will try to connect to failed dns names in the background
            named_channel = random.choice(self.named_channels)
            return named_channel.grpc_channel

    def close(self) -> None:
        """Closes all gRPC channels. Only close if you really are finished with the channels."""

        with self.lock:
            for named_channel in self.named_channels:
                if named_channel.grpc_channel is not None:
                    named_channel.grpc_channel.close()


class ChannelHolder(object):
    def __init__(self, channel: grpc.Channel) -> None:
        assert channel is not None
        self.channel = channel

    def get(self) -> grpc.Channel:
        return self.channel


class ChannelGetter(typing_extensions.Protocol):
    def get(self) -> grpc.Channel:
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
    parser.add_argument(
        "--round_robin", default=False, action="store_true", help="use round_robin "
    )
    args = parser.parse_args()
    if args.addrs == "":
        raise ValueError("--addrs is required")

    addrs = args.addrs.split(",")
    grpc_options: typing.Iterable[typing.Tuple[str, str]] = ()
    if args.round_robin:
        # see channel arguments:
        # https://grpc.github.io/grpc/python/glossary.html#term-channel_arguments
        # https://github.com/grpc/grpc/blob/v1.37.x/include/grpc/impl/codegen/grpc_types.h
        grpc_options = (("grpc.lb_policy_name", "round_robin"),)
    logging.info(
        "connecting to %d addresses = %r; grpc_options=%r ...", len(addrs), addrs, grpc_options
    )

    if len(addrs) == 1 and not args.force_multi:
        logging.warning("using single gRPC channel with single address")
        channel = grpc.insecure_channel(addrs[0], grpc_options)
        channel_getter: ChannelGetter = ChannelHolder(channel)
    else:
        logging.info("using RoundRobinMultiChannel with %d addresses = %r ...", len(addrs), addrs)
        channel_getter = RoundRobinMultiChannel(addrs, grpc_options)

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
