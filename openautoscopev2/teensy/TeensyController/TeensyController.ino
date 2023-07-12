// Latest Version @ 2023-03-02
// Latest Use     @ 2023-06-02

// Libraries
#include <AccelStepper.h>

// Ports Catalogue
// # Digital
#define P_ENABLE 6
#define P_RESTSLEEP 2
#define P_M0 5
#define P_M1 4
#define P_M2 3
#define P_DIR_X 0
#define P_STP_X 1
#define P_DIR_Y 7
#define P_STP_Y 8
#define P_DIR_Z 9
#define P_STP_Z 10
#define P_LED_BEHAVIOR 21
// # Analogue
#define P_A_LED_GCAMP 17
#define P_A_LED_OPTOGENETIC 16
#define P_A_LED_BEHAVIOR 20


// Stepper Constants
#define DEFAULT_STEPMODE 7
#define STEPPER_MAXSPEED_X 1024.0
#define STEPPER_MAXSPEED_Y 1024.0
#define STEPPER_MAXSPEED_Z 1024.0
#define STEPPER_ACCELERATION_X 10000.0
#define STEPPER_ACCELERATION_Y 10000.0
#define STEPPER_ACCELERATION_Z 5000.0


// Programming Constants
#define SIZE_COMMAND_BUFFER 24



// Initialize

// # Stepper Motor Drivers
// https://www.airspayce.com/mikem/arduino/AccelStepper/classAccelStepper.html
AccelStepper stepperX(AccelStepper::DRIVER, P_STP_X, P_DIR_X);
AccelStepper stepperY(AccelStepper::DRIVER, P_STP_Y, P_DIR_Y);
AccelStepper stepperZ(AccelStepper::DRIVER, P_STP_Z, P_DIR_Z);

// # Variables
float xspeed, yspeed, zspeed;
long x, y, z;
long vx, vy, vz;
char *comBuf;
int nChar;


// Functions
void setStepMode(int mode) {
  // mode: corresponds to different step resolutions -> higher means more fine
  // Driver Used: DRV8825 Stepper Motor Controller IC
  // docs: https://www.ti.com/lit/ds/symlink/drv8825.pdf
  int res = mode >= 7 ? 7 : mode; // greater than 7 -> just 7 ->
  int m0 = res % 2;
  res /= 2;
  int m1 = res % 2;
  res /= 2;
  int m2 = res % 2;

  // Set Step Resolution
  digitalWrite( P_M0, m0 );
  digitalWrite( P_M1, m1 );
  digitalWrite( P_M2, m2 );
}


// SETUP
void setup()
{
  // Set USB Port
  Serial.begin(115200);
  Serial.setTimeout(100);

  comBuf = (char*) malloc(SIZE_COMMAND_BUFFER);
  nChar = 0;

  // Set Pins Mode
  int ports [] = {
    P_ENABLE, P_RESTSLEEP,
    P_M0, P_M1, P_M2,
    P_DIR_X, P_STP_X,
    P_DIR_Y, P_STP_Y,
    P_DIR_Z, P_STP_Z,
    P_LED_BEHAVIOR, P_A_LED_BEHAVIOR,
    P_A_LED_GCAMP, P_A_LED_OPTOGENETIC
  };
  for (int port : ports) {
    pinMode(port, OUTPUT);
  }

  // Stepper Motors Initializations
  // # Max Speeds
  stepperX.setMaxSpeed(STEPPER_MAXSPEED_X);
  stepperY.setMaxSpeed(STEPPER_MAXSPEED_Y);
  stepperZ.setMaxSpeed(STEPPER_MAXSPEED_Z);
  // # Accelerations
  stepperX.setAcceleration(STEPPER_ACCELERATION_X);
  stepperY.setAcceleration(STEPPER_ACCELERATION_Y);
  stepperZ.setAcceleration(STEPPER_ACCELERATION_Z);
  // # Stop Motors
  stepperX.setSpeed(0.0);
  stepperY.setSpeed(0.0);
  stepperZ.setSpeed(0.0);
  // # Set Resolution
  setStepMode(DEFAULT_STEPMODE);
}

