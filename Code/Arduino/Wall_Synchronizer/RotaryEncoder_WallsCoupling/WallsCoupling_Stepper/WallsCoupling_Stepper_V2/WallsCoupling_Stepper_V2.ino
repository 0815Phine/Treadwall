#include <Tic.h>
#include <SoftwareSerial.h>

// Tic Setup
SoftwareSerial ticSerial(10, 11); //pin 10 to Driver TX; pin 11 to Driver RX
TicSerial tic1(ticSerial, 14);
TicSerial tic2(ticSerial, 15);

// Constants
//    Arduino pins:
#define EncoderPin A0
#define ScalingPin A0
//    Data Stream:
#define DEAD_ZONE 0.5  // Ignore changes below 0.5 degrees
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
//    Time variables
volatile uint32_t SampleStartTime = 0; 
volatile uint32_t SampleStopTime = 0;
volatile uint32_t ElapsedTime = 0;

float mapfloat(float x, float in_min, float in_max, float out_min, float out_max) {
  return (x-in_min) * (out_max-out_min) / (in_max - in_min) + out_min;
}

float readScaleFactor() {
    int rawValue = analogRead(ScalingPin);  // Read scaling analog input
    return mapFloat(rawValue, 0, 4095, SCALE_MIN, SCALE_MAX);  // Map to range
}

// Function to read encoder position from 0-4V input
float readEncoderPosition() {
    int rawValue = analogRead(EncoderPin);  // Read 12-bit ADC value (0-4095)
    return (rawValue / 4095.0) * 360.0;  // Convert to 0-360°
}

int calculateTargetVelocity(float speed) {
   float scaleFactor = readScaleFactor();
  return speed*StepsDegree*10000*scaleFactor; // microsteps per 10000 seconds
}

void MeasureRotation() {
  currentPosition = readEncoderPosition(); 
  SampleStopTime = micros(); //in ms
  ElapsedTime = SampleStopTime-SampleStartTime;

  Degree = currentPosition - lastPosition;

  // Handle wraparound at ±180°
  if (Degree > 180) Degree -= 360;
  if (Degree < -180) Degree += 360;
  
  // Ignore small fluctuations
  if (abs(Degree) < DEAD_ZONE) {
     CurrentSpeed = 0;  // Set speed to zero if change is too small
  } else {
      CurrentSpeed = Degree / ElapsedTime * 1000000;  // deg/s
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
  //Serial.begin(9600);
  analogReadResolution(12);

  pinMode(EncoderPin, INPUT);
  pinMode(ScalePin, INPUT);
  
  // Initialize Tic motor controllers
  delayWhileResettingCommandTimeout(20);

  SampleStartTime = micros();
}

void loop() {
  SynchWalls();
  //Serial.print("Current Pos: "); Serial.print(currentPosition);
  //Serial.print(" | Last Pos: "); Serial.print(lastPosition);
  //Serial.print(" | Degree: "); Serial.print(Degree);
  //Serial.print(" | Speed (deg/s): "); Serial.print(CurrentSpeed);
  //Serial.print(" | Target Velocity: "); Serial.println(targetVelocity);
  resetCommandTimeout();
}
