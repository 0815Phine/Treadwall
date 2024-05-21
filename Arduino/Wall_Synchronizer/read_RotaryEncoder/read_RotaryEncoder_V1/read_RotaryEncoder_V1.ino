int encOutA = 2;
int encOutB = 4;
int aLastState = 0;
int aState = 0;
int counter = 0;

void setup() {
  pinMode(encOutA, INPUT);
  pinMode(encOutB, INPUT);
  
  Serial.begin(9600);
  
  aLastState = digitalRead(encOutA); // Reads the initial state of the encOutA
}

void loop() {
  aState = digitalRead(encOutA); // Reads the "current" state of the encOutA
   // If the previous and the current state of the encOutA are different, that means a Pulse has occured
   if (aState != aLastState) {     
     // If the encOutB state is different to the encOutA state, that means the encoder is rotating clockwise
     if (digitalRead(encOutB) != aState) { 
       counter ++;
     } else {
       counter --;
     }
     Serial.print("Position: ");
     Serial.println(counter);
   } 
   aLastState = aState; // Updates the previous state of the encOutA with the current state
}
