// Constants
//    Arduino pins:
#define sensorPinright A0  // VOut optical sensor right
#define ledPinright 13     // pulse optical sensor right
#define sensorPinleft A1   // VOut optical sensor left
#define ledPinleft 12      // pulse optical sensor left
#define DataStreamright 10 // PWM pin 
#define DataStreamleft 11  // PWm pin
//    the following constants have to be adjusted to the final tuning curve
#define MinVoltage 0
#define MaxVoltage 2.7
#define MinDistance 0 // in mm
#define MaxDistance 32.5 // in mm
#define MaxPWMValue 255 // value to generate 5V with PWM
#define pwmBaseline 127

// Variables
int pwmOutput = pwmBaseline;
int sensValR = 0;
int sensValOnR = 0;
int sensValOffR = 0;
int sensValL = 0;
int sensValOnL = 0;
int sensValOffL = 0;
int buffersensVal = 0;
float sensVoltageR = 0;
float sensVoltageL = 0;
volatile static float Distance_right = 0.00;
volatile static float Distance_left = 0.00;

float mapfloat(float x, float in_min, float in_max, float out_min, float out_max) {
  return (x-in_min) * (out_max-out_min) / (in_max - in_min) + out_min;
}

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

  // Analog Stream:
  //pwmOutput = mapfloat(sensVoltageR, MinVoltage, MaxVoltage, 0, MaxPWMValue);
  //pwmOutput = constrain(pwmOutput, 0, MaxPWMValue);
  //analogWrite(DataStreamright, pwmOutput);

  //pwmOutput = mapfloat(sensVoltageL, MinVoltage, MaxVoltage, 0, MaxPWMValue);
  //pwmOutput = constrain(pwmOutput, 0, MaxPWMValue);
  //analogWrite(DataStreamleft, pwmOutput);

  // Seriel Stream:
  Distance_right = mapfloat(sensVoltageR, MinVoltage, MaxVoltage, MinDistance, MaxDistance);
  //Serial.print("sensor = ");
  //Serial.println(sensorVoltage);
  Serial.print("Distance in mm right Side = ");
  Serial.println(Distance_right);

  Distance_left = mapfloat(sensVoltageL, MinVoltage, MaxVoltage, MinDistance, MaxDistance);
  //Serial.print("sensor = ");
  //Serial.println(sensorVoltage);
  Serial.print("Distance in mm left Side = ");
  Serial.println(Distance_left);
  delay(1000);
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