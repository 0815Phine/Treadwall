//    Arduino pins:
#define sensorPin A0  // VOut optical sensor 
#define ledPin 11     // pulse optical sensor 

// Variables
int sensVal = 0;
int sensValOn = 0;
int sensValOff = 0;
int buffersensVal = 0;
float sensVoltage = 0;


void PulseTrain(){
  // turn the ledPin on
  digitalWrite(ledPin, HIGH);
  delay(0.4);
  // read the value from the sensor:
  sensValOn = analogRead(sensorPin);
  delay(0.4);
  // turn the ledPin off:
  digitalWrite(ledPin, LOW);
  delay(0.4);
  // read the value from the sensor:
  sensValOff = analogRead(sensorPin);
  delay(0.8);
}

void StreamData() {
  sensVal = sensValOn - sensValOff;
  sensVoltage = sensVal * (5.0 / 1023.0)*1000; //in mV

  // Send measurements to Serial in CSV format
  Serial.println(sensVoltage);
}


void setup() {
  pinMode(ledPin, OUTPUT);
  Serial.begin(9600);
}

void loop() {
  PulseTrain();
  StreamData();
}