# export_align

A CSV to JSON-LD pipeline, generates IIIF Presentation manifests and Linked Art data from CSV files exported out of the EmbARK Web Kiosk.

## Requirements

A server or laptop running the EmbARK Web Kiosk and an updated data file, python 3.X, and Java 8.

## Usage

To install the pipeline dependencies, run `pip3 install -r requirements.txt`.

To execute the pipeline, for:
- IIIF manifests, run `python3 export_align.py --iiif-manifest`
- Linked Art entities, run `python3 export_align.py --linked-art`
