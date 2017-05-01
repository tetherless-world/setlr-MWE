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
	turtle.write(prefixes)
	
	#WRITE DATA FILE EXTRACT
	df = config['Data Files']['data_file']
	extract = writeDataFileExtract(df)
	turtle.write(extract)

	#ontology
	o = ''':ontology a owl:Ontology;
\tprov:wasGeneratedBy [
\t\ta setl:Extract;
\t\tprov:used <{ontology}>;
\t].\n\n'''
	ont = o.format(ontology=ontpath)
	turtle.write(ont)

	base_uri = config['Prefixes']['base_uri']
	tfcontext = writeTransformContext(base_uri)
	turtle.write(tfcontext)

	#theTransform = writeTransformValue(cb, dct, tl)
	theCodebook,theSDD,theTimeline = compileSDD(cb, dct, tl)
#	for concept in theSDD:
#		print concept
#	print theSDD
	with open("testSDD.json","w") as f:
		json.dump(theSDD,f)
#	with open("testCB.json","w") as f:
#		json.dump(theCodebook,f)
#	with open("testTP.json","w") as f:
#		json.dump(theTimeline,f)
	test_sb = writeTransformValue(theCodebook,theSDD,theTimeline)
	turtle.write(test_sb)
	
	theLoad = writeLoad(out_fname)
	turtle.write(theLoad)
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
#			else:
#				print("WARN: untyped variable {}".format(row[1]))
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
	numents = len(dictionary)
	scriptbuffer = "\t\tprov:value '''[{\n"

	# the semantic data dictionary
	scriptbuffer += '''\t"@id": "dataset:{{row.get('STUDYID')}}",
\t"@graph": [
'''
	#TEMPLATES LIVE HERE
	conj = {'sio:isPartOf' : '/part/',
					'sio:isConnectedTo' : '/part/',
					'sio:hasTarget' : '/attr/',
					'sio:hasParticipant' : '/attr/',
					'sio:existsAt' : '/timepoint/', #fix VISIT stuff
					'sio:isRelatedTo' : '/rel/' }
	tp = {'??birth' : '1',
				'??visit' : "{{row.get('VISIT')}}",
				'??preganncy' : 'EFO_0002950'}
	subj_template ='''\t{{
{i}"@id": "{uri}",
{i}"@type" : "{tp}",
'''
	entity_template = '''\t{{
{i}{entcond}
{i}"@id": "{uri}",
{i}"@type" : "{tp}",
{i}"{rel}" : "{subj}",
'''
	entity_conditional = '''{c}\'{prop}\' in row'''

	relation_template = '''{i}"{rel}": [
{i}{{
{i}\t"@if": "'{col}' in row",
{i}\t"@id": "dataset:{{{{row['STUDYID']}}}}/{{{{row['SUBJID']|int}}}}/attr/{col}",
{i}\t"@type": ["sio:Attribute", "hbgd:HBGDkiConcept", "hbgd:Variable", "{attr}" ],
{i}\t"rdfs:label": "{label}"{m_at}{unit}{value}
{i}}}]'''

	unit_template =''',\n{i}\t"sio:hasUnit": {{ "@value": "{unit}" }}'''

	hasv_template = ''',\n{i}\t"sio:hasValue": {{ "@value": "{{{{row['{col}']}}}}" }}'''

	mat_template = ''',\n{i}\t"sio:measuredAt" : [{{
{i}\t\t"@id":"dataset:{{{{row['STUDYID']}}}}/{{{{row['SUBJID']|int}}}}/timepoint/{timepoint}"
{i}\t}}]'''

#	cl_temp = '''
#{i}}}]'''
	cl = '''
\t]
}]\'\'\'
\t].
'''

	numEnts = len(dictionary.items())
	countEnts = 0
	for entity,vals in dictionary.items():
		countEnts += 1
		subj_base_uri = "dataset:{{row.STUDYID}}/{{row.SUBJID|int}}"
#SAD VARIABLES :(((
		if entity == 'NULL':
			#print(WARN: orphaned variables exist)
			if countEnts == numEnts:
				scriptbuffer = scriptbuffer[:-2] + '\n'				
			continue
#WRITE THE STUDY
		elif entity == '??study':
			if countEnts == numEnts:
				scriptbuffer = scriptbuffer[:-2] + '\n'				
			continue
#WRITE THE SUBJECT
		elif entity == '??subject':
			i = '\t'*2
			scriptbuffer += subj_template.format(i=i, uri=subj_base_uri, tp=vals['@type'])
			numRels = len(vals)
			countRels = 0
			for rel in vals.keys():
				if rel in {'??subject', '@type', 'sio:hasRole'}:
					countRels += 1
					if countRels == numRels:
						scriptbuffer = scriptbuffer[:-2] + '\n'
					continue
				else:
					countRels += 1
					numStuff = len(vals[rel])
					countStuff = 0
					for var, deets in vals[rel].items():
						countStuff += 1
						if var not in codebook.keys():
							i = '\t'*2
							attr = ''
							label = ''
							unit = ''
							hasv = hasv_template.format(i=i, col=var)
							mat = ''
							if 'rdfs:subClassOf' in deets.keys():
								attr = str(deets['rdfs:subClassOf'])
							if 'rdfs:label' in deets.keys():
								label = str(deets['rdfs:label'])
							if 'sio:hasUnit' in deets.keys():
								unit = unit_template.format(i=i, unit=str(deets['sio:hasUnit']))
							if 'sio:measuredAt' in deets.keys():
								mat = mat_template.format(i=i, timepoint=tp.get(str(deets['sio:measuredAt']), 'UNKNOWN'))
							scriptbuffer += relation_template.format(i=i, rel=rel, col=var, attr=attr, label=label, m_at = mat, unit=unit, value=hasv)
						else:
							scriptbuffer += writeCodebook(codebook, var, rel)
						if countStuff < numStuff:
							scriptbuffer += ',\n'
						else:
							scriptbuffer += '\n'
				if countRels < numRels:
					scriptbuffer = scriptbuffer[:-1]
					scriptbuffer += ',\n'
			if countEnts < numEnts:
				scriptbuffer += '\t},\n'
			else:
				scriptbuffer += '\n'

