// Copyright 2023
// Author: Sina Rasouli, Mahdi Torkashvand

#include <AccelStepper.h>

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
#define P_LED_GCAMP 17
#define P_LED_OPTOGENETIC 16

#define DEFAULT_STEPMODE 7
#define STEPPER_MAXSPEED_X 1024.0
#define STEPPER_MAXSPEED_Y 1024.0
#define STEPPER_MAXSPEED_Z 1024.0
#define STEPPER_ACCELERATION_X 10000.0
#define STEPPER_ACCELERATION_Y 10000.0
#define STEPPER_ACCELERATION_Z 10000.0

#define SIZE_COMMAND_BUFFER 32

AccelStepper stepperX(AccelStepper::DRIVER, P_STP_X, P_DIR_X);
AccelStepper stepperY(AccelStepper::DRIVER, P_STP_Y, P_DIR_Y);
AccelStepper stepperZ(AccelStepper::DRIVER, P_STP_Z, P_DIR_Z);

long x, y, z;
long xlimp=45000.0; 
long ylimp=45000.0;
long zlimp=0.0; // Original value: 0.0
long xlimn=-45000.0;
long ylimn=-45000.0;
long zlimn=-30000.0;
long vx, vy, vz;
char *comBuf;
int nChar;

void setStepMode(int mode) {
  int res = mode >= 7 ? 7 : mode;
  int m0 = res % 2;
  res /= 2;
  int m1 = res % 2;
  res /= 2;
  int m2 = res % 2;

  digitalWrite( P_M0, m0 );
  digitalWrite( P_M1, m1 );
  digitalWrite( P_M2, m2 );
}

void setup()
{
  Serial.begin(115200);
  Serial.setTimeout(100);

  comBuf = (char*) malloc(SIZE_COMMAND_BUFFER);
  nChar = 0;

  int ports [] = {
    P_ENABLE, P_RESTSLEEP,
    P_M0, P_M1, P_M2,
    P_DIR_X, P_STP_X,
    P_DIR_Y, P_STP_Y,
    P_DIR_Z, P_STP_Z,
    P_LED_BEHAVIOR,
    P_LED_GCAMP, P_LED_OPTOGENETIC
  };
  for (int port : ports) {
    pinMode(port, OUTPUT);
  }

  stepperX.setMaxSpeed(STEPPER_MAXSPEED_X);
  stepperY.setMaxSpeed(STEPPER_MAXSPEED_Y);
  stepperZ.setMaxSpeed(STEPPER_MAXSPEED_Z);

  stepperX.setAcceleration(STEPPER_ACCELERATION_X);
  stepperY.setAcceleration(STEPPER_ACCELERATION_Y);
  stepperZ.setAcceleration(STEPPER_ACCELERATION_Z);

  stepperX.setSpeed(0.0);
  stepperY.setSpeed(0.0);
  stepperZ.setSpeed(0.0);

  setStepMode(DEFAULT_STEPMODE);
}

