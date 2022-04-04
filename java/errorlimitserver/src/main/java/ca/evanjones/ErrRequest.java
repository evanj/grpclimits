package ca.evanjones;

public class ErrRequest {
  private static final String PREFIX = "errLength=";

  public static int parseErrLength(String msg) {
    if (!msg.startsWith(PREFIX)) {
      throw new IllegalArgumentException("msg does not start with " + PREFIX);
    }

    final String numericPart = msg.substring(PREFIX.length(), msg.length());
    return Integer.parseInt(numericPart);
  }

  public static String generate(int length) {
    final String MSG_BASE = "this is a long error message abcdefghijklmnopqrstuvwxyz 0123456789 ";
    final StringBuilder builder = new StringBuilder(length);
    while (builder.length() < length) {
      builder.append(MSG_BASE);
    }
    builder.setLength(length);
    return builder.toString();
  }
}
