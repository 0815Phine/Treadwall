#include <Tic.h>
#include <SoftwareSerial.h>

SoftwareSerial ticSerial(10, 11); //pin 10 to Driver TX; pin 11 to Driver RX
TicSerial tic1(ticSerial, 14); //right
TicSerial tic2(ticSerial, 15); //left

#define analogIn A0
#define MicrostepsPerStep 4 //Steppers

// Thresholds for pulse detection
#define ThresholdCentre45 80
#define ThresholdCentre39 160
#define ThresholdCentre33 240
#define ThresholdCentre27 320
#define ThresholdLeft45 400
#define ThresholdLeft39 485
#define ThresholdLeft33 570
#define ThresholdLeft27 650
#define ThresholdRight45 730
#define ThresholdRight39 800
#define ThresholdRight33 915
#define ThresholdRight27 1000

int lastAnalogValue = 0;  //value read from analog output module
volatile bool pulseDetected = false;
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
  if (analogValue > ThresholdRight27 && lastAnalogValue <= ThresholdRight27) {
    pulseDetected = true;
    TrialType  = "R27";
  } else if (analogValue > ThresholdRight33  && lastAnalogValue <= ThresholdRight33) {
    pulseDetected = true;
    TrialType  = "R33";
  } else if (analogValue > ThresholdRight39  && lastAnalogValue <= ThresholdRight39) {
    pulseDetected = true;
    TrialType = "R39";
  } else if (analogValue > ThresholdRight45 && lastAnalogValue <= ThresholdRight45) {
    pulseDetected = true;
    TrialType = "R45";
  } else if (analogValue > ThresholdLeft27  && lastAnalogValue <= ThresholdLeft27) {
    pulseDetected = true;
    TrialType  = "L27";
  } else if (analogValue > ThresholdLeft33  && lastAnalogValue <= ThresholdLeft33) {
    pulseDetected = true;
    TrialType  = "L33";
  } else if (analogValue > ThresholdLeft39  && lastAnalogValue <= ThresholdLeft39) {
    pulseDetected = true;
    TrialType = "L39";
  } else if (analogValue > ThresholdLeft45 && lastAnalogValue <= ThresholdLeft45) {
    pulseDetected = true;
    TrialType = "L45";
  } else if (analogValue > ThresholdCentre27  && lastAnalogValue <= ThresholdCentre27) {
    pulseDetected = true;
    TrialType  = "C27";
  } else if (analogValue > ThresholdCentre33  && lastAnalogValue <= ThresholdCentre33) {
    pulseDetected = true;
    TrialType  = "C33";
  } else if (analogValue > ThresholdCentre39  && lastAnalogValue <= ThresholdCentre39) {
    pulseDetected = true;
    TrialType = "C39";
  } else if (analogValue > ThresholdCentre45 && lastAnalogValue <= ThresholdCentre45) {
    pulseDetected = true;
    TrialType = "C45";
  } else if (analogValue < ThresholdCentre45 && lastAnalogValue >= ThresholdCentre45) {
    pulseDetected = true;
    TrialType = "ITI";
  }

  // Update the last analog value
  lastAnalogValue = analogValue;
}

void setTargetPosition() {
  if (TrialType == "C45") {
    tic1.setTargetPosition(-60*MicrostepsPerStep);
    tic2.setTargetPosition(60*MicrostepsPerStep);
  } else if (TrialType == "L45") {
    tic1.setTargetPosition(-83*MicrostepsPerStep);
    tic2.setTargetPosition(37*MicrostepsPerStep);
  } else if (TrialType == "R45") {
    tic1.setTargetPosition(-37*MicrostepsPerStep);
    tic2.setTargetPosition(83*MicrostepsPerStep);
  }  else if (TrialType == "C39") {
    tic1.setTargetPosition(-71*MicrostepsPerStep);
    tic2.setTargetPosition(71*MicrostepsPerStep);
  } else if (TrialType == "L39") {
    tic1.setTargetPosition(-94*MicrostepsPerStep);
    tic2.setTargetPosition(48*MicrostepsPerStep);
  }  else if (TrialType == "R39") {
    tic1.setTargetPosition(-48*MicrostepsPerStep);
    tic2.setTargetPosition(94*MicrostepsPerStep);
  } else if (TrialType == "C33") {
    tic1.setTargetPosition(-83*MicrostepsPerStep);
    tic2.setTargetPosition(83*MicrostepsPerStep);
  }  else if (TrialType == "L33") {
    tic1.setTargetPosition(-106*MicrostepsPerStep);
    tic2.setTargetPosition(60*MicrostepsPerStep);
  } else if (TrialType == "R33") {
    tic1.setTargetPosition(-60*MicrostepsPerStep);
    tic2.setTargetPosition(106*MicrostepsPerStep);
  }  else if (TrialType == "C27") {
    tic1.setTargetPosition(-94*MicrostepsPerStep);
    tic2.setTargetPosition(94*MicrostepsPerStep);
  }  else if (TrialType == "L27") {
    tic1.setTargetPosition(-117*MicrostepsPerStep);
    tic2.setTargetPosition(71*MicrostepsPerStep);
  } else if (TrialType == "R27") {
    tic1.setTargetPosition(-71*MicrostepsPerStep);
    tic2.setTargetPosition(117*MicrostepsPerStep);
  } else if (TrialType == "ITI") {
    tic1.goHomeForward();
    tic2.goHomeReverse();
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

  // homes motors at outer limit switches -> connect motors accordingly to correct tic
  tic1.goHomeForward();
  tic2.goHomeReverse();
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