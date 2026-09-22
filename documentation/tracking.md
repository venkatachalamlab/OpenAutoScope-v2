# Neural-Network Tracking

OpenAutoScope v2 uses a convolutional neural network to locate the terminal bulb in transmitted-light behavior images. Its position estimate feeds the XY optical-stage controller to keep the animal in view. Z position is calculated separately from the animal's XY position and an interpolated sample-surface plane.

## Tracking Objective

The runtime model receives a cropped behavior frame and returns two image coordinates. The software compares that estimate with the desired image position, then sends a correction through the system command path. Tracking is separated from camera acquisition and hardware control so that image capture, inference, display, writing, and motion remain independently managed processes.

<p align="center">
  <img src="../images/images/trackercnn.png" alt="Tracking-network architecture, test-error distribution, and terminal-bulb localization examples" width="900">
</p>

The figure shows the coordinate-regression network, a localization-error histogram, and representative predictions. Red points are manual annotations and blue circles are model outputs.

## Dataset Evolution

The project has several distinct dataset counts. They describe different stages of development and should not be presented as if every image were manually labeled.

| Stage | Scope | Attribution |
| --- | --- | --- |
| Initial dataset | Approximately 17,000 frames with manually marked terminal-bulb coordinates | Collected and annotated by Mahdi Torkashvand |
| Expanded developmental dataset | Semi-automatic annotation of 147,202 frames spanning L1 through young adult in the dissertation | Expansion and augmentation were collaborative work by Mahdi Torkashvand and Sina Rasouli |
| Current model-specific corpora | Repository metadata records 64,000-frame and 220,000-frame training collections for different magnifications and conditions | Model training, selection, and runtime integration led by Sina Rasouli |

The initial 17,000 manually annotated frames were split 4:1 into training and validation sets. The dissertation's later, expanded dataset used separate training (94,210), validation (23,552), and test (29,440) sets; its reported mean test error corresponds to approximately 3-4 pixels between predicted and annotated terminal-bulb positions. This result should not be treated as a benchmark for every ONNX model now stored in the repository.

## Runtime Models

[`models.json`](../models.json) describes models for 4x and 10x imaging, including variants intended for different developmental stages, focus conditions, lighting, and noise augmentation. The ONNX files are stored in [`openautoscopev2/models/`](../openautoscopev2/models/).

The repository provides the inference artifacts used by the instrument. It does not include a complete, reproducible training pipeline, the full training-image corpora, or all intermediate experiments used to select the deployed models.

## Contributions

Mahdi Torkashvand designed the original tracking objective in the context of the instrument, built the initial training-data collection workflow, and manually annotated the first approximately 17,000 frames.

Mahdi and Sina collaborated on expanding and augmenting the dataset. Sina led model training, integration into the control software, and continued refinement after Mahdi left the lab. The wider system and software contributions are described in [Project History and Contributions](project-history.md).
