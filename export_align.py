# export_align.py:
# - Exports CSV data from EmbARK Web Kiosk XML template exporter
# - Transform into JSON-LD as IIIF manifests or Linked.Art objects
# - (FUTURE) Validates data for type and format

import argparse
import csv
import json
import re
import csv
import os

from pprint import pprint
from tempfile import NamedTemporaryFile

from rdflib import Graph

from embarkservice import KioskQuery, EmbarkService
from pycsvw import CSVW
from pyld import jsonld

import requests

# pycsvw requires Jena
RIOT_PATH = "./bin/apache-jena-3.6.0/bin/riot"

def parse_args(): 
	parser = argparse.ArgumentParser(description = """Uses metadata templates to generate IIIF and linked.art as JSON-LD from CSV files.""")
	parser.add_argument("--fetch-csv", action = "store_true", help = "Fetch CSV files from the Web Kiosk")
	parser.add_argument("--fix-ccma-iiif", action = "store_true", help = "Optional: apply CCMA-specific fixes to surrogates")
	parser.add_argument("--iiif-manifest", action = "store_true", help = "Generate files representing sc:Manifest objects for each object")
	parser.add_argument("--linked-art", action = "store_true", help = "Generate JSON-LD for linked.art")
	parser.add_argument("--riot", default = "./bin/apache-jena-3.6.0/bin/riot", help = "Path to Jena's riot command")

	#parser.add_argument("--csv_file", help = "Process CSV file instead of fetching from server")
	#parser.add_argument("--metadata", help = "Metadata file (if not in an expected location)", required = False)
	#parser.add_argument("--aac-align", help = "Adds rdfs:label+rdf:value pattern where needed for RDF to conform to the AAC model", action = "store_true", required = False)
	#parser.add_argument("--jena_bin", help = "Path to Jena binaries (for RDF generation)")

	args = vars(parser.parse_args())
	return args

def fix_iiif_id(surrogates):
	# Returns surrogates with _cd.[jpg|jpeg|JPG|JPEG] suffix removed
	regex = r'_cd\.[jpgJPEG]+?$'
	for s in surrogates:
		s["File_Name"] = re.sub(regex,'',s["File_Name"])

	return surrogates

def fix_iiif_dimensions(surrogates, endpoint = 'http://iiif.museum.colby.edu/image'):

	if len(surrogates) > 0 and ( 'height' not in surrogates[0] or 'width' not in surrogates[0] ):
		for s in surrogates:
			height = None
			width = None

			if s["File_Name"]:
				url = "{endpoint}/{iiif_id}/info.json".format( endpoint = endpoint, iiif_id = s["File_Name"] )
				print("Fetching ",url)
				r = requests.get(url)
				if r.status_code == 200:
					info = json.loads(r.content)
					height = info.get('height')
					width = info.get('width')

			if height and width:
				s["height"] = height
				s["width"] = width
			else:
				s["height"] = 0
				s["width"] = 0
				# FIXME: log this ID

	return surrogates

def fix_ccma_iiif(surrogates = None):

	with open('data/surrogates.csv') as f:
		reader = csv.DictReader(f)
		surrogates = [ row for row in reader ]

	surrogates = fix_iiif_id(surrogates)
	surrogates = fix_iiif_dimensions(surrogates)

	headers = surrogates[0].keys()

	with open("data/surrogates.csv", 'w') as f:

		writer = csv.DictWriter(f, fieldnames=headers)
		writer.writeheader()

		for row in surrogates:
			writer.writerow(row)

def fetch_data(rec_type):
	# Fetches CSV data from embark.colby.edu and writes them to disk
	svc = EmbarkService()

	query = KioskQuery(layout = rec_type + "-csv", max_recs = 10000, query="_ID>1", rec_type = rec_type)
	csv_data = svc.fetch_csv(query)

	headers = csv_data.fieldnames

	with open("data/" + rec_type + ".csv", 'w') as f:

		writer = csv.DictWriter(f, fieldnames=headers)
		writer.writeheader()

		for row in csv_data:

			# Fixes an issue where 4D integer types insert commas for numbers > 999
			if None in row.keys():
				row.pop(None)

			writer.writerow(row)

