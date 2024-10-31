// Constants
//    Arduino pins:
#define sensorPinright A1  // VOut optical sensor right
#define ledPinright 10     // pulse optical sensor right
#define sensorPinleft A0   // VOut optical sensor left
#define ledPinleft 11      // pulse optical sensor left
#define DataStreamright 12 // PWM pin 
#define DataStreamleft 13  // PWm pin

// Variables
float maxVoltageR = 0.0;
float maxVoltageL = 0.0;

int sensValR = 0;
int sensValOnR = 0;
int sensValOffR = 0;
int sensValL = 0;
int sensValOnL = 0;
int sensValOffL = 0;
int buffersensVal = 0;
float sensVoltageR = 0;
float sensVoltageL = 0;

void PulseTrain(){
  // turn the ledPin on
  digitalWrite(ledPinright, HIGH);
  delay(0.2);
  digitalWrite(ledPinleft, HIGH);
  delay(0.1);

  // read the value from the sensors:
  buffersensVal = analogRead(sensorPinright);
  delay(0.1);
  sensValOnR = analogRead(sensorPinright); //repeat read to give multiplexer time to switch
  delay(0.1);
  buffersensVal = analogRead(sensorPinleft);
  delay(0.1);
  sensValOnL = analogRead(sensorPinleft); //repeat read to give multiplexer time to switch
  delay(0.2);

  // turn the ledPin off:
  digitalWrite(ledPinright, LOW);
  delay(0.2);
  digitalWrite(ledPinleft, LOW);
  delay(0.1);

  // read the value from the sensors:
  buffersensVal = analogRead(sensorPinright);
  delay(0.1);
  sensValOffR = analogRead(sensorPinright); // repeat read to give multiplexer time to switch
  delay(0.1);
  buffersensVal = analogRead(sensorPinleft);
  delay(0.1);
  sensValOffL = analogRead(sensorPinleft); // repeat read to give multiplexer time to switch
  delay(0.6);
}

void StreamData() {
  sensValR = sensValOnR - sensValOffR;
  sensVoltageR = sensValR * (5.0 / 1023.0);
  sensValL = sensValOnL - sensValOffL;
  sensVoltageL = sensValL * (5.0 / 1023.0);
  
  // Update maximum voltage values if new peak is detected
  if (sensVoltageR > maxVoltageR) {
    maxVoltageR = sensVoltageR;
  }
  if (sensVoltageL > maxVoltageL) {
    maxVoltageL = sensVoltageL;
  }
}


void setup() {
  pinMode(ledPinright, OUTPUT);
  pinMode(ledPinleft, OUTPUT);
  Serial.begin(9600);
}

void loop() {
  PulseTrain();
  StreamData();
}