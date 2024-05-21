int encAPin = 2;
int encBPin = 4;

double PulsperMil = 3.2;

volatile bool DetectChange = false;
volatile int encoder0Pos = 0;
volatile int Direction = 0;
long newposition;
long oldposition = encoder0Pos; 
unsigned long currenttime;
unsigned long oldtime = 0;
long dist = 0;
long speed = 0;

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
    currenttime = millis();
    //Serial.println(currenttime);

    // Distance in mm
    newposition = encoder0Pos;
    dist = (abs(oldposition-newposition))/PulsperMil;
    Serial.print("Distance [mm]: ");
    Serial.println(dist);
    oldposition = newposition;

    // Speed in mm/s
    speed = dist*1000/(currenttime-oldtime);
    Serial.print("Speed [mm/s]: ");
    Serial.println(speed);
    oldtime = currenttime;

    //Serial.print("Position: ");
    //Serial.println(encoder0Pos);
    Serial.println(Direction);

    DetectChange = false;
    delay(500);
  }
}
