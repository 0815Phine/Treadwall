// Constants
//    Arduino pins:
#define sensorPinright A0  // VOut optical sensor right
#define ledPinright 11     // pulse optical sensor right
#define sensorPinleft A1   // VOut optical sensor left
#define ledPinleft 10      // pulse optical sensor left
#define DataStreamright 13 // PWM pin 
#define DataStreamleft 12  // PWm pin
//    
#define MinDistance_left 11 // in mm
#define MinDistance_right 10 // in mm
#define MaxDistance_left 32 // in mm
#define MaxDistance_right 31 // in mm 
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

// Constants and Variables from Tuning Curve. Currently have to be hardcoded her (in increasing order of x_axis = voltage).
// Alternative: Connect SD card with CSV-File to Arduino and read directly from there
// had to remove the 'baseline' voltage value as this would interfere with the interpolation
#define NUM_POINTS 8
float distances_left[NUM_POINTS] = {11, 14, 17, 20, 23, 26, 29, 32};  // Distances in mm
float voltages_left[NUM_POINTS] = {2923.99, 3026.64, 3103.62, 3173.27, 3227.03, 3233.75, 3241.69, 3242.94};  // Average voltages (mV)
float distances_right[NUM_POINTS] = {10, 13, 16, 19, 22, 25, 28, 31};  // Distances in mm
float voltages_right[NUM_POINTS] = {481.43, 540.08, 572.46, 593.85, 636.6, 676.92, 713.59, 733.14};  // Average voltages (mV)

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
  //delay(0.2);
}

void StreamData() {
  sensValR = sensValOnR - sensValOffR;
  sensVoltageR = sensValR * (5.0 / 1023.0)*1000;
  sensValL = sensValOnL - sensValOffL;
  sensVoltageL = sensValL * (5.0 / 1023.0)*1000;

  Distance_right = interpolate(sensVoltageR, voltages_right, distances_right, NUM_POINTS);
  Distance_left = interpolate(sensVoltageL, voltages_left, distances_left, NUM_POINTS);

  // Analog Stream:
  pwmOutput = mapfloat(Distance_right, MinDistance_right, MaxDistance_right, 0, MaxPWMValue);
  pwmOutput = constrain(pwmOutput, 0, MaxPWMValue);
  analogWrite(DataStreamright, pwmOutput);

  pwmOutput = mapfloat(Distance_left, MinDistance_left, MaxDistance_left, 0, MaxPWMValue);
  pwmOutput = constrain(pwmOutput, 0, MaxPWMValue);
  analogWrite(DataStreamleft, pwmOutput);
}

void SerialStream() {
  Serial.print("sensor right= ");
  Serial.println(sensVoltageR);
  Serial.print("Distance in mm right Side = ");
  Serial.println(Distance_right);

  Serial.print("sensor left= ");
  Serial.println(sensVoltageL);
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
  //SerialStream();
}