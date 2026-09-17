#include <CapacitiveSensor.h>

// Logic:
// detect running and measure distance
// if a certain distance crossed dispense reward after random time in a window in which animal is moving
// simultaneously detect licks

// Sensor Setup
CapacitiveSensor cs_7_8 = CapacitiveSensor(7,8); //10M Resistor between pins 7 and 8 -> connect antenna on pin 8
#define SENSRES 80 // Sensor resolution is set to 80; will store the capacitance as an arbitrary value
#define LICKTH 1000 //Changed by AXEL from 100 to 1000 (arbitrary number)
#define CSTH 3800 //cs_sum threshold

// CONSTANTS
//    Arduino pins:
#define LICK_OUT 12
#define ENC_A_PIN 2 //Encoder A - Arduino pin 2 to Black
#define ENC_B_PIN 4 //Encoder B - Arduino pin 4 to White
#define PUMP 3 //
#define CLEAN 13
//    Serial config:
#define BAUD 9600
//    Speed constants:
#define FW 1 //forwards
#define BW -1 //backwards
#define MIN_DIST 150 //minimum distance to deliver reward in mm
#define MIN_PROB 70 //minimum probabiliyt to deliver reward
//    Timings
#define LICKTTLOUT 1 //length of TTL pulse in ms
#define PUMPONDUR 3 //length of pump being powered in ms
//    Hardware measurements:
#define N_STEPS 1024 //Rotary Encoder: number of steps per rotation
#define WHEEL_RADIUS 53 //wheel radius in microns in mm
#define WHEEL_CIRCUMFERENCE ((float)WHEEL_RADIUS*2*PI)
#define DISTANCE_PER_STEP ((float)WHEEL_CIRCUMFERENCE/N_STEPS)

// VARIABLES
//    Time variables
volatile uint32_t sample_start_time = 0;
volatile uint32_t sample_stop_time = 0;
volatile uint32_t elapsed_time = 0;
uint32_t time_no_change = 0;
uint32_t elapsed_time_no_change = 0;
//
unsigned long cs_sum; // This variable stores accumulates capacitive values till reaching a threshold
volatile bool detect_change = false;
volatile static float total_distance_in_mm = 0.00;
volatile bool distance_flag = false;
volatile int direction = 0;
int prob = 0;

// Read capacitive sensor
void capacitive_sensor_read() {
  long cs = cs_7_8.capacitiveSensor(SENSRES);
  //Serial.println(total_distance_in_mm);

  if (distance_flag == false) {
    if (total_distance_in_mm >= MIN_DIST) {
      Serial.println("Distance reached");
      distance_flag = true;
    }
  }

	if (cs > LICKTH) {
		cs_sum += cs; // Same as cs_sum = cs_sum + cs ; cumulative value for reachiung threshold
		//Serial.println(cs);
		if (cs_sum >= CSTH) //Testing if cs_sum reached threshold, a High value means it takes longer to trigger
		{
			Serial.print("Trigger: ");
			Serial.println(cs_sum);
      ttl_out();
      deliver_reward();
			if (cs_sum > 0) { cs_sum = 0; } //Reset of cs_sum
			cs_7_8.reset_CS_AutoCal(); //Stops readings and recalibration of capacitive sensor
		}
	} else {
		cs_sum = 0; //Timeout caused by bad readings
	}
  reset_change();
}

// Send lick events
void ttl_out() {
  digitalWrite(LICK_OUT, HIGH);
  delay(LICKTTLOUT);
  digitalWrite(LICK_OUT, LOW);
}

// Detect movement and save distance
void measure_rotations() {
  detect_change = true;
  if (digitalRead(ENC_A_PIN) == digitalRead(ENC_B_PIN)) {
  total_distance_in_mm += DISTANCE_PER_STEP;
  direction = FW;
  } else {
  total_distance_in_mm -= DISTANCE_PER_STEP;
  direction = BW;
  }
  sample_stop_time = micros(); //in ms
  elapsed_time = sample_stop_time-sample_start_time;
  sample_start_time = sample_stop_time;
}

// Start pump
void deliver_reward() {
  if (detect_change == true && direction == FW) {
    if (total_distance_in_mm >= MIN_DIST) {
      prob = random(0,100); //probability of reward delivery
      Serial.print("Set probability:");
      Serial.println(prob);
      if (prob >= MIN_PROB) {
        Serial.println("Deliver Reward");
        digitalWrite(PUMP, HIGH);
        delay(PUMPONDUR);
        digitalWrite(PUMP, LOW);

        total_distance_in_mm = 0; //reset distance count
        distance_flag = false;
      }
    }
  }
}

void reset_change() {
  if (detect_change == true) {
  detect_change = false;
  }
}

void clean_pump() {
  while (digitalRead(CLEAN) == LOW) {
    digitalWrite(PUMP, HIGH);
  }
  digitalWrite(PUMP, LOW);
}

void setup() {
  Serial.begin(BAUD);
  pinMode(LICK_OUT, OUTPUT);
  pinMode(PUMP, OUTPUT);
  pinMode(ENC_A_PIN, INPUT_PULLUP);
  pinMode(ENC_B_PIN, INPUT_PULLUP);
  pinMode(CLEAN, INPUT_PULLUP);

  attachInterrupt(digitalPinToInterrupt(ENC_A_PIN), measure_rotations, RISING);
  sample_start_time = micros();
}

void loop() {
  capacitive_sensor_read();
  if (digitalRead(CLEAN) == LOW) {
    clean_pump();
  }
  //delay(5);
}
