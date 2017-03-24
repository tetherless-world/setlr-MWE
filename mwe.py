import pandas as pd
import numpy as np
import configparser
import json, math
import re
import sys


def main():
	if len(sys.argv) < 2:
		print("USAGE: python subj_mwe.py <config.ini>")
		sys.exit()

	#file setup and configuration
	config = configparser.ConfigParser()
	config.read(sys.argv[1])

	dctfile = config['Source Files']['dictionary']
	cbfile = config['Source Files']['codebook']
	tlfile = config['Source Files']['timeline']

	dct = pd.read_csv(dctfile)
	cb = pd.read_csv(cbfile)
	tl = pd.read_csv(tlfile)
	ontpath = config['Source Files']['ontology']

	#name of intermediate setlr file
	tname = config['Output Files']['setl_file']

	#name of output file
	out_fname = config['Output Files']['converted_file']
	
	turtle = open(tname, 'w')
	#prefixes
	prefix_template = '''@prefix rdf:         <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs:        <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd:         <http://www.w3.org/2001/XMLSchema#> .
@prefix owl:         <http://www.w3.org/2002/07/owl#> .
@prefix skos:        <http://www.w3.org/2004/02/skos/core#> .
@prefix prov:        <http://www.w3.org/ns/prov#> .
@prefix sio:         <http://semanticscience.org/resource/> .
@prefix dcat:        <http://www.w3.org/ns/dcat#> .
@prefix dcterms:     <http://purl.org/dc/terms/> .
@prefix void:        <http://rdfs.org/ns/void#> .
@prefix foaf:        <http://xmlns.com/foaf/0.1/> .
@prefix ov:          <http://open.vocab.org/terms/> .
@prefix setl:        <http://purl.org/twc/vocab/setl/> .
@prefix csvw:        <http://www.w3.org/ns/csvw#> .
@prefix pv:          <http://purl.org/net/provenance/ns#>.
@prefix chear:       <http://hadatac.org/ont/chear#> .

@prefix :            <{transform}> .
\n
'''

	prefixes = prefix_template.format(transform = config['Prefixes']['transform_prefix'])
	#turtle.write(prefixes)
	
	#WRITE DATA FILE EXTRACT
	df = config['Data Files']['data_file']
	extract = writeDataFileExtract(df)
	#turtle.write(extract)

	#ontology
	o = ''':ontology a owl:Ontology;
\tprov:wasGeneratedBy [
\t\ta setl:Extract;
\t\tprov:used <{ontology}>;
\t].\n\n'''
	ont = o.format(ontology=ontpath)
	#turtle.write(ont)

	base_uri = config['Prefixes']['base_uri']
	tfcontext = writeTransformContext(base_uri)
	#turtle.write(tfcontext)

	#theTransform = writeTransformValue(cb, dct, tl)
	theCodebook,theSDD,theTimeline = compileSDD(cb, dct, tl)
	with open("testSDD.json","w") as f:
		json.dump(theSDD,f)
#	with open("testCB.json","w") as f:
#		json.dump(theCodebook,f)
	#turtle.write(theTransform)
#	test_sb = writeTransformValue(theCodebook,theSDD,theTimeline)
#	print test_sb
	
	theLoad = writeLoad(out_fname)
	#turtle.write(theLoad)
	turtle.close()
#/MAIN




#WRITE DATA FILE EXTRACT
def writeDataFileExtract(fname):
	suffix = fname.split('.')[-1].lower()
	# these are defined in SETLr's documentation
	filetype = {"csv" : "csvw:Table, setl:Table",
							 "tsv" : "csvw:Table, setl:Table",
							 "xpt" : "setl:XPORT, setl:Table",
							 "sas" : "setl:SAS7BDAT, setl:Table",
							 "owl" : "owl:Ontology",
							 "rdf" : "void:Dataset" }
	try:
		dtype = filetype[suffix]
	except KeyError:
		print('Invalid or unsupported data file type: ' + df)
		sys.exit()
	
	scriptbuffer = ''
	sf = ''':table a {ft};
\tprov:wasGeneratedBy [
\t\ta setl:Extract;
\t\tprov:used <{dfile}>;
\t].\n\n'''
	scriptbuffer += sf.format(dfile=fname, ft=dtype)
	return scriptbuffer
#/WRITE DATA FILE EXTRACT


#WRITE TRANSFORM CONTEXT
def writeTransformContext(base_uri):
	scriptbuffer = ''':transform a void:Dataset, dcat:Dataset, setl:Persisted;
\tprov:wasGeneratedBy [
\t\ta setl:Transform, setl:JSLDT;
\t\tprov:used :table;\n'''

	ctxt = '''\t\tsetl:hasContext \'\'\'{{
\t"@vocab" :  "http://hadatac.org/ont/chear#",
\t"sio" :     "http://semanticscience.org/resource/",
\t"chear" :   "http://hadatac.org/ont/chear#",
\t"skos" :    "http://www.w3.org/2004/02/skos/core#",
\t"prov" :    "http://www.w3.org/ns/prov#",
\t"rdfs" :    "http://www.w3.org/2000/01/rdf-schema#",
\t"hbgd" :    "https://hbgd.tw.rpi.edu/ns/",
\t"dataset" : "{base_uri}"\n'''
	scriptbuffer += ctxt.format(base_uri=base_uri)
	scriptbuffer += "\t\t}''';\n"
	return scriptbuffer
#/WRITE TRANSFORM CONTEXT