void loop()
{
  if ( Serial.available() > 0 ) {
    // https://arduinogetstarted.com/reference/serial-readbytesuntil
    nChar = Serial.readBytesUntil('\n', comBuf, SIZE_COMMAND_BUFFER);

    // Cases
    // Global: Turn Off, Turn On
    // LED: IR On/off/set power, behavior/gcamp/optogenetic set power
    // Stepper: set mode, enable/sleep, x/y/z set speed
    char cmd = comBuf[0];
    char subcmd = comBuf[1];
    if (cmd == 'g') { // -------------- GLOBALS
      if ( subcmd == 'n' || subcmd == 'N') {
        //        call_turno();
      } else if ( subcmd == 'f' || subcmd == 'F') {
        //        call_turnoff();
      }
    } else if (cmd == 'l') { // -------------- LEDS
      // Chooes LED
      if ( subcmd == 'b' || subcmd == 'B' ) { // IR LED
        char func = comBuf[2];
        if ( func == 'n' || func == 'N' ) { // # On
          digitalWrite(P_LED_BEHAVIOR, HIGH);
        } else if ( func == 'f' || func == 'F' ) { // # Off
          digitalWrite(P_LED_BEHAVIOR, LOW);
        } else if ( func == 's' || func == 'S' ) { // # Set Power
          analogWrite(P_A_LED_BEHAVIOR, atof(comBuf + 3));
        }
      } else if ( subcmd == 'g' || subcmd == 'G' ) { // GCaMP
        char func = comBuf[2];
        if ( func == 's' || func == 'S' ) { // # Set Power
          analogWrite(P_A_LED_GCAMP, atof(comBuf + 3));
        }
      } else if ( subcmd == 'o' || subcmd == 'O' ) {
        // Optogenetic
        char func = comBuf[2];
        if ( func == 's' || func == 'S' ) { // Set Power
          analogWrite(P_A_LED_OPTOGENETIC, atof(comBuf + 3));
        }
      }

    } else if (cmd == 's') { // -------------- Steppers
      if ( subcmd == 's' || subcmd == 'S' ) { // Set Mode
        setStepMode(atoi(comBuf + 2));
      } else if ( subcmd == 'n' || subcmd == 'N' ) { // # On
        // Turn ON Common Driver Pins
        digitalWrite(P_ENABLE, LOW);
        digitalWrite(P_RESTSLEEP, HIGH);
        // Set Current Position as Zero
        stepperX.setSpeed(0);
        stepperY.setSpeed(0);
        stepperZ.setSpeed(0);
        stepperX.setCurrentPosition(0);
        stepperY.setCurrentPosition(0);
        stepperZ.setCurrentPosition(0);
      } else if ( subcmd == 'f' || subcmd == 'F' ) { // # Off
        // Reset Position to Initial
        //        stepperX.setSpeed(1024);
        //        stepperY.setSpeed(1024);
        //        stepperZ.setSpeed(1024);
        //        stepperX.runToNewPosition(0);
        //        stepperY.runToNewPosition(0);
        //        stepperZ.runToNewPosition(0);
        stepperX.setSpeed(0);
        stepperY.setSpeed(0);
        stepperZ.setSpeed(0);
        // Turn OFF Common Driver Pins
        digitalWrite(P_ENABLE, HIGH);
        digitalWrite(P_RESTSLEEP, LOW);
      } else if ( subcmd == 'x' || subcmd == 'X' ) { // # X Speed
        stepperX.setSpeed(atof(comBuf + 2));
      } else if ( subcmd == 'y' || subcmd == 'Y' ) { // # Y Speed
        stepperY.setSpeed(atof(comBuf + 2));
      } else if ( subcmd == 'z' || subcmd == 'Z' ) { // # Z Speed
        stepperZ.setSpeed(atof(comBuf + 2));
      }
    }

    // Logging
    x=stepperX.currentPosition();
    y=stepperY.currentPosition();
    z=stepperZ.currentPosition();
    vx=stepperX.speed();
    vy=stepperY.speed();
    vz=stepperZ.speed();
    Serial.print(x);
    Serial.print(" ");
    Serial.print(y);
    Serial.print(" ");
    Serial.print(z);
    Serial.print(" ");
    Serial.print(vx);
    Serial.print(" ");
    Serial.print(vy);
    Serial.print(" ");
    Serial.print(vz);
    Serial.print("\n");
    //    Serial.send_now();
  }

  // Moving
  x = stepperX.currentPosition();
  y = stepperY.currentPosition();
  z = stepperZ.currentPosition();
  xspeed = stepperX.speed();
  yspeed = stepperY.speed();
  zspeed = stepperZ.speed();

  // Bounds
  // # X
  //  if(x >  18000 && vx > 0){
  //    stepperX.setSpeed(0);
  //  }else if (x < -25000 && vx < 0){
  //    stepperX.setSpeed(0);
  //  }
  //  // # Y
  //  if(y >  18000 && vy > 0){
  //    stepperY.setSpeed(0);
  //  }else if (y < -25000 && vy < 0){
  //    stepperY.setSpeed(0);
  //  }
  //  // # Z
  //  if(z >  10000 && vz > 0){
  //    stepperZ.setSpeed(0);
  //  }else if( z < 0 && vz < 0 ){
  //    stepperZ.setSpeed(0);
  //  }

  // RUN - most important command!
  stepperX.runSpeed();
  stepperY.runSpeed();
  stepperZ.runSpeed();
}
