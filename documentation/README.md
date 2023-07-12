
This is to navigate to different sections of the documentation for OpenAutoScope2.0. The tutorials provided cover a range of topics including assembling the system,
installing the software, configuring the necessary parameters, performing calibration, preparing samples for optimal results, and conducting imaging sessions on the prepared samples.
You can refer to the specific sections that align with your current needs and requirements.

## [Printed Circuit Board](../pcb)

The manufacturing of the printed circuit board (PCB) typically requires a certain amount of time. There are multiple vendors available, both within and outside the US, that handle PCB production. We used EasyEDA for designing the PCB and ordering it, including the soldered components.

## [Software Installation](installation.md)
The git repository contains all the software codes for the system, primarily written in Python programming language. To ensure the hardware components, such as the Cameras and Teensy board, function properly, specific Software Development Kits (SDKs) are needed. This file provides a comprehensive, step-by-step guide on installing all the necessary packages, libraries, and SDKs for running the system effectively.

## [Hardware Assembly](https://drive.google.com/file/d/1PnN88vxZwhIJeRHgJQa5Ft3MLd5eSH1t/view?usp=share_link)
The provided pdf file serves as a comprehensive construction manual for the OpenAutoScope 2.0 system. It offers a detailed, step-by-step guide for assembling the system. The list of all the necessary parts required for the assembly can be found [here](../parts/parts.pdf). Towards the final stages of the assembly process, the SpinView application is utilized to align the cameras accurately. For more information on installing the SpinView application, refer to the [installation](installation.md) section.

## [Graphical User Interface (GUI)](gui.md)
This document provides an explanation of the various elements present in the graphical user interface (GUI) and their respective functions.
It is assumed that you have already assembled the system before proceeding to this stage.



## [Parameters](parameters.md)
Within this file, you will find the definitions for parameters in the [configuration file](../configs.json) as well as various other components of the system.

## [Calibrations](calibration.md) 
At this stage, with the hardware assembly completed and the software installed, you are ready to run the system and utilize the graphical user interface. However, it is important to note that certain devices may require calibration, and the cameras need to be aligned to ensure simultaneous focus and image alignment. This guide shows you how to perform the necessary steps.

## [Sample Preparation](sample_preparation.md)
The purpose of the protocol is to ensure optimal performance of the tracking algorithm by emphasizing the importance of sample preparation. To achieve precise z tracking during imaging and effectively image single neurons, it is recommended to prepare the sample on glass. For improved tracking accuracy, it is advised to prepare agar plates with a low peptone percentage and seed them with a small amount of OP50 close to the experiment's execution, minimizing food residues in the recordings. Additionally, creating thin agar plates and utilizing agarose or noble agar enhances sample transparency, thereby increasing the signal-to-noise ratio in the recordings.

## [Motion Control With The Xbox Controller](xbox_controller.md)
This explains how you can utilize an Xbox controller to easily move the stage and find the sample and focus on it.



## [How to run an imaging session](imaging_session.md)
This is an example flow for an imaging session with OpenAutoScope 2.0:

