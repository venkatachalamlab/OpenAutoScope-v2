# Installation Guide
This file provides a comprehensive guide for the step-by-step installation of all essential software required for OpenAutoScope2.0. It is designed with a blank Windows machine in mind, therefore, if your Windows machine already has certain software components installed, you are welcome to skip those specific steps accordingly.

## Overview
Here are the general steps to follow

- (1) Install required SDK to operate the FlirCameras throught your computer -> install SpinnakerSDK in Development Mode

- (2) Create a python virtual environment to install all requirements there -> install Anaconda

- (3) Install `OAS` along with its requirements inside the python virtual environment -> download from Github and install

- (4) Install ArduinoIDE to edit and upload code to the Teensy controller device -> install ArduinoIDE and configure Teensy Support

- (5) Running `OAS` procedure and testing how it works -> open CMD, activate `oas` environment, run `oas`

It's recommended to install an IDE to help with reading and editing the codes and config files. E.g. [Visual Studio Code](https://code.visualstudio.com/) with [VSCode Python Extension](https://marketplace.visualstudio.com/items?itemName=ms-python.python).

## (0) Create a folder for all files
The `OAS` software and the required-installation-files will be located inside a folder that we will create now.

Create a folder inside the `C` drive called `src`, either through windows `File Explorer` or with the following command in command-line (CMD)
```
if not exist "c:\src" mkdir "c:\src" && cd "c:\src"
```
> Now you should have a folder at this location `c:\src`.


## (1) Spinnaker (SDK and SpinView)
> **Note:** As long as the version of the `SpinnakerSDK.exe` software installed, matches the same `SpinnakerSDK python.whl` version installed, then any version should work in theory! :grin:
> Here we will use the most recent version at the time of writing this guide, `4.2.0.83`, though the tools have been tested with `3.x.x` and `4.0.x` versions as well.

