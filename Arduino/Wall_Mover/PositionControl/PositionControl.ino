#include <Tic.h>
#include <SoftwareSerial.h>

SoftwareSerial ticSerial(10, 11); //pin 10 (Arduino RX pin) to Driver TX; pin 11 (Arduino TX pin) to Driver RX
TicSerial tic1(ticSerial, 14);
TicSerial tic2(ticSerial, 15);

#define analogIn

// Time variables
volatile uint32_t SampleStartTime = 0;


// Sends a "Reset command timeout" command to the Tic.
void resetCommandTimeout() {
  tic1.resetCommandTimeout();
  tic2.resetCommandTimeout();
}

// Delays for the specified number of milliseconds while resetting the Tic's command timeout so that its movement does not get interrupted.
void delayWhileResettingCommandTimeout(uint32_t ms) {
  uint32_t start = millis();
  do
  {
    resetCommandTimeout();
  } while ((uint32_t)(millis()-start) <= ms);
}

// Polls the Tic, waiting for it to reach the specified target position.
void waitForPosition(int32_t targetPosition) {
  do
  {
    resetCommandTimeout();
  } while (tic1.getCurrentPosition() != targetPosition);
}


void setup() {
  // Set the baud rate.
  ticSerial.begin(9600);

  pinMode(analogIn, INPUT_PULLUP);

  // Give the Tic some time to start up.
  delay(20);
  // Set the Tic's current position to 0
  tic1.haltAndSetPosition(0);
  tic2.haltAndSetPosition(0);
  // Tells the Tic that it is OK to start driving the motor.
  tic1.exitSafeStart();
  tic2.exitSafeStart();

  SampleStartTime = micros();
}

void loop() {
tic1.setTargetPostition(targetPosition)
tic2.setTargetPostition(targetPosition)
waitForPosition(targetPosition);
}