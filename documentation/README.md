# OpenAutoScope v2 Documentation

This index organizes the repository for readers who want to understand the system, build it, operate it, or inspect the research it enables. OpenAutoScope v2 is a deployed laboratory instrument; verify the current hardware revision and local safety procedures before following an operating instruction.

## Understand the System

| Document | Purpose |
| --- | --- |
| [System overview](system-overview.md) | Optical paths, motion hardware, electronics, and design goals |
| [Software architecture](software-architecture.md) | Runtime processes, messages, image flow, and configuration |
| [Neural-network tracking](tracking.md) | Terminal-bulb localization, training datasets, and attribution |
| [Long-term data showcase](data-showcase.md) | Approved derived figures, methods, and dataset provenance |
| [Project history and contributions](project-history.md) | Development history and collaborator roles |
| [Media attribution](media-attribution.md) | Sources and reuse terms for images and derived figures |

## Build the Instrument

| Resource | Scope |
| --- | --- |
| [Parts list](../parts/parts.pdf) | Mechanical, optical, and electronic components |
| [PCB manufacturing files](../pcb/README.md) | Gerber and drill files with ordering notes |
| [Assembly preview](../images/showcase/assembly-preview.gif) | Condensed view of the mechanical build sequence |
| [Hardware assembly manual](https://drive.google.com/file/d/1PnN88vxZwhIJeRHgJQa5Ft3MLd5eSH1t/view?usp=share_link) | Step-by-step construction guide maintained with the project materials |

## Install and Configure

| Document | Scope |
| --- | --- |
| [Software installation](installation.md) | Windows environment, Spinnaker SDK, Python environment, and Teensy setup |
| [Parameters](parameters.md) | Configuration-file fields and motion or acquisition settings |
| [Calibration](calibration.md) | Cameras, illumination, motor drivers, and optical alignment |

## Run an Experiment

| Document | Scope |
| --- | --- |
| [Graphical interface](gui.md) | Controls and live displays |
| [Xbox controller](xbox_controller.md) | Manual stage motion |
| [Imaging session](imaging_session.md) | Example sequence for starting and recording an experiment |

## Safety and Scope

These pages document a particular research system. They do not replace institutional laser, electrical, mechanical, chemical, or biological safety procedures. Configuration values and device identifiers shown in the repository should be treated as installation-specific.
