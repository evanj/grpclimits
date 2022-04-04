package ca.evanjones;

import io.grpc.Server;
import io.grpc.ServerBuilder;
import io.grpc.Status;
import io.grpc.examples.helloworld.GreeterGrpc;
import io.grpc.examples.helloworld.HelloReply;
import io.grpc.examples.helloworld.HelloRequest;
import io.grpc.stub.StreamObserver;
import java.io.IOException;

public class ErrorLimitsServer {
  public static void main(String[] args) throws IOException, InterruptedException {
    final int PORT = 8001;
    final Server grpcServer = ServerBuilder.forPort(PORT).addService(new GreeterImpl()).build();

    System.out.println("listening to requests on port " + PORT);
    grpcServer.start();
    grpcServer.awaitTermination();
  }

  private static class GreeterImpl extends GreeterGrpc.GreeterImplBase {
    @Override
    public void sayHello(HelloRequest request, StreamObserver<HelloReply> responseObserver) {
      final int errLength = ErrRequest.parseErrLength(request.getName());
      System.out.println("returning response with errLength=" + errLength);

      final Status error =
          Status.FAILED_PRECONDITION.withDescription(ErrRequest.generate(errLength));

      responseObserver.onError(error.asException());
    }
  }
}
