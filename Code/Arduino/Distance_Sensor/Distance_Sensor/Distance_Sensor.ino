int sensorPin = A0;   // select the input pin for the potentiometer
int ledPin = 13;      // select the pin for the LED
int sensorValue = 0;  // variable to store the value coming from the sensor

void setup() {
  // declare the ledPin as an OUTPUT:
  pinMode(ledPin, OUTPUT);
  Serial.begin(9600);
}

void loop() {
  // turn the ledPin on
  digitalWrite(ledPin, HIGH);
  delay(0.4);
  // read the value from the sensor:
  sensorValue = analogRead(sensorPin);
  Serial.print("sensor = ");
  Serial.println(sensorValue);
  delay(0.4);
  // turn the ledPin off:
  digitalWrite(ledPin, LOW);
  delay(1.2);
}