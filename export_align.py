# Cleans up input RDF to align the model with the AAC

import argparse
import csv 
import re
import pprint

from utils.embarkservice import KioskQuery, EmbarkService
from pycsvw import CSVW
from rdflib import URIRef, RDF, Graph
from rdflib.plugins.sparql.processor import processUpdate

# Specifically:
	# Duplicates rdf:value literals into rdfs:label where necessary (Accession Number, Title, etc)
	# Materializes title, material, credit line, and other blank nodes as slugged URLs

# pycsvw requires Jena
RIOT_PATH = "/usr/local/jena/bin/riot"

def parse_args(): 
	parser = argparse.ArgumentParser(description = """ Uses a metadata template to generate RDF from a CSV on the Web template.
		Also aligns the graph with the AAC model (slugging and duplicating literal nodes)""")
	parser.add_argument("--csv_file", help = "Process CSV file instead of fetching from server")
	parser.add_argument("--metadata", help = "Metadata file (if not in an expected location)", required = False)
	parser.add_argument("--aac-align", help = "Adds rdfs:label+rdf:value pattern where needed for RDF to conform to the AAC model", action = "store_true", required = False)
	parser.add_argument("--jena_bin", help = "Path to Jena binaries (for RDF generation)")

	args = vars(parser.parse_args())
	return args

def bnode_to_url_slug():
	# Find the bnodes in a graph, replace them with deref'd URLs based on connected literals (rdf:value or rdf:label)
	pass
	
def slugify(text):
	# Removes non-alphanumeric characters, spaces, and extra whitespace
	slug = text.strip().lowercase()
	slug = re.sub('[^A-Za-z0-9]+', '', slug)
	return slug

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

def slugify(uri):
	# Takes a pct-escaped URIRef and slugs the final parameter
	# Returns a URIRef
	full = uri.toPython()
	unslugged = full.split('/')[-1]

	slugged = re.sub(r"\%.{2}","",unslugged) # remove precent-encodes
	slugged = slugged.lower()
	slugged = uri.replace(unslugged,slugged)

	return URIRef(slugged)

def slugify_class(rdf_type, g):
	# Slugifies all URI references for a given rdf:type
	# Takes an rdflib graph object and a class name
	# Modifies graph in-place

	urls = set()
	urls = { url for url in g.subjects( predicate = RDF.type, object = URIRef(rdf_type) ) }

	subjects = 'DELETE { ?old ?p ?o . } INSERT { ?new ?p ?o . } WHERE { ?old ?p ?o . }'
	objects = 'DELETE { ?s ?p ?old . } INSERT { ?s ?p ?new . } WHERE { ?s ?p ?old . }'

	for url in urls:
		slugged = slugify(url)
	
		update = subjects.replace('?old',"<" + url.toPython() + ">").replace('?new',"<" + slugged.toPython() + ">")
		processUpdate(g,update)
		
		update = objects.replace('?old',"<" + url.toPython() + ">").replace('?new',"<" + slugged.toPython() + ">")
		processUpdate(g,update)
	
	return g

def slug_thesauri(g):
	# Slug the thesauri for Medium, Department + Nationality, Classification
	g = slugify_class('http://www.cidoc-crm.org/cidoc-crm/E57_Material', g)
	g = slugify_class('http://www.cidoc-crm.org/cidoc-crm/E74_Group', g)
	g = slugify_class('http://www.cidoc-crm.org/cidoc-crm/E55_Type', g)

def process_csv(csv_file, jena_bin):
	# Generate RDF from a CSV file, correct it, and write the graph to disk
	metadata = "metadata/" + csv_file.split('/')[-1] + "-metadata.json"

	csvw = CSVW(csv_path = csv_file, metadata_path = metadata, riot_path = jena_bin)
	g = Graph()
	g.parse(data = csvw.to_rdf('turtle'), format = "turtle")

	slug_thesauri(g)
	
	with open(csv_file.replace("csv","ttl"), 'wb') as f:
		f.write(g.serialize(format= 'turtle'))

def trim_nodes(g):
	# Remove blank middle classes (alt_title classes, etc)
	pass

def enrich_values(g):
	# On nodes intended to have both rdf:value and rdf:label pairs, copy rdf:value into rdf:label
	pass

def add_label(g,klass,path):
	# On nodes of class, assign an rdfs:label using property path
	pass
	 
def main():
	args = parse_args()
	rec_types = ['objects_1', 'artist_maker','surrogates'] 
	jena_bin = RIOT_PATH

	if args["jena_bin"]:
		jena_bin = args["jena_bin"]

	if args["csv_file"]:

		csv_file = args["csv_file"]
		process_csv(csv_file, jena_bin)

	else:
		for rec_type in rec_types:
			
			fetch_data(rec_type)	

			csv_file = "data/" + rec_type + ".csv"
			process_csv(csv_file, jena_bin)

if __name__ == "__main__":
	main()