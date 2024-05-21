#define version "1"

//Rotary encoder setup:
//  Encoder A - pin 2 Black
//  Encoder B - pin 4 White
//  Encoder Z - NC    Orange
//  Encoder VCC - 5V Brown
//  Encoder ground GND Blue (0V common) and Shield
//Resolution 1024 P/R

#define encAPin 2
#define encBPin 4
#define servoPin 9
#define AnalogDataStreamPin 11

#define MaxRunningSpeed 2 // in m/s
#define MinRunningSpeed (MaxRunningSpeed*-1)
#define RunningTimeout 500000
#define MaxAnalogOut 5.0 //Maximum of 5V analog output for data stream
#define MaxPWMValue 255 //Value to generate 5V with PWM
#define nSteps 1024 //number of steps per rotation
#define wheelRadius (100*1000) //wheel radius in mm (1mm is 1000 microns) makes it easer to calculate speed later
#define wheelDiameter ((float)wheelRadius*2*PI)
#define DistancePerStep ((float)wheelDiameter/nSteps)

#define FW 1 //code for forward direction rotation
#define BW -1 //same for backwards

#define AnalogBaseline 2.5 //Baseline for Analog signal is 2.5 to also encode BW motion
#define pwmBaseline 127

volatile int Direction = 0;
volatile bool DetectChange = false;
volatile uint32_t SampleStartTime=0;
volatile uint32_t SampleStopTime=0;
volatile uint32_t ElapsedTime=0;
volatile static float CurrentSpeed=0.00;
volatile static float TotalDistanceInMM=0.00;

uint32_t TimeNoChange=0;
uint32_t ElapsedTimeNoChange=0;
float AnalogOutput = AnalogBaseline;
int pwmOutput = pwmBaseline;
int WallSpeed = 95;
int pwmSynch = pwmBaseline;

#include "Servo.h" // Include the servo library
Servo myservo;  // create servo object to control our servo

float mapfloat(float x, float in_min, float in_max, float out_min, float out_max) {
  return (x-in_min) * (out_max-out_min) / (in_max - in_min) + out_min;
}

void MeasureRotations() {
  DetectChange = true;
  if (digitalRead(encAPin) == digitalRead(encBPin)) {
  Direction = BW;
  } else {
  Direction = FW;
  }
  TotalDistanceInMM += DistancePerStep/1000;
  SampleStopTime = micros();
  ElapsedTime = SampleStopTime-SampleStartTime;
  SampleStartTime = SampleStopTime;
  CurrentSpeed = (float)DistancePerStep/ElapsedTime*Direction; // microns/microseconds equals m/s negative means BW positive means FW
}

void setup() {
  Serial.begin(9600);
  
  pinMode(encAPin, INPUT_PULLUP);
  pinMode(encBPin, INPUT_PULLUP);
  pinMode(AnalogDataStreamPin, OUTPUT);

  delay(500);
  Serial.print("Trashcan Interface Version: ");
  Serial.println(version);
  Serial.println("Speed_MS; AnalogOut_V; PWMOut; Direction; TotalDistance_MM");
  delay(500);

  attachInterrupt(digitalPinToInterrupt(encAPin), MeasureRotations, RISING);
  myservo.attach(servoPin);  // attaches the servo on pin 9 to the servo object
  myservo.write(95);
  SampleStartTime = micros();
}

void loop() {
  //noInterrupts();
  StreamData();
  SynchWalls();
  //interrupts();
}

void StreamData() {
  if (DetectChange == true) {
    AnalogOutput = mapfloat(CurrentSpeed, MinRunningSpeed, MaxRunningSpeed, 0.00, MaxAnalogOut);
    AnalogOutput = constrain(AnalogOutput, 0.00, MaxAnalogOut);
    pwmOutput = mapfloat(CurrentSpeed, MinRunningSpeed, MaxRunningSpeed, 0, MaxPWMValue);
    pwmOutput = constrain(pwmOutput, 0, MaxPWMValue);
    Serial.print(CurrentSpeed);
    Serial.print("; ");
    Serial.print(AnalogOutput);
    Serial.print("; ");
    Serial.print(pwmOutput);
    Serial.print("; ");
    Serial.print(Direction);
    Serial.print("; ");
    Serial.println(TotalDistanceInMM);
    analogWrite(AnalogDataStreamPin, pwmOutput);
    DetectChange = false;
  } else if (DetectChange == false) {
    TimeNoChange = micros();
    ElapsedTimeNoChange = TimeNoChange-SampleStartTime;
    if (ElapsedTimeNoChange > RunningTimeout && TimeNoChange > SampleStopTime) {
      CurrentSpeed=0.00;
      DetectChange=true;
    }
  }
}

void SynchWalls() {
  if (pwmSynch != pwmOutput) {
    WallSpeed = map(pwmOutput, 0, 255, 0, 190);
    myservo.write(WallSpeed);
    pwmSynch=pwmOutput;
  }
}