#COMPILE SDD
def compileSDD(codebook, dictionary, timeline):
# TIMEPOINTS NEW
# (0:index) 1:Name 2:Start 3:End 4:Unit 5:Type
	tl_dict = {}
	for tlrow in timeline.itertuples():
		tl_dict[tlrow[1]] = tlrow[5]

# CODEBOOK
# (0:index) 1:Column 2:Value 3:Class 4:New Term 5:Working Column (From Original DD) 6:Notes	
	cb_dict = {}
	current_var = ''
	for cbrow in codebook.itertuples():
		if pd.notnull(cbrow[1]): #reset current var if we're on a new one
			current_var = cbrow[1]
		if current_var not in cb_dict: #if this var isn't in the codebook yet, add a spot for it
			cb_dict[current_var] = {}
		if pd.isnull(cbrow[2]) and pd.isnull(cbrow[3]):
			print('WARN: blank row: {}'.format(cbrow[0]))
			continue
		value_key = str(int(cbrow[2]))
		# (label, uri)
		cb_dict[current_var][value_key] = {}
		cb_dict[current_var][value_key]['sio:hasValue'] = cbrow[5]
		cb_dict[current_var][value_key]['@type'] = cbrow[3]

	numrows = dictionary.shape[0]

	sdd = {}

	# MAIN PARSING LOOP FOR DATA DICTIONARY
	for row in dictionary.itertuples():
		if pd.isnull(row[1]):
			print("WARN: unspecified variable row in SDD {}".format(row[0]))
			continue
	# row is META
#	0:index ... 8:Entity 9:Role 10:Relation 11:inRelationTo 12:NewConcept ...
		if row[1].startswith('??'):
			conc = row[1]
			# add new concept to dictionary if we don't have it yet
			if conc not in sdd: 
				if pd.isnull(conc):
					conc = 'NULL'
				sdd[conc] = {}
			# entity type needs to not be null
			if pd.notnull(row[8]):
				sdd[conc]['@type'] = row[8]
			else:
				print('WARN: entity {} missing type'.format(row[1]))
			# it's okay if there's no role
			if pd.notnull(row[9]):
				sdd[conc]['sio:hasRole'] = row[9]
			# specify entity relation if there is one
			if pd.notnull(row[11]):
				if pd.notnull(row[10]):
					sdd[conc][row[11]] = row[10]
				else: #default relation
					sdd[conc][row[11]] = 'sio:isRelatedTo'
	#/META

	# row is REGULAR
# REGULAR 
#	0:index 1:Column 2:LABEL 3:Definition 4:Attribute 5:attributeOf 6:Unit 7:Time ... 10:Relation 11:inRelationTo 12:NewConcept 13:wasDerivedFrom 14:wasGeneratedBy
		else:
			conc = row[5] #check for the meta row
			#add new concept to dictionary if we don't have it yet
			attr = 'sio:hasAttribute'
			if pd.notnull(row[10]):
				attr = row[10]
			if conc not in sdd: 
				if pd.isnull(conc):
					conc = 'NULL'
				sdd[conc] = {}
			if attr not in sdd[conc]:
				sdd[conc][attr] = {}
			if pd.isnull(row[1]):
				print('WARN: unspecified variable row in SDD: {}'.format(row[0]))
				continue
			col_name = row[1]
			sdd[conc][attr][col_name] = {}
			if pd.notnull(row[4]):
				sdd[conc][attr][col_name]['rdfs:subClassOf'] = row[4]
			else:
				print("WARN: untyped variable {}".format(row[1]))
			if pd.notnull(row[2]):
				sdd[conc][attr][col_name]['rdfs:label'] = row[2]
			if pd.notnull(row[6]):
				sdd[conc][attr][col_name]['sio:hasUnit'] = row[6]
			if pd.notnull(row[7]):
				sdd[conc][attr][col_name]['sio:measuredAt'] = row[7]
			
	#/REGULAR
	return cb_dict, sdd, tl_dict
#/COMPILESDD


#WRITETRANSFORMVALUE
def writeTransformValue(codebook, dictionary, timeline):
	#transform (prov:value is the transform)
	scriptbuffer = "\t\tprov:value '''[{\n"

	# the semantic data dictionary
	scriptbuffer += '''\t"@id": "dataset:{{row.STUDYID}}",
\t"@graph": [{
'''
	for entity in dictionary.items():
		subj_base_uri = "dataset:{{row.STUDYID}}/{{row.SUBJID|int}}"
		if entity == '??subject':
			scriptbuffer += '\t\t"@id": {},\n'.format(subj_base_uri)
		elif entity == 'NULL':
			#print(WARN: orphaned variables exist)
			continue
		elif entity == '??study':
			continue
		else:
			rel = entity['??subject']
			conj = {'sio:hasPart' : '/part/',
							'sio:isConnectedTo' : '/part/',
							'sio:hasTarget' : '/attr/',
							'sio:hasParticipant' : '/attr/',
							'sio:isRelatedTo' : '/rel/' }
			piece = conj.get(rel, '/attr/')
			etype = entity['@type'].split(['/:#'])[-1]
			scriptbuffer += '\t\t"@id": {},\n'.format(subj_base_uri + conj[rel] + etype)
			

	cl = '''
	\t}]
	}]\'\'\'
	\t].
	'''
	scriptbuffer += cl
	scriptbuffer += "\n\n"
	return scriptbuffer
#/WRITETRANSFORMVALUE



if __name__ == "__main__": main()
