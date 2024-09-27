int sensorPin = A0;   // select the input pin for the potentiometer
int ledPin = 13;      // select the pin for the LED

int sensorValue = 0;
int sensorValueOn = 0;
int sensorValueOff = 0;
float sensorVoltage = 0;
volatile static float Distance = 0.00;

// the following variables have to be adjusted to the end settings and material
#define MinVoltage 0
#define MaxVoltage 2.7
#define MinDistance 0 // in mm
#define MaxDistance 32.5 // in mm

float mapfloat(float x, float in_min, float in_max, float out_min, float out_max) {
  return (x-in_min) * (out_max-out_min) / (in_max - in_min) + out_min;
}

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
  sensorValue = sensorValueOn - sensorValueOff;
  //sensorValue = sensorValueOn;
  sensorVoltage = sensorValue * (5.0 / 1023.0);
  Distance = mapfloat(sensorVoltage, MinVoltage, MaxVoltage, MinDistance, MaxDistance);
  Serial.print("sensor = ");
  Serial.println(sensorVoltage);
  Serial.print("Distance in mm = ");
  Serial.println(Distance);
}


void setup() {
  pinMode(ledPin, OUTPUT); // declare the ledPin as an OUTPUT:
  Serial.begin(9600);
}

void loop() {
  PulseTrain();
  StreamData();
}