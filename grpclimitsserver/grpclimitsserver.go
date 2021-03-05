package main

import (
	"context"
	"flag"
	"log"
	"net"

	"github.com/evanj/grpclimits/errrequest"
	"github.com/evanj/grpclimits/helloworld"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

type server struct {
	helloworld.UnimplementedGreeterServer
}

func (s *server) SayHello(ctx context.Context, request *helloworld.HelloRequest) (*helloworld.HelloReply, error) {
	errMsg, err := errrequest.Generate(request.Name)
	if err != nil {
		return nil, status.Errorf(codes.InvalidArgument, err.Error())
	}
	log.Printf("returning error with len(message)=%d bytes", len(errMsg))

	// st, err := status.New(codes.FailedPrecondition, errMsg).WithDetails(&helloworld.HelloReply{Message: "reply"})
	// if err != nil {
	// 	return nil, status.Errorf(codes.Internal, "failed to add details: %w", err)
	// }
	// return nil, st.Err()
	return nil, status.Errorf(codes.FailedPrecondition, errMsg)
}

func main() {
	addr := flag.String("addr", "localhost:8001", "listening address")
	flag.Parse()

	lis, err := net.Listen("tcp", *addr)
	if err != nil {
		panic(err)
	}

	s := grpc.NewServer()
	helloworld.RegisterGreeterServer(s, &server{})

	log.Printf("serving on %s ...", *addr)
	if err := s.Serve(lis); err != nil {
		panic(err)
	}
}