def patch_image_service(manifests):
	# Adds "@context": "http://iiif.io/api/image/2/context.json" to all image service blocks
	for m in manifests["@graph"]:

		seq = m.get("sequences")

		if seq and len(seq) > 0:
			
			seq = seq[0]
			canv = seq.get('canvases')
			
			if canv and len(canv) > 0:
				for c in canv:
					img = c.get("images")
					if img and len(img) > 0:
						for i in img:
							rsc = i.get('resource')
							if rsc:
								svc = rsc.get("service")
								if svc:
									svc["@context"] = "http://iiif.io/api/image/2/context.json"

	return manifests


def process_csv(csv_file, metadata_file, riotpath, g = None):
	# Generate RDF from a CSV file and metadata file pair, 
	# csv_file is a path string
	# metadata-file is a path string path optionally merging it into a Graph

	if g is None:
		g = Graph()

	csvw = CSVW(csv_path = csv_file, metadata_path = metadata_file, riot_path = riotpath)

	with NamedTemporaryFile() as f:
		rdf_output = csvw.to_rdf_files([ (f,'turtle') ])
		f.seek(0)
		g.parse(f, format = 'ttl')

	csvw.close()

	return g

def write_jsonld(json_ld, output_dir):
	# Write out manifest JSON files, one per entry in the graph

	for js in json_ld["@graph"]:
		# IIIF takes an "@id", linked.art takes "id"
		ident = js.get("@id")
		ident = js.get("id") if ident is None else ident

		fp = os.path.join(output_dir, ident.split('/')[-1])

		if not fp.endswith(".json"):
			fp = fp + ".json"
			
		js["@context"] = json_ld["@context"]
		with open(fp,'w') as f:
			json.dump(js,f, indent = 4, sort_keys = True )

def frame_and_write(graph, context, frame, output_dir, graph_fixer = None ):
	# Take an RDF graph, convert it to JSON-LD with a compaction context, frame, and an optional graph fixer func

	fp = os.path.join("frames/", frame)
	with open(fp) as f:
		frm = json.load(f)

	print("Loading graph as JSON-LD")
	js = json.loads(graph.serialize(format = 'json-ld', context = context ))

	with open('data/graph.json', 'w') as f:
		json.dump(js,f)

	print("Framing entities")
	entities = jsonld.frame( js,frm )

	if graph_fixer:
		entities = graph_fixer(entities)

	print("Writing entities")
	write_jsonld(entities, output_dir)

def fix_iiif(manifests):
	with open('contexts/iiif2-jsonld11.json') as f:
		ctx = json.load(f)
	manifests = jsonld.compact( manifests, ctx )
	manifests = patch_image_service(manifests)

	manifests["@context"] = "http://iiif.io/api/presentation/2/context.json"

	return manifests

def main():
	args = parse_args()

	RIOT_PATH = args["riot"]

	if args["fetch_csv"]:
		fetch_data('surrogates')
		fetch_data('objects_1')
		fetch_data('artist_maker')

	if args["fix_ccma_iiif"]:
		fix_ccma_iiif()

	if args["iiif_manifest"]:
		graph = Graph()
		print("Building IIIF graph",len(graph),"statements")
		process_csv("data/surrogates.csv", "metadata/surrogates-iiif.csv-metadata.json", RIOT_PATH, graph)
		print("After canvases",len(graph),"statements") 
		process_csv("data/objects_1.csv", "metadata/objects_1-iiif.csv-metadata.json", RIOT_PATH, graph)
		print("After manifests",len(graph),"statements")
		print("Framing and writing manifests")
		frame_and_write(graph, context = "http://iiif.io/api/presentation/2/context.json", frame = "iiif_manifest.json", output_dir = "output/manifests/", graph_fixer = fix_iiif)

	if args["linked_art"]:
		graph = Graph()
		print("Building Linked Art graph", len(graph), "statements")
		process_csv("data/objects_1.csv", "metadata/objects_1.csv-metadata.json", RIOT_PATH, graph)
		print("After ManMadeObjects", len(graph), "statements")
		process_csv("data/artist_maker.csv", "metadata/artist_maker.csv-metadata.json", RIOT_PATH, graph)
		print("After Actors", len(graph), "statements")
		#process_csv("data/surrogates.csv", "metadata/surrogates.csv-metadata.json", RIOT_PATH, graph)
		print("After Visual Items", len(graph),"statements")
		frame_and_write(graph, context = "https://linked.art/ns/v1/linked-art.json", frame = "la_mmos.json", output_dir = "otuput/mmos/")
		frame_and_write(graph, context = "https://linked.art/ns/v1/linked-art.json", frame =  "la_actors.json", output_dir = "output/actors/")
		#frame_and_write(graph, "la_visualitems.json")

if __name__ == "__main__":
	main()
