# Long-Term Data Showcase

This page presents derived results from one unpublished OpenAutoScope v2 recording. The Venkatachalam Lab approved public display of these plots. Sina Rasouli collected and analyzed the dataset; the documentation figures were rendered from Sina's processed outputs.

The strain identifier is intentionally omitted. Fluorescence is described as NSM activity without publishing the strain name.

## Dataset Scope

The processed behavior record contains 2,052,578 timestamps spanning approximately 112 hours. Within that record, 44 discrete observations contain matched NSM fluorescence and pharyngeal-pumping data. The first and last matched observations are approximately 97.6 hours apart.

The 44 observations are discrete sessions. They do not represent uninterrupted fluorescence acquisition throughout the experiment.

## Developmental Overview

![Longitudinal morphology, food position, and observation timeline](../images/showcase/longitudinal-overview.png)

The upper panel summarizes body area and centerline length after hatching. The middle panel shows signed distance to the nearest of 18 mapped food patches; negative values indicate that the tracked position was inside a patch. The lower panel marks the 44 matched NSM and pumping observations.

Processing used for this documentation figure:

- Non-finite and non-positive morphology values were excluded.
- Intervals marked as tracking loss, with a ten-frame buffer, were excluded.
- Morphology and food-distance values were summarized in ten-minute median bins.
- Isolated morphology bins differing by more than 18 percent from a local 70-minute median were replaced by that local median, followed by a three-bin median filter.
- Observation timing was calculated from the recorded behavior timestamps relative to the recorded hatching timestamp.

These steps make developmental trends easier to see while limiting the effect of isolated segmentation errors.

## Body Shape and Segmentation Masks

![Body-width profiles and segmentation masks at four times after hatching](../images/showcase/body-width-and-masks.png)

The four curves summarize body width along the animal, using the interior positions of a 49-point profile. They use four-hour windows centered at 6, 24, 40, and 90 hours after hatching. At each position, the line is the median and the band spans the 25th to 75th percentiles. The matching masks below are individual frames at those times, cropped to the same pixel dimensions so that the change in apparent size is preserved. The outline is the boundary of each processed binary mask; the raw transmitted-light frames are not shown.

For the width summaries, frames with non-finite or non-positive body area or centerline length, frames before hatching, and marked tracking-loss intervals with a ten-frame buffer were excluded. Every 80th remaining frame in each window was sampled. Non-finite and non-positive widths were omitted, and the two end positions were excluded from the profiles. The masks are shown without smoothing or anatomical-stage assignments.

## Pumping Event Detail

![Pharyngeal kymograph with manual pump marks and a separate pharynx reference image](../images/showcase/pumping-kymograph-with-reference.png)

The kymograph is a ten-second excerpt from one of the 44 pumping observations, approximately 65.6 hours after hatching. Its grayscale range spans the second to 98th percentiles of the displayed excerpt. Red ticks below the kymograph are pump events recovered from manual marks in the corresponding annotated image; they are not automatic pump detections. The right-hand image is a crop of the separate tracking example in [`trackercnn.png`](../images/images/trackercnn.png), not a frame from this pumping observation. The terminal-bulb marker is part of that source image.

## Matched NSM and Pumping Observation

![Representative NSM trace and pharyngeal pumping kymograph](../images/showcase/representative-observation.png)

This example begins 74.1 hours after the recorded hatching time. The NSM trace is the mean fluorescence across each processed 500-sample profile, with a one-second moving average overlaid. The kymograph shows processed intensity along the pharyngeal centerline. Missing kymograph values were not interpolated.

The trace is shown in arbitrary fluorescence units. It shows changes within this observation; the values are not calibrated for comparison between experiments.

## Pumping Across Development

![Pharyngeal pumping kymographs across development](../images/showcase/pumping-across-development.png)

The three observations begin 5.4, 39.9, and 97.9 hours after hatching. Each panel uses its own second-to-98th-percentile intensity range so that pumping structure remains visible despite changes in brightness and animal size. Blank vertical regions correspond to missing values in the processed kymograph and were not filled.

## Data Availability

The raw and processed dataset is not committed to this repository. It is large, contains unpublished material, and remains under laboratory stewardship. The repository stores only the lab-approved derived figures needed to document the system's capabilities.

## Provenance

| Contribution | Person |
| --- | --- |
| Instrument design, primary assembly, control-software design and development, initial tracking-data collection, and initial manual annotations | Mahdi Torkashvand |
| Tracking-model training and integration, later system modifications, collection of this dataset, and data analysis | Sina Rasouli |
| Permission to display derived plots | Venkatachalam Lab |

See [Project History and Contributions](project-history.md) for the broader project record and [Media Attribution](media-attribution.md) for figure reuse terms.
