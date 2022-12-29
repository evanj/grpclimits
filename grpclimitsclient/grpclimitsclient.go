package main

import (
	"context"
	"flag"
	"log"
	"time"

	"github.com/evanj/grpclimits/errrequest"
	"github.com/evanj/grpclimits/helloworld"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/keepalive"
	"google.golang.org/grpc/status"
	"google.golang.org/protobuf/proto"
	"google.golang.org/protobuf/reflect/protoreflect"
)

func main() {
	addr := flag.String("addr", "localhost:8001", "server address")
	errLength := flag.Int("errLength", 128, "error message length")
	maxHeaderSize := flag.Int("maxHeaderSize", 0, "value to set using WithMaxHeaderListSize")
	keepaliveTime := flag.Duration("keepaliveTime", 0, "enable client keepalive with this time")
	count := flag.Int("count", 1, "number of requests to make")
	interRequestSleep := flag.Duration("interRequestSleep", 0, "time to sleep between requests")
	withBlock := flag.Bool("withBlock", true, "if we should use the WithBlock dial option")
	dialTimeout := flag.Duration("dialTimeout", time.Minute, "timeout to use for DialContext")
	flag.Parse()

	dialOptions := []grpc.DialOption{grpc.WithTransportCredentials(insecure.NewCredentials())}
	if *withBlock {
		log.Printf("setting Dial option WithBlock")
		dialOptions = append(dialOptions, grpc.WithBlock())
	}
	if *maxHeaderSize > 0 {
		log.Printf("setting Dial option WithMaxHeaderListSize(%d)", *maxHeaderSize)
		dialOptions = append(dialOptions, grpc.WithMaxHeaderListSize(uint32(*maxHeaderSize)))
	}
	if *keepaliveTime != 0 {
		log.Printf("setting client keepalive time=%s", keepaliveTime.String())
		opt := grpc.WithKeepaliveParams(keepalive.ClientParameters{Time: *keepaliveTime})
		dialOptions = append(dialOptions, opt)
	}

	ctx := context.Background()
	dialCtx := ctx
	cancel := func() {}
	if *dialTimeout > 0 {
		dialCtx, cancel = context.WithTimeout(ctx, *dialTimeout)
		log.Printf("setting Dial timeout=%s", dialTimeout.String())
	}
	conn, err := grpc.DialContext(dialCtx, *addr, dialOptions...)
	cancel()
	if err != nil {
		panic(err)
	}
	client := helloworld.NewGreeterClient(conn)

	log.Printf("sending request to %s with error length %d ...", *addr, *errLength)
	for i := 0; i < *count; i++ {
		if i > 0 {
			time.Sleep(*interRequestSleep)
		}

		resp, err := client.SayHello(ctx, &helloworld.HelloRequest{Name: errrequest.New(*errLength)})
		if err != nil {
			if grpcStatus, ok := status.FromError(err); ok {
				msg := grpcStatus.Message()
				msgTruncated := msg
				if grpcStatus.Code() != codes.Unavailable {
					const msgLimit = 70
					if len(msgTruncated) > msgLimit {
						msgTruncated = msg[:msgLimit] + "...TRUNCATED FOR DISPLAY"
					}
				}

				details := grpcStatus.Details()
				detailsBytes := 0
				for _, detail := range details {
					detailsBytes += proto.Size(detail.(protoreflect.ProtoMessage))
				}
				totalBytes := len(msg)
				if len(details) > 0 {
					// the message and code is DUPLICATED in the Status protobuf
					// the -bin header is base64 encoded
					// this is an underestimate, but is close enough
					b64Bytes := (len(msg) + detailsBytes) * 4 / 3
					totalBytes += b64Bytes
				}
				log.Printf("gRPC code=%d (%s); len(msg)=%d; len(details)=%d; details bytes=%d; TOTAL BYTES=%d; msg=%s",
					grpcStatus.Code(), grpcStatus.Code().String(), len(msg), len(details),
					detailsBytes, totalBytes, msgTruncated)
			} else {
				panic(err)
			}
		} else {
			log.Printf("SUCCESS %d bytes", proto.Size(resp))
		}
	}

	time.Sleep(time.Second)

	err = conn.Close()
	if err != nil {
		panic(err)
	}
	time.Sleep(100 * time.Millisecond)
}
