#include <CapacitiveSensor.h>
CapacitiveSensor cs_7_8 = CapacitiveSensor(7,8); //10M Resistor between pins 7 and 8, you may also connect an antenna on pin 8. If the antenna is connected to pin 7 it will sense touch-release...
unsigned long csSum; // This variable stores accumulates capacitive values till reaching a threshold

void setup() {
    Serial.begin(9600); // Begin serial communication
    pinMode(12, OUTPUT); //LED (to signal touches) is on pin 12 
}

void loop() {
    CapacitiveSensorRead(); // This time we put everything in a function
}

void CapacitiveSensorRead() {
    long cs = cs_7_8.capacitiveSensor(80); // Sensor resolution is set to 80; will store the capacitance as an arbitrary value
	if (cs > 100) { //Arbitrary number; lower threshold
		csSum += cs; // Same as csSum = csSum + cs ; cumulative value for reachiung threshold
		//Serial.println(cs); 
		if (csSum >= 3800) //Testing if csSum reached threshold, a High value means it takes longer to trigger
		{
			//Serial.print("Trigger: ");
			//Serial.println(csSum);
      TTLout();
			if (csSum > 0) { csSum = 0; } //Reset of csSum
			cs_7_8.reset_CS_AutoCal(); //Stops readings and recalibration of capacitive sensor
		}
	} else {
		csSum = 0; //Timeout caused by bad readings
	}
}

void TTLout() {
      digitalWrite(12, HIGH);  //  if a lick is detected, turn LED ON.
      delay(1);
      digitalWrite(12, LOW);  //  turn the LED OFF.
  }