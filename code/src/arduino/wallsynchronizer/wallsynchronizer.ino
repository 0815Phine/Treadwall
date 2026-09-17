#include <Tic.h>
#include <SoftwareSerial.h>

// Tic Setup
SoftwareSerial tic_serial(10, 11); //pin 10 to Driver TX; pin 11 to Driver RX
TicSerial tic1(tic_serial, 14);
TicSerial tic2(tic_serial, 15);

// Constants
//    Arduino pins:
#define ANALOG_DATA_STREAM_PIN A0
#define ENC_A_PIN 2 //Encoder A - Arduino pin 2 to Black
#define ENC_B_PIN 4 //Encoder B - Arduino pin 4 to White
#define SPEED_PIN 3
//    Serial config:
#define BAUD 115385
#define ANRES 12
//    Data Stream:
#define FW 1 //forwards
#define BW -1 //backwards
#define RUNNING_TIMEOUT 5000
#define MAX_RUNNING_SPEED 1 //in m/s
#define MIN_RUNNING_SPEED (MAX_RUNNING_SPEED*-1)
#define MAX_PWM_VALUE 4095 //Value to generate 5V with PWM
#define PWM_BASELINE 2045
//    Rotary Encoder, Motor specs:
#define N_STEPS 1024 //Rotary Encoder: number of steps per rotation
#define STEPS_PER_REVOLUTION 200 //Steppers
#define MICROSTEPS_PER_STEP 2 //Steppers
//    Setup measurements:
#define WALL_WHEEL_CIRCUMFERENCE (109*1000) //in microns (1mm is 1000 microns), of the roller wheel
#define WHEEL_RADIUS (53*1000) //wheel radius in microns (1mm is 1000 microns)
#define WHEEL_CIRCUMFERENCE ((float)WHEEL_RADIUS*2*PI)
#define DISTANCE_PER_STEP ((float)WHEEL_CIRCUMFERENCE/N_STEPS)

// Variables
int pwm_output = PWM_BASELINE;
volatile bool detect_change = false;
volatile int direction = 0;
volatile static float total_distance_in_mm = 0.00;
volatile static float current_speed = 0.00;
static int previous_target_velocity = 0;
int target_velocity = 0;
float speed_multiplier = 1.0;
//    Time variables
volatile uint32_t wall_start_time = 0;  //Timestamp for wall movement start
volatile uint32_t sample_start_time = 0;
volatile uint32_t sample_stop_time = 0;
volatile uint32_t elapsed_time = 0;
uint32_t time_no_change = 0;
uint32_t elapsed_time_no_change = 0;
//    Scaling
volatile uint32_t pulse_start = 0;
volatile uint32_t pulse_width = 0;
volatile bool new_pulse = false;
volatile float scale_factor = 1.0; // Default scaling factor

// Sends a "Reset command timeout" command to the Tic.
void reset_command_timeout() {
  tic1.resetCommandTimeout();
  tic2.resetCommandTimeout();
}

// Delays for the specified number of milliseconds while resetting the Tic's command timeout so that its movement does not get interrupted.
void delay_while_resetting_command_timeout(uint32_t ms) {
  uint32_t start = millis();
  do {
    reset_command_timeout();
  } while ((uint32_t)(millis()-start) <= ms);
}

float mapfloat(float x, float in_min, float in_max, float out_min, float out_max) {
  return (x-in_min) * (out_max-out_min) / (in_max - in_min) + out_min;
}

void measure_rotations() {
  detect_change = true;
  if (digitalRead(ENC_A_PIN) == digitalRead(ENC_B_PIN)) {
  direction = FW;
  } else {
  direction = BW;
  }
  total_distance_in_mm += DISTANCE_PER_STEP/1000;
  sample_stop_time = micros(); //in ms
  elapsed_time = sample_stop_time-sample_start_time;
  sample_start_time = sample_stop_time;
  current_speed = (float)DISTANCE_PER_STEP/elapsed_time*direction; //in microm/micros
}

int calculate_target_velocity(float speed) {
  if (Serial.available()){
    String input = Serial.readStringUntil('\n');
    speed_multiplier = input.toFloat();
  }
  speed = speed*speed_multiplier;

  // Calculate Wall-Wheel revolutions per second (based on treadmill speed)
  float wheel_revolutions_per_second = (speed*1000000)/WALL_WHEEL_CIRCUMFERENCE;
  // Convert Wall-Wheel revolutions to motor steps per second
  float motor_steps_per_second = wheel_revolutions_per_second*STEPS_PER_REVOLUTION;
  // Convert steps to microsteps per second
  float microsteps_per_second = motor_steps_per_second*MICROSTEPS_PER_STEP;

  return microsteps_per_second*10000;
}

void synch_walls() {
  if (detect_change == true) {
    target_velocity = calculate_target_velocity(current_speed);
    if (target_velocity != previous_target_velocity) {
      tic1.setTargetVelocity(target_velocity);
      tic2.setTargetVelocity(target_velocity*-1);
      previous_target_velocity = target_velocity;

      wall_start_time = micros();  // Record wall movement start time
      uint32_t delay = (wall_start_time - sample_stop_time)/1000;
      //Serial.print("Delay (ms): ");
      //Serial.println(delay);  // Log the delay in milliseconds
    }
    detect_change = false;
  } else if (detect_change == false) {
    time_no_change = micros();
    elapsed_time_no_change = time_no_change-sample_start_time;
    if (elapsed_time_no_change > RUNNING_TIMEOUT && time_no_change > sample_stop_time) {
      current_speed=0.00;
      direction = 0;
      detect_change=true;
    }
  }
}

void stream_data() {
  //pwm_output = mapfloat(current_speed, MIN_RUNNING_SPEED, MAX_RUNNING_SPEED, 0, MAX_PWM_VALUE);
  //pwm_output = constrain(pwm_output, 0, MAX_PWM_VALUE);
  //analogWrite(SPEED_PIN, pwm_output);

  Serial.println(current_speed);
  Serial.println(target_velocity);
  //Serial.print(",");
  //Serial.print(pwm_output);
  //Serial.print(",");
  //Serial.println(total_distance_in_mm);
}


void setup() {
  //tic_serial.begin(9600);
  tic_serial.begin(BAUD);
  //Serial.begin(9600);
  Serial.begin(BAUD);
  analogWriteResolution(ANRES);

  pinMode(ENC_A_PIN, INPUT_PULLUP);
  pinMode(ENC_B_PIN, INPUT_PULLUP);
  //pinMode(SPEED_PIN, OUTPUT);
  //pinMode(ANALOG_DATA_STREAM_PIN, OUTPUT);

  // Give the Tic some time to start up.
  delay(20);
  // Tells the Tic that it is OK to start driving the motor.
  tic1.exitSafeStart();
  tic2.exitSafeStart();

  attachInterrupt(digitalPinToInterrupt(ENC_A_PIN), measure_rotations, RISING);
  sample_start_time = micros();
}

void loop() {
  synch_walls();
  //stream_data();
  reset_command_timeout();
}
