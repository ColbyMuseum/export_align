# export_align

A CSV to JSON-LD pipeline, generates IIIF Presentation manifests and Linked Art data from CSV files exported out of the EmbARK Web Kiosk.

## Requirements

An EmbARK Web Kiosk instance to pull data from, a Linux or macOS instance to run the scripts with python, pip, and Java 8 installed.

## Usage

- Clone this repo `git clone https://github.com/ColbyMuseum/export_align`
- `cd export_align`
- Install the python dependencies, `pip install -r requirements.txt` (or set up a virtualenv)
- Install riot `./install_riot.sh`

Copy the WebKiosk SHTML templates in `./templates` to the WebFolder directory of your WebKiosk install and reboot the WebKiosk service. 

- `python export_align.py --fetch-csv --iiif-manifest` will produce IIIF manifests in `./output/manifest`
- `python export_align.py --fetch-csv --linked-art` will produce LinkedArt JSON documents in `./output/mmo` and `./output/actor`