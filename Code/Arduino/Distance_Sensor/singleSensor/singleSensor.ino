//    Arduino pins:
#define sensorPin A1  // VOut optical sensor 
#define ledPin 10     // pulse optical sensor 

// Variables
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
  digitalWrite(ledPin, HIGH);
  delay(0.4);
  // read the value from the sensor:
  sensorValueOn = analogRead(sensorPin);
  delay(0.4);
  // turn the ledPin off:
  digitalWrite(ledPin, LOW);
  delay(0.4);
  // read the value from the sensor:
  sensorValueOff = analogRead(sensorPin);
  delay(0.8);
}

void StreamData() {
  sensValR = sensValOnR - sensValOffR;
  sensVoltageR = sensValR * (5.0 / 1023.0)*1000; //in mV
  sensValL = sensValOnL - sensValOffL;
  sensVoltageL = sensValL * (5.0 / 1023.0)*1000; //in mV

  // Send measurements to Serial in CSV format
  Serial.print(sensVoltageR);
  Serial.print(",");
  Serial.println(sensVoltageL);
}


void setup() {
  pinMode(ledPin, OUTPUT);
  Serial.begin(9600);
}

void loop() {
  PulseTrain();
  StreamData();
}