// Constants
//    Arduino pins:
#define sensorPinright A0  // VOut optical sensor right
#define ledPinright 13     // pulse optical sensor right
#define sensorPinleft A1   // VOut optical sensor left
#define ledPinleft 12      // pulse optical sensor left
#define DataStreamright 11 // PWM pin 
#define DataStreamleft 10  // PWm pin
//    
#define MinDistance_left 11 // in mm
#define MinDistance_right 10 // in mm
#define MaxDistance_left 32 // in mm
#define MaxDistance_right 31 // in mm 
#define MaxPWMValue 255 // value to generate 5V with PWM

// Variables
int pwmOutput_right = 0;
int pwmOutput_left = 0;
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

// Constants and Variables from Tuning Curve. Currently have to be hardcoded her (in increasing order of x_axis = voltage).
// Alternative: Connect SD card with CSV-File to Arduino and read directly from there
// had to remove the 'baseline' voltage value as this would interfere with the interpolation
#define NUM_POINTS 8
float distances_left[NUM_POINTS] = {11, 14, 17, 20, 23, 26, 29, 32};  // Distances in mm
float voltages_left[NUM_POINTS] = {2834.8, 2976.54, 3044.97, 3098.73, 3172.04, 3191.54, 3196.48, 3201.37};  // Average voltages (mV)
float distances_right[NUM_POINTS] = {10, 13, 16, 19, 22, 25, 28, 31};  // Distances in mm
float voltages_right[NUM_POINTS] = {430.11, 483.87, 513.20, 537.63, 566.96, 615.84, 645.16, 659.82};  // Average voltages (mV)

float mapfloat(float x, float in_min, float in_max, float out_min, float out_max) {
  return (x-in_min) * (out_max-out_min) / (in_max - in_min) + out_min;
}

float interpolate(float x, float* x_points, float* y_points, int num_points) {
  if (x <= x_points[0]) return y_points[0];  // Below range
  if (x >= x_points[num_points - 1]) return y_points[num_points - 1]; // Above range
  
  for (int i = 0; i < num_points - 1; i++) {
    if (x >= x_points[i] && x <= x_points[i + 1]) {
      // Linear interpolation
      return y_points[i] + (x - x_points[i]) * (y_points[i + 1] - y_points[i]) / (x_points[i + 1] - x_points[i]);
    }
  }
  return y_points[0];  // Fallback (shouldn't reach here)
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
  delay(0.7);

  // read the value from the sensors:
  buffersensVal = analogRead(sensorPinright);
  delay(0.1);
  sensValOffR = analogRead(sensorPinright); // repeat read to give multiplexer time to switch
  delay(0.1);
  buffersensVal = analogRead(sensorPinleft);
  delay(0.1);
  sensValOffL = analogRead(sensorPinleft); // repeat read to give multiplexer time to switch
}

void StreamData() {
  sensValR = sensValOnR - sensValOffR;
  sensVoltageR = sensValR * (5.0 / 1023.0)*1000;
  sensValL = sensValOnL - sensValOffL;
  sensVoltageL = sensValL * (5.0 / 1023.0)*1000;

  Distance_right = interpolate(sensVoltageR, voltages_right, distances_right, NUM_POINTS);
  Distance_left = interpolate(sensVoltageL, voltages_left, distances_left, NUM_POINTS);

  // Analog Stream:
  pwmOutput_right = mapfloat(Distance_right, MinDistance_right, MaxDistance_right, 0, MaxPWMValue);
  pwmOutput_right = constrain(pwmOutput_right, 0, MaxPWMValue);
  analogWrite(DataStreamright, pwmOutput_right);
  //Serial.print("PWM Output right: ");
  //Serial.println(pwmOutput_right);

  pwmOutput_left = mapfloat(Distance_left, MinDistance_left, MaxDistance_left, 0, MaxPWMValue);
  pwmOutput_left = constrain(pwmOutput_left, 0, MaxPWMValue);
  analogWrite(DataStreamleft, pwmOutput_left);
  //Serial.print("PWM Output left: ");
  //Serial.println(pwmOutput_left);
  //delay(500);
}

void SerialStream() {
  //Serial.print("sensor right= ");
  Serial.println(sensVoltageR);
  //Serial.print("Distance in mm right Side = ");
  //Serial.print(Distance_right);

  Serial.print(",");

  //Serial.print("sensor left= ");
  Serial.println(sensVoltageL);
  //Serial.print("Distance in mm left Side = ");
  //Serial.println(Distance_left);
  //delay(1000);
}


void setup() {
  pinMode(ledPinright, OUTPUT);
  pinMode(ledPinleft, OUTPUT);
  Serial.begin(9600);
}

void loop() {
  PulseTrain();
  StreamData();
  SerialStream();
}