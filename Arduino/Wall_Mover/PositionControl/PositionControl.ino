#include <Tic.h>
#include <SoftwareSerial.h>

SoftwareSerial ticSerial(10, 11); //pin 10 (Arduino RX pin) to Driver TX; pin 11 (Arduino TX pin) to Driver RX
TicSerial tic1(ticSerial, 14);
TicSerial tic2(ticSerial, 15);

#define analogIn A0
#define ThresholdCentre 500
#define ThresholdLeft 700
#define ThresholdRight 900
int lastAnalogValue = 0;  //value read from analog output module
volatile bool pulseDetected = false;

volatile uint32_t SampleStartTime = 0;
String TrialType = ""; // String variable to represent trial type

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

void DetectPulse(){
  // Read the analog input
  int analogValue = analogRead(analogIn);

  // Detect rising and falling edges
  if (analogValue > ThresholdRight && lastAnalogValue <= ThresholdRight) {
    pulseDetected = true;
    TrialType  = "R";
  } else if (analogValue > ThresholdLeft  && lastAnalogValue <= ThresholdLeft) {
    pulseDetected = true;
    TrialType  = "L";
  } else if (analogValue > ThresholdCentre  && lastAnalogValue <= ThresholdCentre) {
    pulseDetected = true;
    TrialType = "C";
  }  else if (analogValue < ThresholdCentre && lastAnalogValue >= ThresholdCentre) {
    pulseDetected = true;
    TrialType = "ITI";
  }

  // Update the last analog value
  lastAnalogValue = analogValue;
}

// for 45mm
void setTargetPosition() {
  if (TrialType == "C") {
    tic1.setTargetPosition(75);
    tic2.setTargetPosition(-75);
  } else if (TrialType == "L") {
    tic1.setTargetPosition(106);
    tic2.setTargetPosition(-44);
  } else if (TrialType == "R") {
    tic1.setTargetPosition(44);
    tic2.setTargetPosition(-106);
  } else if (TrialType == "ITI") {
    tic1.setTargetPosition(0);
    tic2.setTargetPosition(0);
  }
}


void setup() {
  // Set the baud rate.
  ticSerial.begin(9600);
  Serial.begin(9600);

  pinMode(analogIn, INPUT_PULLUP);
  // Initialize the last analog value.
  lastAnalogValue = analogRead(analogIn);

  // Give the Tic some time to start up.
  delay(20);

  resetCommandTimeout();
  // Tells the Tic that it is OK to start driving the motor.
  tic1.exitSafeStart();
  tic2.exitSafeStart();

  // add here moving out completely (measured by limit switches) -> check out homing .. homing should be at the outer limit switch
  // Set the Tic's current position to 0
  tic1.haltAndSetPosition(0);
  tic2.haltAndSetPosition(0);

  SampleStartTime = micros();
}

void loop() {
  resetCommandTimeout();
  DetectPulse();

  if (pulseDetected) {
    setTargetPosition();
    //waitForPosition(targetPosition);
    pulseDetected = false;
  }
}