void loop()
{
  if ( Serial.available() > 0 )
  {
    nChar = Serial.readBytesUntil('\n', comBuf, SIZE_COMMAND_BUFFER);

    char cmd = comBuf[0];
    char subcmd = comBuf[1];
    if (cmd == 'l')
    {
      char state = comBuf[2];
      if ( subcmd == 'b' )
      {
        if ( state == '1' ) 
        {
          digitalWrite(P_LED_BEHAVIOR, HIGH);
        } 
        else if ( state == '0')
        {
          digitalWrite(P_LED_BEHAVIOR, LOW);
        }
      }
      else if ( subcmd == 'g' ) 
      {
        if ( state == '1' )
        {
          digitalWrite(P_LED_GCAMP, HIGH);
        }
        else if ( state == '0' )
        {
          digitalWrite(P_LED_GCAMP, LOW);
        }
      }
      else if ( subcmd == 'o' )
      {
        if ( state == '1' )
        {
          digitalWrite(P_LED_OPTOGENETIC, HIGH);
        }
        else if ( state == '0' )
        {
            digitalWrite(P_LED_OPTOGENETIC, LOW);
        }
      }
    }
    else if (cmd == 's')
    {
      if ( subcmd == 'n')
      {
        digitalWrite(P_ENABLE, LOW);
        digitalWrite(P_RESTSLEEP, HIGH);
        stepperX.setSpeed(0);
        stepperY.setSpeed(0);
        stepperZ.setSpeed(0);
        stepperX.setCurrentPosition(0);
        stepperY.setCurrentPosition(0);
        stepperZ.setCurrentPosition(0);
      }
      else if ( subcmd == 'f' )
      {
        stepperX.setSpeed(512);
        stepperY.setSpeed(512);
        stepperZ.setSpeed(512);
        if (xlimp <= 0)
        {
          stepperX.runToNewPosition(xlimp);
        }
        else if (xlimn >= 0)
        {
          stepperX.runToNewPosition(xlimn);
        }
        else 
        {
          stepperX.runToNewPosition(0);
        }
        if (ylimp <= 0)
        {
          stepperY.runToNewPosition(ylimp);
        }
        else if (ylimn >= 0)
        {
          stepperY.runToNewPosition(ylimn);
        }
        else 
        {
          stepperY.runToNewPosition(0);
        }
        if (zlimp <= 0)
        {
          stepperZ.runToNewPosition(zlimp);
        }
        else if (zlimn >= 0)
        {
          stepperZ.runToNewPosition(zlimn);
        }
        else 
        {
          stepperZ.runToNewPosition(0);
        }
        stepperX.setSpeed(0);
        stepperY.setSpeed(0);
        stepperZ.setSpeed(0);
        digitalWrite(P_ENABLE, HIGH);
        digitalWrite(P_RESTSLEEP, LOW);
      }
      else if ( subcmd == 'x')
      {
        stepperX.setSpeed(atof(comBuf + 2));
      }
      else if ( subcmd == 'y')
      {
        stepperY.setSpeed(atof(comBuf + 2));
      }
      else if ( subcmd == 'z')
      {
        stepperZ.setSpeed(atof(comBuf + 2));
      }
    }
    else if ( cmd == 'g' )
    {
      if ( subcmd == 'p')
      {
        // This is only to return the current position.
      }
    }
    else if ( cmd == 'm')
    {
      char dir = comBuf[2];
      if ( subcmd == 'x' )
      {
        if ( dir == 'p')
        {
          xlimp=stepperX.currentPosition();
        }
        else if ( dir == 'n')
        {
          xlimn=stepperX.currentPosition();
        }
      }
      else if ( subcmd == 'y' )
      {
        if ( dir == 'p')
        {
          ylimp=stepperY.currentPosition();
        }
        else if ( dir == 'n')
        {
          ylimn=stepperY.currentPosition();
        }
      }
      else if ( subcmd == 'z')
      {
        if ( dir == 'p')
        {
          zlimp=stepperZ.currentPosition();
        }
        else if ( dir == 'n')
        {
          zlimn=stepperZ.currentPosition();
        }
      }
    }

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
    Serial.send_now();
  }

  x = stepperX.currentPosition();
  y = stepperY.currentPosition();
  z = stepperZ.currentPosition();

   if ( x > xlimp && vx > 0 )
   {
     stepperX.setSpeed(0);
   }
   else if ( x < xlimn && vx < 0 )
   {
     stepperX.setSpeed(0);
   }

   if ( y > ylimp && vy > 0 )
   {
     stepperY.setSpeed(0);
   }
   else if ( y < ylimn && vy < 0 )
   {
     stepperY.setSpeed(0);
   }

   if( z > zlimp && vz > 0 )
   {
     stepperZ.setSpeed(0);
   }
   else if( z < zlimn && vz < 0 )
   {
     stepperZ.setSpeed(0);
   }

  stepperX.runSpeed();
  stepperY.runSpeed();
  stepperZ.runSpeed();
}