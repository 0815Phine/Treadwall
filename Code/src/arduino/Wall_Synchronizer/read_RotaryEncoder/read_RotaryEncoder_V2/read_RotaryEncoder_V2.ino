int encAPin = 2;
int encBPin = 4;

volatile bool DetectChange = false;
volatile int encoder0Pos = 0;
volatile int Direction = 0;

void doEncoder() {
  DetectChange = true;

  if (digitalRead(encAPin) == digitalRead(encBPin)) {
    encoder0Pos -- ;
    Direction = -1;
  } else {
    encoder0Pos ++ ;
    Direction = 1;
  }
}

void setup() {
  Serial.begin(9600);
  pinMode(encAPin, INPUT_PULLUP);
  pinMode(encBPin, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(encAPin), doEncoder, RISING);
}

void loop() {
  if (DetectChange == true) {
    Serial.print("Position: ");
    Serial.println(encoder0Pos);
    Serial.println(Direction);

    DetectChange = false;
  }
}
