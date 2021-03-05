package main

import (
	"context"
	"flag"
	"log"
	"time"

	"github.com/evanj/grpclimits/errrequest"
	"github.com/evanj/grpclimits/helloworld"
	"google.golang.org/grpc"
	"google.golang.org/grpc/status"
	"google.golang.org/protobuf/proto"
	"google.golang.org/protobuf/reflect/protoreflect"
)

func main() {
	addr := flag.String("addr", "localhost:8001", "server address")
	errLength := flag.Int("errLength", 128, "error message length")
	maxHeaderSize := flag.Int("maxHeaderSize", 0, "value to set using WithMaxHeaderListSize")
	flag.Parse()

	dialOptions := []grpc.DialOption{grpc.WithInsecure(), grpc.WithBlock()}
	if *maxHeaderSize > 0 {
		log.Printf("setting Dial option WithMaxHeaderListSize(%d)", *maxHeaderSize)
		dialOptions = append(dialOptions, grpc.WithMaxHeaderListSize(uint32(*maxHeaderSize)))
	}

	log.Printf("sending request to %s with error length %d ...", *addr, *errLength)
	ctx := context.Background()

	conn, err := grpc.DialContext(ctx, *addr, dialOptions...)
	if err != nil {
		panic(err)
	}
	client := helloworld.NewGreeterClient(conn)
	resp, err := client.SayHello(ctx, &helloworld.HelloRequest{Name: errrequest.New(*errLength)})
	if err != nil {
		if grpcStatus, ok := status.FromError(err); ok {
			msg := grpcStatus.Message()
			msgTruncated := msg
			const msgLimit = 70
			if len(msgTruncated) > msgLimit {
				msgTruncated = msg[:msgLimit] + "...TRUNCATED"
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

	resp, err = client.SayHello(ctx, &helloworld.HelloRequest{})
	log.Println("follow up requset: ", resp, err)

	time.Sleep(time.Second)

	err = conn.Close()
	if err != nil {
		panic(err)
	}
	time.Sleep(100 * time.Millisecond)
}
