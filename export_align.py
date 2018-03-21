# export_align.py:
# - Exports CSV data from EmbARK Web Kiosk XML template exporter
# - (FUTURE) Validates data for type and format
# - Transform into JSON-LD as IIIF manifests or Linked.Art objects

import argparse
import csv
import json
import re
import csv

from pprint import pprint
from tempfile import NamedTemporaryFile

from rdflib import Graph

from utils.embarkservice import KioskQuery, EmbarkService
from pycsvw import CSVW
from pyld import jsonld

import requests

# pycsvw requires Jena
RIOT_PATH = "/usr/local/jena/bin/riot"

def parse_args(): 
	parser = argparse.ArgumentParser(description = """Uses metadata templates to generate IIIF and linked.art as JSON-LD from CSV files.""")
	parser.add_argument("--fetch-csv", action = "store_true", help = "Fetch CSV files from the Web Kiosk")
	parser.add_argument("--fix-ccma-iiif", action = "store_true", help = "Optional: apply CCMA-specific fixes to surrogates")
	parser.add_argument("--iiif-manifest", action = "store_true", help = "Generate files representing sc:Manifest objects for each object")
	parser.add_argument("--linked-art", action = "store_true", help = "Generate JSON-LD for linked.art")

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

	csvw = CSVW(csv_path = csv_file, metadata_path = metadata_file, riot_path = RIOT_PATH)

	with NamedTemporaryFile() as f:
		rdf_output = csvw.to_rdf_files([ (f,'turtle') ])
		f.seek(0)
		g.parse(f, format = 'ttl')

	csvw.close()

	return g


def build_canvases(graph = None):
	if graph is not None:
		process_csv('data/surrogates.csv', 'metadata/surrogates-iiif.csv-metadata.json',RIOT_PATH, graph)
	else:
		graph = process_csv('data/surrogates.csv', 'metadata/surrogates-iiif.csv-metadata.json',RIOT_PATH)

	return graph 

def build_manifests(graph = None):
	if graph is not None:
		process_csv('data/objects_1.csv', 'metadata/objects_1-iiif.csv-metadata.json', RIOT_PATH, graph)
	else: 
		graph = process_csv('data/objects_1.csv', 'metadata/objects_1-iiif.csv-metadata.json',RIOT_PATH)

	return graph

def frame_and_write_canvases():
	# FIXME: frame and write canvases to disk
	pass

def write_manifests(json_ld):
	# Write out manifest JSON files, one per entry in the graph

	for m in json_ld["@graph"]:
		fp = "manifests/" + m["@id"].split('/')[-1]
		m["@context"] = "http://iiif.io/api/presentation/2/context.json"
		with open(fp,'w') as f:
			json.dump(m,f, indent = 4, sort_keys = True )

def frame_and_write_manifests(g):
	
	#with open('contexts/linked-art.json') as f:
	#	ctx = json.load(f)

	js = json.loads(g.serialize(format = 'json-ld', context = "http://iiif.io/api/presentation/2/context.json" ))
	# js = {
	# 	"@context": "http://iiif.io/api/presentation/2/context.json", 
	# }
	# js["@graph"] = [ json.loads(g.serialize(format = 'json-ld')) ]

	with open('graph.json', 'w') as f:
		json.dump(js,f)

	frame = {
		"@context": "http://iiif.io/api/presentation/2/context.json",
		"@embed": "@always",
		"@type": "http://iiif.io/api/presentation/2#Manifest",
		"explicit": "true",
		"metadata": {},
		"sequences": {
			"canvases": {
				"images": {
					"resource": {
						"service": {
							"@context": "http://iiif.io/api/image/2/context.json"
						}
					}
				}
			}
		}
	}

	# See https://github.com/zimeon/iiif-ld-demo/blob/master/prezi-api/jabber5.py
	# frame = {
	# 	"@context": "http://iiif.io/api/presentation/2/context.json",
	# 	"@type": "sc:Manifest",
	# 	"startCanvas": {
	# 		"@embed": False
	# 	},
	# 	"sequences": [
	# 		{
	# 		"@type": "sc:Sequence",
	# 		"startCanvas": {
	# 			"@embed": False
	# 		},
	# 		"canvases": [
	# 			{
	# 				"@type": "sc:Canvas",
	# 				"images": [
	# 					{
	# 					"@type": "oa:Annotation",
	# 					"@embed": True
	# 					}
	# 				],
	# 				"otherContent": [
	# 					{
	# 					"@explicit": True,
	# 					"@embed": True,
	# 					"@type": "sc:AnnotationList",
	# 					"label": {"@embed": True}
	# 					}
	# 				]	
	# 			}
	# 		]
	# 		}
	# 	],
	# 	"structures": [{
	# 	"@type": "sc:Range",
	# 	"@embed": True,
	# 	"canvases": [{
	# 	"@embed": False
	# 	}],
	# 	"ranges": [{
	# 	"@embed": False
	# 	}],
	# 	"members": [{
	# 	"@embed": True,
	# 	"@explicit": True,
	# 	"@type": "",
	# 	"label": {"@embed": True}
	# 	}]
	# 	}]
	# }

	manifests = jsonld.frame( js,frame )

	# Compact with an amended context using "@container": "@set" instead of "@list" to account for JSON-LD 1.1..
	with open('contexts/iiif2-jsonld11.json') as f:
		ctx = json.load(f)
	manifests = jsonld.compact( manifests, ctx )
	manifests = patch_image_service(manifests)
	write_manifests(manifests)

def main():
	args = parse_args()

	if args["fetch_csv"]:
		fetch_data('surrogates')
		fetch_data('objects_1')
		fetch_data('artist_maker')

	if args["fix_ccma_iiif"]:
		fix_ccma_iiif()

	if args["iiif_manifest"]:
		graph = Graph()
		print("Before builds",len(graph),"statements") 
		build_canvases(graph = graph)
		print("After canvas build",len(graph),"statements") 
		build_manifests(graph)
		print("After manifest build",len(graph),"statements")
		frame_and_write_manifests(graph)

	if args["linked_art"]:
		raise NotImplementedError

if __name__ == "__main__":
	main()