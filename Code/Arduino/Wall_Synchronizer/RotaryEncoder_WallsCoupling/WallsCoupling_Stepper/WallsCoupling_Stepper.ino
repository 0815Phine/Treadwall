#include <Tic.h>
#include <SoftwareSerial.h>

// Tic Setup
SoftwareSerial ticSerial(10, 11); //pin 10 to Driver TX; pin 11 to Driver RX
TicSerial tic1(ticSerial, 14);
TicSerial tic2(ticSerial, 15);

// Constants
//    Arduino pins:
#define AnalogDataStreamPin A0
#define encAPin 2 //Encoder A - Arduino pin 2 to Black
#define encBPin 4 //Encoder B - Arduino pin 4 to White
//    Data Stream:
#define FW 1 //forwards
#define BW -1 //backwards
#define RunningTimeout 5000
#define MaxRunningSpeed 1 //in m/s
#define MinRunningSpeed (MaxRunningSpeed*-1)
#define MaxPWMValue 4095 //Value to generate 5V with PWM
#define pwmBaseline 2045
//    Rotary Encoder, Motor specs:
#define nSteps 1024 //Rotary Encoder: number of steps per rotation
#define StepsperRevolution 200 //Steppers
#define MicrostepsPerStep 1 //Steppers
//    Setup measurements
#define WallWheelCircumference (109*1000) //in microns (1mm is 1000 microns)
#define wheelRadius (53*1000) //wheel radius in microns (1mm is 1000 microns)
#define wheelDiameter ((float)wheelRadius*2*PI)
#define DistancePerStep ((float)wheelDiameter/nSteps) 

// Variables
int pwmOutput = pwmBaseline;
volatile bool DetectChange = false;
volatile int Direction = 0;
volatile static float TotalDistanceInMM = 0.00;
volatile static float CurrentSpeed = 0.00;
static int previousTargetVelocity = 0;
int targetVelocity = 0;
//    Time variables
volatile uint32_t WallStartTime = 0;  //Timestamp for wall movement start
volatile uint32_t SampleStartTime = 0; 
volatile uint32_t SampleStopTime = 0;
volatile uint32_t ElapsedTime = 0;
uint32_t TimeNoChange = 0;
uint32_t ElapsedTimeNoChange = 0;

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

float mapfloat(float x, float in_min, float in_max, float out_min, float out_max) {
  return (x-in_min) * (out_max-out_min) / (in_max - in_min) + out_min;
}

void MeasureRotations() {
  DetectChange = true;
  if (digitalRead(encAPin) == digitalRead(encBPin)) {
  Direction = FW;
  } else {
  Direction = BW;
  }
  TotalDistanceInMM += DistancePerStep/1000;
  SampleStopTime = micros(); //in ms
  ElapsedTime = SampleStopTime-SampleStartTime;
  SampleStartTime = SampleStopTime;
  CurrentSpeed = (float)DistancePerStep/ElapsedTime*Direction; //in microm/micros 
}

int calculateTargetVelocity(float speed) {
  // Calculate Wall-Wheel revolutions per second (based on treadmill speed)
  float wheelRevolutionsPerSecond = (speed*1000000)/WallWheelCircumference;
  // Convert Wall-Wheel revolutions to motor steps per second
  float motorStepsPerSecond = wheelRevolutionsPerSecond*StepsperRevolution;
  // Convert steps to microsteps per second
  float microstepsPerSecond = motorStepsPerSecond*MicrostepsPerStep;
  
  return microstepsPerSecond*10000;
}

void SynchWalls() {
  if (DetectChange == true) {
    targetVelocity = calculateTargetVelocity(CurrentSpeed);
    if (targetVelocity != previousTargetVelocity) {
      tic1.setTargetVelocity(targetVelocity);
      tic2.setTargetVelocity(targetVelocity*-1);
      previousTargetVelocity = targetVelocity;

      WallStartTime = micros();  // Record wall movement start time
      uint32_t delay = (WallStartTime - SampleStopTime)/1000;
      Serial.print("Delay (ms): ");
      Serial.println(delay);  // Log the delay in milliseconds
    }
    DetectChange = false;
  } else if (DetectChange == false) {
    TimeNoChange = micros();
    ElapsedTimeNoChange = TimeNoChange-SampleStartTime;
    if (ElapsedTimeNoChange > RunningTimeout && TimeNoChange > SampleStopTime) {
      CurrentSpeed=0.00;
      Direction = 0;
      DetectChange=true;
    }
  }
}

void StreamData() {
  pwmOutput = mapfloat(CurrentSpeed, MinRunningSpeed, MaxRunningSpeed, 0, MaxPWMValue);
  pwmOutput = constrain(pwmOutput, 0, MaxPWMValue);
  analogWrite(AnalogDataStreamPin, pwmOutput);

  //Serial.print(CurrentSpeed);
  //Serial.print(",");
  //Serial.print(pwmOutput);
  //Serial.print(",");
  //Serial.println(TotalDistanceInMM);
}


void setup() {
  //ticSerial.begin(9600);
  ticSerial.begin(115385);
  //Serial.begin(9600);
  //Serial.begin(115385);
  analogWriteResolution(12);

  pinMode(encAPin, INPUT_PULLUP);
  pinMode(encBPin, INPUT_PULLUP);
  //pinMode(AnalogDataStreamPin, OUTPUT);

  // Give the Tic some time to start up.
  delay(20);
  // Tells the Tic that it is OK to start driving the motor.
  tic1.exitSafeStart();
  tic2.exitSafeStart();

  attachInterrupt(digitalPinToInterrupt(encAPin), MeasureRotations, RISING);
  SampleStartTime = micros();
}

void loop() {
  SynchWalls();
  StreamData();
  resetCommandTimeout();
}