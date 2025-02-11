#include <Tic.h>
#include <SoftwareSerial.h>

// Tic Setup
SoftwareSerial ticSerial(10, 11); //pin 10 to Driver TX; pin 11 to Driver RX
TicSerial tic1(ticSerial, 14);
TicSerial tic2(ticSerial, 15);

// Constants
//    Arduino pins:
#define EncoderPin A0
#define ScalingPin 2
//    Data Stream:
#define DEAD_ZONE 0.75  // Ignore changes below 0.5 degrees
#define SCALE_MIN 0.5  // Minimum speed scaling (e.g., 50%)
#define SCALE_MAX 2.0  // Maximum speed scaling (e.g., 200%)
//    Rotary Encoder, Motor specs:
#define StepsRevolution 200 //Steppers
#define Microsteps 1 //Steppers: Microsteps per Step
#define StepsDegree ((StepsRevolution*Microsteps)/360.0)

// Variables
float currentPosition = 0;
float lastPosition = 0;
float Degree = 0;
static float CurrentSpeed = 0.00;
static int previousTargetVelocity = 0;
int targetVelocity = 0;
int rotationCount = 0;
//    Scaling
volatile uint32_t pulseStart = 0;
volatile uint32_t pulseWidth = 0;
volatile bool newPulse = false;
float scaleFactor = 1.0;  // Default scaling factor
//    Time variables
volatile uint32_t SampleStartTime = 0; 
volatile uint32_t SampleStopTime = 0;
volatile uint32_t ElapsedTime = 0;


float mapfloat(float x, float in_min, float in_max, float out_min, float out_max) {
  return (x-in_min) * (out_max-out_min) / (in_max - in_min) + out_min;
}

void getPulseWidth() {
    if (digitalRead(ScalingPin) == HIGH) {
        pulseStart = micros();  // Capture start time on rising edge
    } else {
        pulseWidth = micros() - pulseStart;  // Calculate pulse duration
        newPulse = true;  // Flag to indicate a new measurement is ready
    }
}

// Function to read encoder position from 0-4V input
float readEncoderPosition() {
    int rawValue = analogRead(EncoderPin);  // Read 12-bit ADC value of 4.5V (0-3686)
    //Serial.println(rawValue);
    return (rawValue / 3686.0) * 360.0;  // Convert to 0-360°
}

int calculateTargetVelocity(float speed) {
  return speed*StepsDegree*10000*scaleFactor; // microsteps per 10000 seconds
}

void MeasureRotation() {
  currentPosition = readEncoderPosition(); 
  SampleStopTime = micros(); //in ms
  ElapsedTime = SampleStopTime-SampleStartTime;

  Degree = currentPosition - lastPosition;

  // Handle wraparound
  if (Degree > 180){
    Degree -= 360;
    rotationCount --;
  } else if (Degree < -180){
    Degree += 360;
    rotationCount ++;
  }

  // Ignore small fluctuations
  if (ElapsedTime > 0 && abs(Degree) >= DEAD_ZONE) {
    CurrentSpeed = Degree / ElapsedTime * 1000000;  // deg/s
  } else {
    CurrentSpeed = 0;  // Set speed to zero if change is too small
  }

  SampleStartTime = SampleStopTime;
  lastPosition = currentPosition;
}

void SynchWalls() {
  MeasureRotation();

  targetVelocity = calculateTargetVelocity(CurrentSpeed);
  if (targetVelocity != previousTargetVelocity) {
    tic1.setTargetVelocity(targetVelocity);
    tic2.setTargetVelocity(targetVelocity*-1);
    previousTargetVelocity = targetVelocity;
  }
}

// Sends a "Reset command timeout" command to the Tic.
void resetCommandTimeout() {
  tic1.resetCommandTimeout();
  tic2.resetCommandTimeout();
}

// Delays for the specified number of milliseconds while resetting the Tic's command timeout so that its movement does not get interrupted.
void delayWhileResettingCommandTimeout(uint32_t ms) {
  uint32_t start = millis();
  do {
    resetCommandTimeout();
  } while ((uint32_t)(millis() - start) <= ms);
}


void setup() {
  ticSerial.begin(115385);
  //Serial.begin(115200);
  analogReadResolution(12);

  pinMode(EncoderPin, INPUT);
  pinMode(ScalingPin, INPUT);
  attachInterrupt(digitalPinToInterrupt(ScalingPin), getPulseWidth, CHANGE);
  
  // Initialize Tic motor controllers
  delayWhileResettingCommandTimeout(20);

  SampleStartTime = micros();
}

void loop() {
  noInterrupts();
  if (newPulse) {
    newPulse = false;  // Reset flag

    // Map pulse width to scaling factor (adjust values based on your pulse range)
    scaleFactor = mapfloat(pulseWidth, 500, 5000, 0.5, 2.0);
    scaleFactor = constrain(scaleFactor, 0.5, 2.0);  // Ensure it stays within range

    //Serial.print("Pulse Width: ");
    //Serial.print(pulseWidth);
    //Serial.print(" µs | Scale Factor: ");
    //Serial.println(scaleFactor);
  }
  interrupts();

  SynchWalls();
  //Serial.print("Current Pos: "); Serial.print(currentPosition);
  //Serial.print(" | Last Pos: "); Serial.print(lastPosition);
  //Serial.print(" | Degree: "); Serial.print(Degree);
  //Serial.print(" | Speed (deg/s): "); Serial.print(CurrentSpeed);
  //Serial.print(" | Target Velocity: "); Serial.print(targetVelocity);
  //Serial.print(" | Rotation Count: "); Serial.println(rotationCount);
  resetCommandTimeout();
}
