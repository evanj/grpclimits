# gRPC Error Limits

gRPC servers should never return errors with messages larger than 7 kiB. If they do, they will not be reliably received by clients without custom configuration. If the server returns error details, the messages are sent twice, and the detail messages are included in an 8 kiB limit. In this case, messages must be even shorter. If a server returns an error larger than this, the clients will get a confusing error: `Received RST_STREAM with error code 2`. It can be hard to tell on the server side that this limit is being exceeded without turning on verbose gRPC logging.

<a href="https://www.evanjones.ca/grpc-is-tricky.html">See my blog post for more details</a>. I also wrote 3 gRPC bugs based on this: <a href="https://github.com/grpc/grpc-go/issues/4265">1</a>, <a href="https://github.com/grpc/grpc-go/issues/4266">2</a>, <a href="https://github.com/grpc/grpc/issues/25713">3</a>.

## details

The gRPC error message is serialized in an HTTP2 header (`grpc-status`). Clients can specify a limit on the size of the total header bytes they will accept. The HTTP2 specification notes that the default is unlimited,
but provides `SETTINGS_MAX_HEADER_LIST_SIZE` as an "advisory setting" to tell the peer the limit they are prepared to accept. However, the [gRPC PROTOCOL-HTTP2 document](https://github.com/grpc/grpc/blob/master/doc/PROTOCOL-HTTP2.md) states "Clients may limit the size of Response-Headers, Trailers, and Trailers-Only, with a default of 8 KiB each suggested". The Go implementation does not follow this limit, but Java and C do. If you use error details, then gRPC serializes the error message twice: Once in the `grpc-status` header, then a second time in the `grpc-status-details-bin` header, which is sadly [undocumented (gRPC issue)](https://github.com/grpc/grpc/issues/24007). This header contains a Base64-encoded [google.rpc.Status](https://github.com/googleapis/googleapis/blob/master/google/rpc/status.proto) protobuf, which has a copy of the message and the code, in addition to a list of the details messages. As a result, if you use error detail, you are probably limited to closer to 3 kiB of data in your error messages.

Requests with very large request metadata, which is also stored in headers, could also trigger similar errors. I have not tested that case.


## Go

The default limit on the HTTP2 header frame set by the client and server is 16 MiB [(transport/defaults.go)](https://github.com/grpc/grpc-go/blob/master/internal/transport/defaults.go#L47). "Our current implicit setting is 16MB (by golang http2 package), and I am setting that explicitly now" [original PR](https://github.com/grpc/grpc-go/pull/2084). It can be changed using the `WithMaxHeaderListSize` option to the `Dial` function for clients and `MaxHeaderListSize` for servers. Increasing the limit does allow very large errors to be returned.

To print the verbose debug logs, set `GRPC_GO_LOG_VERBOSITY_LEVEL=99 GRPC_GO_LOG_SEVERITY_LEVEL=info` [(gRPC docs)](https://github.com/grpc/grpc-go/blob/master/README.md#how-to-turn-on-logging)



### Defaults: Error message length >= 16777030

Server shows no message. Client shows:

```
gRPC code=13 (Internal); 36 bytes in error message: peer header list size exceeded limit
```


### Defaults: Error message length >= 16777217

This is 1 byte past 16 MiB. Server shows no message. Client shows:
```
2021/03/05 09:57:29 gRPC code=14 (Unavailable); 20 bytes in error message: transport is closing
```

Even with verbose gRPC logs, the client and server only show:
```
INFO: 2021/03/14 08:56:45 [transport] transport: loopyWriter.run returning. connection error: desc = "transport is closing"
```

I *think* the client is closing the connection first. At the very least, in Wireshark, I see the server delivering many "full length" HTTP2 CONTINUATION frames with 16384 bytes of data, then a HTTP2 CONTINUATION frame with 7134 bytes of data and the END HEADERS flag, which I assume is the end of the trailers. It appears the server sends the entire error message length. The client then ACKs this, and sends a FIN/ACK to the server to close the TCP connection, with no more HTTP2 messages.


### Client limit 8192: Error message length >= 8003

Server:
```
ERROR: 2021/03/05 10:13:18 [transport] header list size to send violates the maximum size (8192 bytes) set by client
WARNING: 2021/03/05 10:13:18 [core] grpc: Server.processUnaryRPC failed to write status: transport: trying to send header list size larger than the limit set by peer
```

Client:
```
2021/03/05 10:13:18 gRPC code=13 (Internal); 63 bytes in error message: stream terminated by RST_STREAM with error code: INTERNAL_ERROR
```


## Python

For verbose debug logs, set `GRPC_TRACE=all GRPC_VERBOSITY=info` [(gRPC docs)](GRPC_VERBOSITY)

### Defaults Error message length >= 8003

```
code=StatusCode.INTERNAL len(msg)=37 msg=Received RST_STREAM with error code 2
```


### Python server: No error!

The Python server does not honor the client's max header list size request. It returns the entire overly long response, so the client then fails with:

```
code=StatusCode.RESOURCE_EXHAUSTED len(msg)=45 msg=received trailing metadata size exceeds limit
```

This at least makes more sense than the previous error!
