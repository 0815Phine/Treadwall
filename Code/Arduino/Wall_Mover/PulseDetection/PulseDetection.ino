#define analogIn A0
#define THRESHOLD 512   // Analog threshold for detecting a pulse
volatile int pulseCount = 0; // Count of detected pulses
int lastAnalogValue = 0; // Last analog value read
bool pulseDetected = false; // Flag to indicate if a pulse was detected

void setup() {
  // Set the baud rate for serial communication.
  Serial.begin(9600);

  // Initialize the analog input pin.
  pinMode(analogIn, INPUT);

  // Initialize the last analog value.
  lastAnalogValue = analogRead(analogIn);
}

void loop() {
  // Read the analog input
  int analogValue = analogRead(analogIn);

  // Detect rising edge
  if (analogValue > THRESHOLD && lastAnalogValue <= THRESHOLD) {
    pulseDetected = true;
    pulseCount++;
  }
  
  // Detect falling edge
  if (analogValue < THRESHOLD && lastAnalogValue >= THRESHOLD) {
    pulseDetected = true;
    pulseCount--;
  }

  // Update the last analog value
  lastAnalogValue = analogValue;

  // Print pulse count for debugging
  if (pulseDetected) {
    Serial.print("Pulse Count: ");
    Serial.println(pulseCount);
    pulseDetected = false;
  }

  // Small delay to stabilize the reading
  delay(10);
}