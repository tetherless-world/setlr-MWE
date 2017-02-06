import pandas as pd
import numpy as np
import configparser
import re
import sys

if len(sys.argv) < 2:
	print("USAGE: python mwe.py <config.ini>")
	sys.exit()

config = configparser.ConfigParser()
# 'conf_subj.ini'
config.read(sys.argv[1])

dctfile = config['Source Files']['dictionary']
cbfile = config['Source Files']['codebook']
tlfile = config['Source Files']['timeline']

dct = pd.read_csv(dctfile)
cb = pd.read_csv(cbfile)
tl = pd.read_csv(tlfile)
ontpath = config['Source Files']['ontology']

tname = config['Output Files']['setl_file']

turtle = open(tname, 'w')

prfx = '''@prefix rdf:         <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
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

prefixes = prfx.format(transform = config['Prefixes']['transform_prefix'])

turtle.write(prefixes)

df = config['Prefixes']['data_file']
sf = ''':table a setl:XPORT, setl:Table;
\tprov:wasGeneratedBy [
\t\ta setl:Extract;
\t\tprov:used <{dfile}>;
\t].\n\n'''
turtle.write(sf.format(dfile=df))

#ontology
o = ''':ontology a owl:Ontology;
\tprov:wasGeneratedBy [
\t\ta setl:Extract;
\t\tprov:used <{ontology}>;
\t].\n\n'''
ont = o.format(ontology=ontpath)
turtle.write(ont)

#transform preamble
tp = ''':transform a void:Dataset, dcat:Dataset, setl:Persisted;
\tprov:wasGeneratedBy [
\t\ta setl:Transform, setl:JSLDT;
\t\tprov:used :table;\n'''

turtle.write(tp)

#context
turtle.write("\t\tsetl:hasContext '''{")
ctxt = '''
\t"@vocab" :  "http://hadatac.org/ont/chear#",
\t"sio" :     "http://semanticscience.org/resource/",
\t"chear" :   "http://hadatac.org/ont/chear#",
\t"skos" :    "http://www.w3.org/2004/02/skos/core#",
\t"prov" :    "http://www.w3.org/ns/prov#",
\t"rdfs" :    "http://www.w3.org/2000/01/rdf-schema#",
\t"hbgd" :    "https://hbgd.tw.rpi.edu/ns/",
\t"dataset" : "{base_uri}"\n'''
turtle.write(ctxt.format(base_uri=config['Prefixes']['base_uri']))
turtle.write("\t\t}''';\n")

#transform (prov:value is the transform)
turtle.write("\t\tprov:value '''[{\n")

# the semantic data dictionary
turtle.write('''\t"@id": "dataset:{{row.STUDYID}}",
\t"@graph": [{
\t\t"@id": "dataset:{{row.STUDYID}}/{{row.SUBJID|int}}",
\t\t"@type": "sio:Human",
''')

#.format(column, attribute)
#i default=2
attrstart = '''
{i}"{rel}": [
{i}{{
{i}\t"@id": "dataset:{{{{row.STUDYID}}}}/{{{{row.SUBJID|int}}}}{tail}",
{i}\t"@type": ["sio:Attribute", "hbgd:HBGDkiConcept", "hbgd:Variable", "{attr}" ],
{i}\t"rdfs:label": "{label}"'''

#i default=3
mat = ''',\n{i}"sio:measuredAt" : [
{i}{{
{i}\t"@id":"dataset:{{{{row.STUDYID}}}}/{{{{row.SUBJID|int}}}}/timepoint/{timepoint}"
{i}}}]'''


#i default=2
other_subject = '''
{i}"{relation}" :[
{i}{{
{i}\t"@id": "dataset:{{{{row.STUDYID}}}}/{{{{row.SUBJID|int}}}}{tail}",
{i}\t"@type": "{tp}",'''

other_subject_tail = '''/{entconj}/{part}{at}'''
attr_tail = '''/{atrconj}/{col}'''

#i default=2
close = '''
{i}}}],'''


#i default=2
cbthing = '''
{i}"{rel}" :[
{i}'''


#i default=3
cbtype = '''\t{{
{i}\t"@if": "{{{{row.{col}|int}}}} == '{code}'",
{i}\t"@id": "dataset:{{{{row.STUDYID}}}}/{{{{row.SUBJID|int}}}}/{atrconj}/{col}/{{{{row.{col}}}}}",
{i}\t"@type": ["{atr}", "{cls}"],
{i}\t"sio:hasValue": {{ "@value": "{lbl}" }}
{i}}},'''

#i default=2
yn = '''
{i}"{rel}" :[
{i}\t{{
{i}\t"@if": "{{{{row.{col}|int}}}} == '1'",
{i}\t"@id": "dataset:{{{{row.STUDYID}}}}/{{{{row.SUBJID|int}}}}/{atrconj}/{col}",
{i}\t"@type": ["sio:Attribute", "hbgd:HBGDkiConcept", "hbgd:Variable","{atr}"],
{i}\t"rdfs:label": "{lbl}"
{i}\t}}],'''

u =''',\n{i}"sio:hasUnit": {{ "@value": "{unit}" }}'''
hv = ''',\n{i}"sio:hasValue": {{ "@value": "{{{{row.{col}}}}}", "@type": "{datatype}" }}'''

numrows = dct.shape[0]
numcb = cb.shape[0]

#timepoints
tl_dict = {}
#0:index 1:name 2:start 3:end 4:unit 5:type
for tlrow in tl.itertuples():
	tl_dict[tlrow[5]] = tlrow[1]

#codebook
cb_dict = {}
# (0:index), 1:Column, [2:Value OR 3:Code], 4:Full Name, 5:Class
for cbrow in cb.itertuples():
	column_key = cbrow[1]
	if column_key not in cb_dict:
		cb_dict[column_key] = {}
	if pd.notnull(cbrow[2]): #value is a number
		val_key = str(int(cbrow[2]))
	elif pd.notnull(cbrow[3]): #value is a code
		val_key = cbrow[3].strip()
	else: #why are we here?
		print('extra row in codebook?')
		continue 
	new_value = (cbrow[4], cbrow[5])
	cb_dict[column_key][val_key] = new_value

#0:index 1:column 2:label 3:attribute 4:attributeOf 5:entity-conj 6:attr-conj 7:time 8:entity 9:role 10:relation 11:inRelationTo 12:hasUnit 13:datatype
for row in dct.itertuples():
	toAdd = ''
	indent = ''
	#CODEBOOK HANDLING
	if pd.notnull(row[13]) and row[13] == 'CODEBOOK':
		col = row[1]
		attribute = ''
		if pd.notnull(row[3]):
			attribute = row[3]
		label = row[2]
		rel = ''
		if pd.isnull(row[10]):
			rel = 'sio:hasAttribute'
		else:
			rel = row[10]
		indent = '\t'*2
		toAdd = cbthing.format(i=indent, rel=rel)
		for k, v in subdict.items():
			if k.isdigit():
				col_f = col + '|int'
			else: #the value is a code
				val = k.strip()
			indent = '\t'*3
			toAdd += cbtype.format(i=indent, col=col, col_f=col_f, atrconj='attr', code=k, atr=attribute, cls=subdict[k][1], lbl=subdict[k][0])
		toAdd = toAdd[:-1] #slice off last comma
		toAdd += '\n\t\t],'
	
	#Y/N FLAG HANDLING
	elif pd.notnull(row[13]) and row[13] == 'YN':
		col = row[1]
		attribute = ''
		if pd.notnull(row[3]):
			attribute = row[3]
		label = row[2]
		rel = 'sio:hasAttribute'
		ac = 'attr'
		if pd.notnull(row[10]):
			rel = row[10]
		if pd.notnull(row[6]):
			ac = row[6]
		indent = '\t'*2
		toAdd = yn.format(i=indent, rel=rel, col=col, atrconj=ac, code=val, atr=attribute, lbl=label)
	
	#EVERYTHING NOT IN THE CODEBOOK
	elif pd.notnull(row[3]):
		if pd.notnull(row[4]): 
			if row[4] == 'sio:Human':
			# the subject of the row is the child
				col = row[1]
				attribute = row[3]
				label = row[2]
				ac = 'attr' #attribute conjunction
				if pd.notnull(row[6]):
					ac = row[6]
				if pd.isnull(row[10]):
					rel = 'sio:hasAttribute'
				else:
					rel = row[10]
				t = attr_tail.format(atrconj=ac, col=col)
				if pd.notnull(row[6]) and row[6] == 'loc':
						t = attr_tail.format(atrconj=ac, col='{{{{row.{c}|int}}}}'.format(c=col))
				indent = '\t'*2
				toAdd = attrstart.format(i=indent, rel=rel, tail=t, attr=attribute, label=label)
				if pd.notnull(row[7]):
					indent = '\t'*3
					toAdd += mat.format(i=indent, timepoint=tl_dict[row[7]])
				indent = '\t'*3
				if pd.isnull(row[13]):
					dt = ''
				else:
					dt = row[13]
				if pd.notnull(row[12]):
					toAdd += u.format(i=indent, unit=row[12])
				toAdd += hv.format(i=indent, col=col, datatype=dt)
				indent = '\t'*2
				toAdd += close.format(i=indent)
			else:
			# the subject of the row is something else
				if pd.isnull(row[10]):
					continue
				rel = row[10]
				col = row[1]
				attribute = row[3]
				label = row[2]
				#entity conjunction
				ec = ''
				if pd.notnull(row[5]):
					ec = row[5]
				#attribute conjunction
				ac = 'attr' 
				if pd.notnull(row[6]):
					ac = row[6]
				plabel = re.split('\W+', row[4])[-1]
				indent = '\t'*2
				toAdd = other_subject.format(i=indent, relation=rel, tail=other_subject_tail.format(entconj=ec, part=plabel, at=''), tp=row[4])
				indent = '\t'*3
				toAdd += attrstart.format(i=indent, rel='sio:hasAttribute', tail=other_subject_tail.format(entconj=ec, part=plabel, at=attr_tail.format(atrconj=ac,col=col)), attr=attribute, label=label)
				if pd.notnull(row[7]):
					indent = '\t'*4
					toAdd += mat.format(i=indent, timepoint=tl_dict[row[7]])
				indent = '\t'*4
				if pd.isnull(row[13]):
					dt = ''
				else:
					dt = row[13]
				if pd.notnull(row[12]):
					toAdd += u.format(i=indent, unit=row[12])
				indent = '\t'*3
				toAdd += close.format(i=indent)[:-1]
				indent = '\t'*2
				toAdd += close.format(i=indent)				
	if row[0] == (numrows-1):
		toAdd = toAdd[:-1]
	turtle.write(toAdd)

cl = '''
\t}]
}]\'\'\'
\t].
'''

turtle.write(cl)
#/transform
turtle.write("\n\n")

ft = config['Output Files']['converted_type']
fname = config['Output Files']['converted_file']

#load
ld = '''<{name}> a pv:File;
\tdcterms:format "{ftype}";
\tprov:wasGeneratedBy [
\t\ta setl:Load;
\t\tprov:used :transform ;
\t].'''

load = ld.format(name=fname, ftype=ft)

turtle.write(load)

turtle.close()
