# setlr-MWE

The MWE script is for automatic generation of SETLr files based on a Semantic Data Dictionary file. The MWE script does not generate linked data on its own, but rather outputs a setl.ttl file intended to perform this conversion. As the layer above the Turtle file of SETLr, MWE stands for "mighty world elephant", in reference to the cosmology of Sir Terry Pratchett's Discworld series.

The SETLr repository is located at https://github.com/tetherless-world/setlr

This repository contains: 
- MWE script
- MWE config template

You will need to provide the following items:
- the ontology for your project
- data file(s) conforming to your dictionary
- Semantic Data Dictionary spreadsheet, including
-- dictionary
-- codebook
-- timeline/timepoint

A blank Semantic Data Dictionary template may become part of this repo in the future

=== Configuration:
[Prefixes] allows you to designate the prefixes associated with your data transformation, and resulting linked data.
- transform_prefix is for provenance purposes
- base_uri is for coining URI's for the final linked data

[Source Files] contains the parts of the Semantic Data Dictionary. Variable names in this section specify which field holds the path to each section of the SDD

[Data Files] fields describe the data file you wish to convert
- data_format is the format of the file. Supported formats are those supported by SETLr: CSV/TSV, SAS Transport and SAS Dataset file formats, OWL and RDF
- data_file holds the path to the file itself

[Output Files] fields allow you to name the artifacts from the MWE and SETLr process. Note that you select a file name and type for your output format here, even though the MWE does not produce the final linked data - this information is captured in the SETL file anyway as prospective provenance
- setl_file is the name you want to use for the SETLr file this script will produce
- converted_type dictates the file format you want for the linked data output. Supported formats are those supported by SETLr: RDF/XML, Turtle, N-Triples, N3, TriG, and JSON-LD
- converted_file names the linked data output file itself

