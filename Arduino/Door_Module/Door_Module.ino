/* Modular Door for Behavioral Arenas
 by Benjamin Escribano at CADRE University of Bonn

 https://ibehave.nrw/ibots-platform/ibots-make/

Created 03.05.2024
*/

#include <Servo.h>
#define DoorControlPin 2 //Definition of the pin that receives a TTL signal to control the door position
#define SyncPin1 3
#define SyncPin2 12
#define ServoPin 9 //Definition of the pin attached to the servo
#define DoorPosUp 5 // Definition of the door position in the upper state
#define DoorPosDown 74 // Definition of the door position in the lower state
#define Version 1
#define DoorDelay 50 //Delay between each door movement step. Inverse correlation with movement speed.

Servo myservo;  // create servo object to control a servo

int pos = 0;    // variable to store the servo position
int CurrentDoorPos = 0; //Variable for reading and saving current door position
int DoorPositionInput = 0;
//SynchValueint SynchValue = 0;
volatile bool InputChangeDetected = false;

void setup() {
  Serial.begin(115200);
  myservo.attach(ServoPin);  // attaches the servo on pin 9 to the servo object
  delay(50);
  myservo.write(DoorPosUp); // Brings the door up as a closed resting state
  delay(50);
  CurrentDoorPos = myservo.read();
  delay(50);
  pinMode(DoorControlPin, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(DoorControlPin), detectChangeDoorControl, CHANGE);
  delay(50);
  pinMode(SyncPin1, OUTPUT);
  pinMode(SyncPin2, OUTPUT);
  digitalWrite(SyncPin1, HIGH);
  digitalWrite(SyncPin2, HIGH);
  delay(50);
  Serial.println(" ");
  Serial.print("Start Modular Door Serial Interface Version ");
  Serial.println(Version);
  Serial.print("Door Position Up: ");
  Serial.println(CurrentDoorPos);
}

void loop() {
  //noInterrupts(); // noInterrupts will break the delay and move doors very fast...
  moveDoorOnChange();
  //interrupts(); 
}

void moveDoorOnChange() {
  if (InputChangeDetected==true) {
    Serial.print("Change Detected; Input: ");
    DoorPositionInput = digitalRead(DoorControlPin);
    Serial.println(DoorPositionInput);
    if (DoorPositionInput == HIGH) {
      SynchOutput(DoorPositionInput); 
      for (pos = CurrentDoorPos; pos >= DoorPosUp; pos -= 1) {
        myservo.write(pos);
        delay(DoorDelay);
        }
      CurrentDoorPos = myservo.read();
      Serial.print("Door Position Up: ");
      Serial.println(CurrentDoorPos);
    } else {
      SynchOutput(DoorPositionInput);
      for (pos = CurrentDoorPos; pos <= DoorPosDown; pos += 1) {
        myservo.write(pos);
        delay(DoorDelay);
        }
      CurrentDoorPos = myservo.read();
      Serial.print("Door Position Down: ");
      Serial.println(CurrentDoorPos);
    }
    InputChangeDetected = false; //Reset Change Detection
  }
}

void SynchOutput(int SynchValue) {
    int State = SynchValue;
    digitalWrite(SyncPin1, State);
    digitalWrite(SyncPin2, State);
}

void detectChangeDoorControl() {
  InputChangeDetected = true;
}