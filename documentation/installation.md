# Installation Guide
This guide covers installation of the software required for OpenAutoScope v2 on a clean Windows system. Skip components that are already installed.

## Overview
Here are the general steps to follow

- (1) Install the SDK required to operate the FLIR cameras: install the Spinnaker SDK in Development Mode.

- (2) Create a Python virtual environment for the project requirements: install Anaconda.

- (3) Install `OAS` and its requirements inside the Python virtual environment: download the repository from GitHub and install it.

- (4) Install the Arduino IDE to edit and upload code to the Teensy controller, then configure Teensy support.

- (5) Run and test `OAS`: open Command Prompt, activate the `oas` environment, and run `oas`.

An IDE is useful for reading and editing source and configuration files. One option is [Visual Studio Code](https://code.visualstudio.com/) with the [VS Code Python extension](https://marketplace.visualstudio.com/items?itemName=ms-python.python).

## (0) Create a folder for all files
The `OAS` software and the required-installation-files will be located inside a folder that we will create now.

Create a folder inside the `C` drive called `src`, either through windows `File Explorer` or with the following command in command-line (CMD)
```
if not exist "c:\src" mkdir "c:\src" && cd "c:\src"
```
> Now you should have a folder at this location `c:\src`.


## (1) Spinnaker (SDK and SpinView)
> **Note:** The installed Spinnaker SDK and its Python wheel must have matching versions. This guide uses version `4.2.0.83`; the system has also been tested with versions `3.x.x` and `4.0.x`.

- (1.1) Visit [Teledyne Vision Solutions @ Software Development Kits](https://www.teledynevisionsolutions.com/categories/software/software-development-kits/)

- (1.2) Select `Spinnaker SDK`. The vendor also maintains a [Spinnaker product page](https://www.teledynevisionsolutions.com/products/spinnaker-sdk/?model=Spinnaker%20SDK&vertical=machine%20vision&segment=iis).

> The vendor may require an account before downloading the installer.

- (1.3) Download the Spinnaker SDK software appropriate for your operating system.
> The tested installer is `Spinnaker SDK 4.2.0.83 for Windows 64-bit`; its filename is `SpinnakerSDK_FULL_4.2.0.83_x64.exe`.

- (1.4) Download the matching Python 3.10 wheel from the same page.
> For version `4.2.0.83`, the archive is `spinnaker_python-4.2.0.83-cp310-cp310-win_amd64.zip`.


- (1.5) Run `SpinnakerSDK_FULL_4.2.0.83_x64.exe` and follow the installation prompts. Select `Application Development` rather than `Camera Evaluation`, and clear `I will use GigE Cameras` if the system has no GigE camera.
- (1.6) Extract `spinnaker_python-4.2.0.83-cp310-cp310-win_amd64.zip`. The extracted folder should contain `spinnaker_python-4.2.0.83-cp310-cp310-win_amd64.whl`.
- (1.7) Move the `.whl` file to `c:\src`.


## (2) Install Anaconda
- (2.1) Visit [Anaconda](https://www.anaconda.com) website to download the installer for Windows.
- (2.2) Open the installer and follow the on-screen steps to complete the Anaconda installation.
- (2.3) Open `Anaconda Prompt`, run the following command, and follow its instructions. This makes `conda` available in Command Prompt.
> conda init

## (3) Install OpenAutoScope v2
Download the OpenAutoScope v2 repository as a ZIP archive or clone it with Git.
The resulting repository folder should be named `OpenAutoScope-v2`.
> If the extracted folder has a different name, rename it to `OpenAutoScope-v2`.
- (3.1) Place the repository at `c:\src\OpenAutoScope-v2` and confirm that the repository files are directly inside that folder.
- (3.2) Open Windows Command Prompt and run the following commands, one line at a time, to create a Python virtual environment with the required tools.
```
cd c:\src\OpenAutoScope-v2
conda env create --file=environment.yml
```
- (3.3) Activate the Python environment in Command Prompt before installing additional tools.
```
conda activate oas
```
> If the line in CMD starts with `(oas)`, this means the virtual environment is already activated and you don't need to activate it.
- (3.4) Install the Spinnaker Python wheel inside the `oas` environment.
```
conda activate oas
cd c:\src
pip install spinnaker_python-4.2.0.83-cp310-cp310-win_amd64.whl
```
- (3.5) Install the `oas` command and project package.
```
conda activate oas
cd c:\src\OpenAutoScope-v2
pip install -e .
```

> The `oas` package is now installed.
> The remaining steps are uploading the Teensy code and recording the correct camera serial numbers before running `oas`.

## (4) Arduino Software
> If security software blocks the installer, follow your institution's IT and security guidance. Do not disable endpoint protection without authorization.
- (4.1) Visit the [Arduino IDE download page](https://www.arduino.cc/en/software/#ide). The version used when this guide was written was `arduino-ide_2.3.6_Windows_64bit.exe`.
- (4.2) Run the installer and follow its prompts.
- (4.3) Add Teensy board support.
  - (4.3.1) Open `File -> Preferences` and find `Additional boards manager URLs`.
  - (4.3.2) Add the following URL.
  ```
  https://www.pjrc.com/teensy/package_teensy_index.json
  ```
  - (4.3.3) Select `OK` and return to the main IDE window.
- (4.4) Open `Tools -> Board -> Boards Manager`, then search for `Teensy`.
  - (4.4.1) Install `Teensy by Paul Stoffregen`.
- (4.5) Use `File -> Open` to open the controller sketch at the following path.
```
C:\src\OpenAutoScope-v2\openautoscopev2\teensy\TeensyController\TeensyController.ino
```
- (4.6) Under `Tools -> Board -> Teensy`, select the board model installed in the instrument. The original build used a Teensy LC; later builds may use a Teensy 4.0.
```
Tools -> Board -> Teensy (for Arduino 2.0.4 or later) -> Teensy LC
```
- (4.7) Select the port corresponding to the Teensy board and confirm that it is identified as a `Teensy` port. The port number may differ from the `COM4` example.
```
Tools -> Port -> teensy ports -> COM4 (Teensy LC)
```
- (4.8) Record the Teensy port number for use in `configs.json`; for example, `COM4`.
- (4.9) Upload the controller code and wait for the `Uploading completed` notification.
```
Sketch -> Upload
```
> During a successful upload, the blue/orange indicator LED turns on and then off if the driver knob is set to a nonzero value.



## (5) Run OpenAutoScope v2

- (5.0) Once per installation, configure `c:\src\OpenAutoScope-v2\configs.json` with the Teensy COM port and camera serial numbers.
  - Set `teensy_usb_port` to the port recorded in step 4.8; for example, `COM4`.
  - Set the behavior and GCaMP camera serial numbers from the camera labels or SpinView.
- (5.1) Open Windows Command Prompt and run the following commands.
```
conda activate oas
oas
```