#WRITE THE OTHER STUFF
		else:
			rel = vals['??subject']
			piece = conj.get(rel, '/attr/')
			etype = str(vals['@type']).strip()
			numRels = len(vals)
			ec = ''
			if 'sio:hasAttribute' in vals.keys():
				ec = '"@if": "'
				numAttrs = len(vals['sio:hasAttribute'].items())
				countAttrs = 0
				for var, deets in vals['sio:hasAttribute'].items():
					if countAttrs == 0:
						ec += entity_conditional.format(c='', prop=var)
					else:
						ec += entity_conditional.format(c=' or ', prop=var)
					countAttrs += 1
					if countAttrs == numAttrs:
						ec += '",'
			uri = subj_base_uri + conj[rel] + str(entity[2:]).upper()
			i = '\t'*2
			scriptbuffer += entity_template.format(i=i, entcond=ec, uri=uri, tp=etype, rel=rel, subj=subj_base_uri)
			countRels = 0
			for rel in vals.keys():
				if rel in {'??subject', '@type', 'sio:hasRole'}:
					countRels += 1
					continue
				else: 
					countRels += 1
					numStuff = len(vals[rel])
					countStuff = 0
					for var, deets in vals[rel].items():
						countStuff += 1
						if var not in codebook.keys():
							i = '\t'*2
							attr = ''
							label = ''
							unit = ''
							hasv = hasv_template.format(i=i, col=var)
							mat = ''
							if 'rdfs:subClassOf' in deets.keys():
								attr = str(deets['rdfs:subClassOf'])
							if 'rdfs:label' in deets.keys():
								label = str(deets['rdfs:label'])
							if 'sio:hasUnit' in deets.keys():
								unit = unit_template.format(i=i, unit=str(deets['sio:hasUnit']))
							if 'sio:measuredAt' in deets.keys():
								mat = mat_template.format(i=i, timepoint=tp.get(str(deets['sio:measuredAt'])))
							scriptbuffer += relation_template.format(i=i, rel=rel, col=var, attr=attr, label=label, m_at = mat, unit=unit, value=hasv)
						else:
							scriptbuffer += writeCodebook(codebook, var, rel)
						if countStuff < numStuff:
							scriptbuffer += ',\n'
						else:
							scriptbuffer += '\n'
			if countEnts < numEnts:
				scriptbuffer += '\t},\n'
			else:
				scriptbuffer += '\n'


	scriptbuffer += cl
	scriptbuffer += "\n\n"
	return scriptbuffer
#/WRITETRANSFORMVALUE



# Call this in the above method to write a codebook entry.
# TAKES the codebook and a variable
# RETURNS a formatted template string for that variable's codebook options
def writeCodebook(cb, var, rel):
	#i default=2
	cb_start = '''
{i}"{rel}": ['''

	#i default=3
	cb_template= '''\n{i}{{
{i}\t"@if": "{{{{row.{col_f}}}}} == '{code}'",
{i}\t"@id": "dataset:{{{{row.STUDYID}}}}/{{{{row.SUBJID|int}}}}/attr/{col}/{{{{row.get('{col_f}')}}}}",
{i}\t"@type": ["{cls}"],
{i}\t"sio:hasValue": [{{ "@value": "{lbl}" }}]
{i}}},'''
	
	i = '\t'*2
	cbstring = cb_start.format(i=i, rel=rel)

	sub_book = cb[var]
	i = '\t'*2
	for code, info in sub_book.items():
		col_f = var
		label = str(info['sio:hasValue'])
		cls = str(info['@type'])
		if code.isdigit():
			col_f = var + '|int'
		else:
			col_f = col_f.strip()
		cbstring += cb_template.format(i=i, col=var, col_f=col_f, code=code, cls=cls, lbl=label)
	cbstring = cbstring[:-1] #slice off last comma
	cbstring += ']'
	return cbstring




#WRITE LOAD
def writeLoad(fname):
	suffix = fname.split('.')[-1].lower()
	output_filetypes = {
				"rdf" : '"default", "application/rdf+xml", "text/rdf"',
				"xml" : '"default", "application/rdf+xml", "text/rdf"',
				"ttl" : '"text/turtle", "application/turtle", "application/x-turtle"',
				"nt" : "text/plain",
				"n3" : "text/n3",
				"trig" : "application/trig",
				"json" : "application/json" }
	try:
		ftype = output_filetypes[suffix]
	except KeyError:
		print('Invalid or unsupported output type: ' + fname)
		sys.exit()
	scriptbuffer=''
	ld = '''<{name}> a pv:File;
\tdcterms:format {ftype};
\tprov:wasGeneratedBy [
\t\ta setl:Load;
\t\tprov:used :transform ;
\t].'''
	load = ld.format(name=fname, ftype=ftype)
	scriptbuffer += load
	return scriptbuffer
#/writeLoad()

if __name__ == "__main__": main()
