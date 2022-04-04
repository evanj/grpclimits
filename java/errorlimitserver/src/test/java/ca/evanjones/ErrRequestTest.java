package ca.evanjones;

import static org.junit.Assert.assertEquals;

import org.junit.Test;

public class ErrRequestTest {
  @Test
  public void parsesValidValue() {
    assertEquals(42, ErrRequest.parseErrLength("errLength=42"));
  }

  @Test
  public void generateCorrectLength() {
    assertEquals(42, ErrRequest.generate(42).length());
  }
}
