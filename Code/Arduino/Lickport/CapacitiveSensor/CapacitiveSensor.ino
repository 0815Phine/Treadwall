#include <CapacitiveSensor.h>

// Logic:
// detect running and measure distance
// if a certain distance crossed dispense reward after random time in a window in which animal is moving
// simultaneously detect licks

// CONSTANTS
//    Arduino pins:
#define lickOut 12
#define encAPin 2 //Encoder A - Arduino pin 2 to Black
#define encBPin 4 //Encoder B - Arduino pin 4 to White
#define Pump 3 //
CapacitiveSensor cs_7_8 = CapacitiveSensor(7,8); //10M Resistor between pins 7 and 8 -> connect antenna on pin 8
//
#define RunningTimeout 5000
#define minDist 150 //minimum distance to deliver reward in mm
#define minProb 0 //minimum probabiliyt to deliver reward
//    Hardware measurements:
#define nSteps 1024 //Rotary Encoder: number of steps per rotation
#define wheelRadius 53 //wheel radius in microns in mm
#define wheelCircumference ((float)wheelRadius*2*PI)
#define DistancePerStep ((float)wheelCircumference/nSteps) 

// VARIABLES
//    Time variables
volatile uint32_t SampleStartTime = 0; 
volatile uint32_t SampleStopTime = 0;
volatile uint32_t ElapsedTime = 0;
uint32_t TimeNoChange = 0;
uint32_t ElapsedTimeNoChange = 0;
//
unsigned long csSum; // This variable stores accumulates capacitive values till reaching a threshold
volatile bool DetectChange = false;
volatile static float TotalDistanceInMM = 0.00;
int prob = 0;

// Read capacitive sensor
void CapacitiveSensorRead() {
  long cs = cs_7_8.capacitiveSensor(80); // Sensor resolution is set to 80; will store the capacitance as an arbitrary value
	if (cs > 100) { //Arbitrary number; lower threshold
		csSum += cs; // Same as csSum = csSum + cs ; cumulative value for reachiung threshold
		//Serial.println(cs); 
		if (csSum >= 3800) //Testing if csSum reached threshold, a High value means it takes longer to trigger
		{
			Serial.print("Trigger: ");
			Serial.println(csSum);
      TTLout();
      DeliverReward();
			if (csSum > 0) { csSum = 0; } //Reset of csSum
			cs_7_8.reset_CS_AutoCal(); //Stops readings and recalibration of capacitive sensor
		}
	} else {
		csSum = 0; //Timeout caused by bad readings
	}
}

// Send lick events
void TTLout() {
  digitalWrite(lickOut, HIGH);
  delay(1);
  digitalWrite(lickOut, LOW);
}

// Detect movement and save distance
void MeasureRotations() {
  DetectChange = true;
  if (digitalRead(encAPin) == digitalRead(encBPin)) {
  TotalDistanceInMM += DistancePerStep;
  } else {
  TotalDistanceInMM -= DistancePerStep;
  }
  SampleStopTime = micros(); //in ms
  ElapsedTime = SampleStopTime-SampleStartTime;
  SampleStartTime = SampleStopTime;
}

// Start pump
void DeliverReward() {
  if (TotalDistanceInMM >= minDist) {
    Serial.println("Distance reached");
    prob = random(0,100); //probability of reward delivery
    Serial.print("Set probability:");
    Serial.println(prob);
    if (DetectChange == true) {
      if (prob >= minProb) {
        Serial.println("Deliver Reward");
        digitalWrite(Pump, HIGH);
        TotalDistanceInMM = 0; //reset distance count
      }
    } else if (DetectChange == false) {
      TimeNoChange = micros();
      ElapsedTimeNoChange = TimeNoChange-SampleStartTime;
      if (ElapsedTimeNoChange > RunningTimeout && TimeNoChange > SampleStopTime) {
        DetectChange=true;
      }
    }
  }
}


void setup() {
  Serial.begin(9600);
  pinMode(lickOut, OUTPUT);
  pinMode(Pump, OUTPUT);
  pinMode(encAPin, INPUT_PULLUP);
  pinMode(encBPin, INPUT_PULLUP);

  attachInterrupt(digitalPinToInterrupt(encAPin), MeasureRotations, RISING);
  SampleStartTime = micros();
}

void loop() {
  CapacitiveSensorRead();
}