- (1.1) Visit [Teledyne Vision Solutions @ Software Development Kits](https://www.teledynevisionsolutions.com/categories/software/software-development-kits/)

- (1.2) Select "Spinnaker SDK" (they have been changing the links, so maybe this link still works [link](https://www.teledynevisionsolutions.com/products/spinnaker-sdk/?model=Spinnaker%20SDK&vertical=machine%20vision&segment=iis))

> It requires an account to log-in and download. At the time of writing this guide (`2025-04-20`), the account is free to make and proceed with the download.

- (1.3) Download the Spinnaker SDK software appropriate for your operating system.
> In our case, it is `Spinnaker SDK 4.2.0.83 for Windows 64-bit (February 28, 2025)`, and downloaded file name is `SpinnakerSDK_FULL_4.2.0.83_x64.exe`

- (1.4) Also make sure to download the accompanying python file on the same page
> In this case, it is `Spinnaker SDK 4.2.0.83 for Windows 64-bit (February 28, 2025) -> 64-bit Python 3.10`, and downloaded file name is `spinnaker_python-4.2.0.83-cp310-cp310-win_amd64.zip`


- (1.5) Open the `SpinnakerSDK_FULL_4.2.0.83_x64.exe` file and follow on-screen steps to install it.
  Note: between the two options 'Camera Evaluation' and 'Application Development', select 'Application Development'  
  Note: Uncheck 'I will use GigE Cameras'   
- (1.6) Unzip the python sdk zip file `spinnaker_python-4.2.0.83-cp310-cp310-win_amd64.zip` by right-clicking on the downloaded zip folder and clicking on 'Extract All'
> This should create a folder with the following file inside `spinnaker_python-4.2.0.83-cp310-cp310-win_amd64.whl`
- (1.7) Move the `spinnaker_python-4.2.0.83-cp310-cp310-win_amd64.whl` file to `c:\src` folder.


## (2) Install Anaconda
- (2.1) Visit [Anaconda](https://www.anaconda.com) website to download the installer for Windows.
- (2.2) Open the installer and follow the on-screen steps to complete the Anaconda installation.
- (2.3) Find `Anaconda Prompt` and open it, then type the following command and follow the instructions. This make the `conda` command recognizable in CMD.
> conda init

## (3) Install OpenAutoScope2.0
You need the files from `OpenAutoScope2.0` GitHub repository. You can download them as a ZIP file or clone the repository using `git` tool.
Assuming you have either "git cloned" or "downloaded and extracted" the repository files, you should have a folder named `OpenAutoScope-v2` with all the files from the repository.
> If the folder name is different, please rename it to `OpenAutoScope-v2`. Also if you download as a ZIP file, make sure to move the folder inside the extraction folder.
- (3.1) Move the content to the folder `c:\src\OpenAutoScope-v2`, double check that the content of this folder is the same as the files you see online on the repository.
- (3.2) Open windows CMD and run following commands (line by line) to create a new python virtual environment with all required tools
```
cd c:\src\OpenAutoScope-v2
conda env create --file=environment.yml
```
- (3.3) Now a python virtual environment should be created. You need to have it activated in CMD every time you want to install new tools
```
conda activate oas
```
> If the line in CMD starts with `(oas)`, this means the virtual environment is already activated and you don't need to activate it.
- (3.4) Install the `SpinnakerSDK python` wheel file `spinnaker_python-4.2.0.83-cp310-cp310-win_amd64.whl` inside the `oas` environment
```
conda activate oas
cd c:\src
pip install spinnaker_python-4.2.0.83-cp310-cp310-win_amd64.whl
```
- (3.5) Now it's time to install the `oas` command and tools! :party:
```
conda activate oas
cd c:\src\OpenAutoScope-v2
pip install -e .
```

> Congrats! `oas` is now installed!!! :party:
> The only remaining steps are uploading teensy code and writing down correct camera serial numbers before running the `oas`.

## (4) Arduino Software
> If the installation fails due to antivirus prevention, you might need to temporarily deactivate you antivirus for the installation. YET this is not recommended and proceed at your own risk!
- (4.1) Visit [Arduino Software IDE](https://www.arduino.cc/en/software/#ide) website and download the `Arduino IDE`. At the time of writing this guide, the downloaded file+version is `arduino-ide_2.3.6_Windows_64bit.exe`
- (4.2) Run the installation file `arduino-ide_2.3.6_Windows_64bit.exe` and follow the instructions and prompts
- (4.3) Let's add Teensy board management support by adding the indexing info
  - (4.3.1) Open 'File -> Preferences' window and find 'Additional boards manager URLs' section
  - (4.3.2) Add this line to `Additional boards manager URLs` section
  ```
  https://www.pjrc.com/teensy/package_teensy_index.json
  ```
  - (4.3.3) Press 'Ok' and go back to main IDE window
- (4.4) Open 'Tools -> Board -> Boards Manager' from top bar, then a side bar from left appears that allows searhing board names
  - (4.4.1) Search 'Teensy'
  - (4.4.2) Look for and install the package "Teensy by Paul Stoffregen"
- (4.5) Open the arduino code provided in the `OpenAutoScope-v2` folder, from 'File -> Open' in the following path
```
C:\src\OpenAutoScope-v2\openautoscopev2\teensy\TeensyController\TeensyController.ino
```
- (4.6) Go to 'Tools -> Board' and from 'Teensy' section, select the appropriate Teensy board model. In our case it is 'Teensy LC', it could be 'Teensy 4.0' in your case.
```
Tools -> Board -> Teensy (for Arduino 2.0.4 or later) -> Teensy LC
```
- (4.7) Then select the appropriate port that corresponds to the teensy board, and make sure it is automatically detected/named as a "Teensy" port. The port number "COM4" can be different in you case!
```
Tools -> Port -> teensy ports -> COM4 (Teensy LC)
```
- (4.8) Write down the port number for the teensy board since you will need it later: e.g. in this case `COM4`
- (4.9) Now it's time to upload the code to the teensy controller to run it. Make sure you wait till you see a notification (bottom right), that says "Uploading completed"
```
Sketch -> Upload
```
> And indicator of code successfully uploaded is the blue/orange LED turining on, then off during this process (if the driver knob is set to non-zero).



## (5) Running the OAS
Here are the steps you need to do to run `oas` software
- (5.0) (Only once) configure the `c:\src\configs.json` file with proper teensy board "COM" number and camera serial numbers
  - change the "COM3" in front of "teensy_usb_port" to  whatever `COM` value you've found in the section (4.8) to upload the code, e.g. "COM4"
  - set the appropriate serial numbers for behavior and gcamp cameras by reading them on the camera label or using "SpinView" software
- (5.1) To run `oas`, open a CMD in windows and run the following line by line
```
conda activate oas
oas
```
