# Installation Guide
This file provides a comprehensive guide for the step-by-step installation of all essential software required for OpenAutoScope2.0. It is designed with a blank Windows machine in mind, therefore, if your Windows machine already has certain software components installed, you are welcome to skip those specific steps accordingly.

## Git
 - Press the windows button on the keyboard and type `Windows PowerShell` to open the windows power shell.
 - Enter the following command to install Git:
   ```
   winget install --id Git.Git -e --source winget
   ```

## Anaconda
 - Visit [Anaconda](https://www.anaconda.com) website to download the installer for Windows.
 - Open the installer and follow the on-screen steps to complete the Anaconda installation.  
   Important Note: check "Add Anaconda3 to my PATH environment variable"

## 2019 Visual C++ runtime
- Use [this link](https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist#visual-studio-2015-2017-2019-and-2022) and under 'Visual Studio 2015, 2017, 2019, and 2022', select the compatible version/architecture for your system.
- Install the downloaded exe file.

## Clone OpenAutoScope2.0
 - Open a command-pompt and run the following command:
   ```
   if not exist "c:\src" mkdir "c:\src" && cd "c:\src"
   ```
- Clone the OpenAutoScope2.0 Repository:
  ```
  git clone https://github.com/venkatachalamlab/OpenAutoScope-v2.git
  ```
- Change directory to the cloned git folder
  ```
  cd OpenAutoScope-v2
  ```
- Create the python environmet from the `environment.yml` file using the following command:
  ```
  conda env create -f environment.yml
  ```
- Activate `oas` environment:
  ```
  conda activate oas
  ```
- Run the following command:
  ```
  python setup.py develop
  ```
  


## Spinnaker (SDK and SpinView)
- Visit [Flir](https://www.flir.com/products/spinnaker-sdk) website, and sign up to create an account (it is required to download the SDK)
- Once you created an account, go back to [this page](https://www.flir.com/products/spinnaker-sdk) and click on 'Download'
- Once logged in, click on "Download Now"
- In the list, look for the two files to download  
  1- Latest Spinnaker Full SDK for 64-bit Windows, the name is something like:  
  `SpinnakerSDK_FULL_3.x.x.xx_x64.exe`  
  2- Latest Windows Python Spinnaker SDK for 64-bit windows for python version 3.8, the name is something like:  
  `spinnaker_python-3.x.x.xx-cp38-cp38-win_amd64.zip`
- Open the `exe` file and follow on-screen steps to install it.  
  Note: between the two options 'Camera Evaluation' and 'Application Development', select 'Application Development'  
  Note: Uncheck 'I will use GigE Cameras'   
- Unzip the python sdk by right-clicking on the downloaded zip folder and clicking on 'Extract All'
- Open a command prompt and enter this command:
  ```
  conda activate oas
  ```
- Navigate to the unzipped `spinnaker_python-3.x.x.xx-cp38-cp38-win_amd64' folder and run:
  ```
  pip install spinnaker_python-3.x.x.xx-cp38-cp38-win_amd64.whl
  ```
  Note: replace `3.x.x.xx` in this command with the version of the SDK you downloaded.

## Arduino Software
 - Visit [Arduino](https://support.arduino.cc/hc/en-us/articles/360019833020-Download-and-install-Arduino-IDE) and download the latest release for Windows
 - Run the installer and follow on-screen steps to complete the installation.
 - Run 'Arduino IDE', and select 'Install' if asked to install "Arduino USB Driver".
 - Go to File -> Preferences and add the following to the 'Additional boards manager URLs' and press 'Ok':
   ```
   https://www.pjrc.com/teensy/package_teensy_index.json
   ```
 - Go to Tools -> Board -> Boards Manager, and search for 'Teensy' and install 'Teensy by Paul Stoffregen'
 - Go to File -> Open, and open the arduino code in the cloned repository:  
   `c:/src/OpenAutoScope-v2/openautoscopev2/teensy/TeensyController/TeensyController.ino`
 - Go to Tools -> Port, and under 'teensy ports' select the connected teensy port.  
   Note: Write down the port number (e.g. 'COM3'), you will need it later.
 - Go to Tools -> Board -> Teensy, and select the teensy board type.
 - Go to Sketch -> Upload, to upload the code on the board.





