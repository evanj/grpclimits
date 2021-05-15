package main

import (
	"context"
	"flag"
	"log"
	"net"
	"time"

	"github.com/evanj/grpclimits/errrequest"
	"github.com/evanj/grpclimits/helloworld"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

type server struct {
	helloworld.UnimplementedGreeterServer
	responseSleep time.Duration
}

func newServer(responseSleep time.Duration) *server {
	return &server{helloworld.UnimplementedGreeterServer{}, responseSleep}
}

func (s *server) SayHello(ctx context.Context, request *helloworld.HelloRequest) (*helloworld.HelloReply, error) {
	time.Sleep(s.responseSleep)

	errMsg, err := errrequest.Generate(request.Name)
	if err != nil {
		return nil, status.Errorf(codes.InvalidArgument, err.Error())
	}
	log.Printf("returning error with len(message)=%d bytes", len(errMsg))

	// add error details
	// st, err := status.New(codes.FailedPrecondition, errMsg).WithDetails(&helloworld.HelloReply{Message: "reply"})
	// if err != nil {
	// 	return nil, status.Errorf(codes.Internal, "failed to add details: %w", err)
	// }
	// return nil, st.Err()

	return nil, status.Errorf(codes.FailedPrecondition, errMsg)
}

func main() {
	addr := flag.String("addr", "localhost:8001", "listening address")
	responseSleep := flag.Duration("responseSleep", 0, "time to sleep before responding")
	flag.Parse()

	lis, err := net.Listen("tcp", *addr)
	if err != nil {
		panic(err)
	}

	s := grpc.NewServer()
	helloworld.RegisterGreeterServer(s, newServer(*responseSleep))

	log.Printf("serving on %s ...", *addr)
	if err := s.Serve(lis); err != nil {
		panic(err)
	}
}
