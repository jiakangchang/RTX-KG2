#!/usr/bin/env python3
''' kegg_json_to_kg_json.py: Extracts a KG2 JSON file from a
    KEGG API JSON dump

    Usage: kegg_json_to_kg_json.py [--test] <inputFile.json>
    <outputNodesFile.json> <outputEdgesFile.json>
'''

import json
import kg2_util
import argparse
import os
import re
import datetime

__author__ = 'Erica Wood'
__copyright__ = 'Oregon State University'
__credits__ = ['Stephen Ramsey', 'Erica Wood']
__license__ = 'MIT'
__version__ = '0.1.0'
__maintainer__ = ''
__email__ = ''
__status__ = 'Prototype'

KEGG_COMPOUND_PREFIX = re.compile(r'(cpd:|C)')
KEGG_PATHWAY_PREFIX = re.compile(r'(hsa)')
KEGG_ENZYME_PREFIX = re.compile(r'[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+')
KEGG_GLYCAN_PREFIX = re.compile(r'(gl:|G)')
KEGG_DRUG_PREFIX = re.compile(r'(dr:|D)')
KEGG_REACTION_PREFIX = re.compile(r'(R)')

KEGG_PATHWAY_CURIE_PREFIX = kg2_util.CURIE_PREFIX_KEGG
KEGG_COMPOUND_CURIE_PREFIX = kg2_util.CURIE_PREFIX_KEGG_COMPOUND
KEGG_DRUG_CURIE_PREFIX = kg2_util.CURIE_PREFIX_KEGG_DRUG
KEGG_ENZYME_CURIE_PREFIX = kg2_util.CURIE_PREFIX_KEGG_ENZYME
KEGG_GLYCAN_CURIE_PREFIX = kg2_util.CURIE_PREFIX_KEGG_GLYCAN
KEGG_REACTION_CURIE_PREFIX = kg2_util.CURIE_PREFIX_KEGG_REACTION
CHEMBL_COMPOUND_CURIE_PREFIX = kg2_util.CURIE_PREFIX_CHEMBL_COMPOUND
CHEBI_CURIE_PREFIX = kg2_util.CURIE_PREFIX_CHEBI
RHEA_CURIE_PREFIX = kg2_util.CURIE_PREFIX_RHEA
GO_CURIE_PREFIX = kg2_util.CURIE_PREFIX_GO

KEGG_BASE_COMPOUND_IRI = kg2_util.BASE_URL_KEGG_COMPOUND
KEGG_BASE_DRUG_IRI = kg2_util.BASE_URL_KEGG_DRUG
KEGG_BASE_ENZYME_IRI = kg2_util.BASE_URL_KEGG_ENZYME
KEGG_BASE_GLYCAN_IRI = kg2_util.BASE_URL_KEGG_GLYCAN
KEGG_BASE_REACTION_IRI = kg2_util.BASE_URL_KEGG_REACTION
KEGG_BASE_PATHWAY_IRI = kg2_util.BASE_URL_KEGG
KEGG_PROVIDED_BY = kg2_util.CURIE_ID_KEGG
KEGG_SOURCE_IRI = "https://www.genome.jp"
KEGG_RELATION_CURIE_PREFIX = KEGG_PATHWAY_CURIE_PREFIX

CURIE_PREFIX_TO_BASE_IRI = {KEGG_COMPOUND_CURIE_PREFIX: KEGG_BASE_COMPOUND_IRI,
                            KEGG_DRUG_CURIE_PREFIX: KEGG_BASE_DRUG_IRI,
                            KEGG_ENZYME_CURIE_PREFIX: KEGG_BASE_ENZYME_IRI,
                            KEGG_GLYCAN_CURIE_PREFIX: KEGG_BASE_GLYCAN_IRI,
                            KEGG_REACTION_CURIE_PREFIX: KEGG_BASE_REACTION_IRI,
                            KEGG_PATHWAY_CURIE_PREFIX: KEGG_BASE_PATHWAY_IRI}


def get_args():
    arg_parser = argparse.ArgumentParser(description='kegg_json_to_kg_json.py: \
                                         builds a KG2 JSON representation of \
                                         KEGG')
    arg_parser.add_argument('--test', dest='test',
                            action="store_true", default=False)
    arg_parser.add_argument('inputFile', type=str)
    arg_parser.add_argument('outputNodesFile', type=str)
    arg_parser.add_argument('outputEdgesFile', type=str)
    return arg_parser.parse_args()


def date():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def format_node(node_id,
                name,
                category_label,
                update_date,
                description=None,
                sequence=None,
                synonym=[]):
    curie_id = format_id(node_id)
    iri = CURIE_PREFIX_TO_BASE_IRI[curie_id.split(':')[0]] + node_id
    node = kg2_util.make_node(curie_id,
                              iri,
                              name,
                              category_label,
                              update_date,
                              KEGG_PROVIDED_BY)
    if description is not None and len(description) > 0:
        node['description'] = description
    if sequence is not None and len(sequence) > 0:
        node['has_biological_sequence'] = sequence
    node['synonym'] = synonym

    return node


def format_same_as_edge(kegg_id, external_id, update_date):
    edge = kg2_util.make_edge_biolink(format_id(kegg_id),
                                      external_id,
                                      kg2_util.EDGE_LABEL_BIOLINK_SAME_AS,
                                      KEGG_PROVIDED_BY,
                                      update_date)
    return edge


def format_in_taxon_edge(kegg_id, external_id, update_date):
    edge = kg2_util.make_edge_biolink(format_id(kegg_id),
                                      external_id,
                                      kg2_util.EDGE_LABEL_BIOLINK_IN_TAXON,
                                      KEGG_PROVIDED_BY,
                                      update_date)
    return edge


def format_kegg_edge(subject_id, object_id, update_date):
    subject_temp_id = format_id(subject_id).replace(KEGG_PATHWAY_CURIE_PREFIX + ':', KEGG_PATHWAY_CURIE_PREFIX + '.PATHWAY:')
    object_temp_id = object_id.replace(KEGG_PATHWAY_CURIE_PREFIX + ':', KEGG_PATHWAY_CURIE_PREFIX + '.PATHWAY:')
    relation_label = subject_temp_id.replace('KEGG.', '').split(':')[0].lower() + '_to_' + object_temp_id.replace('KEGG.', '').split(':')[0].lower()
    relation_curie = kg2_util.predicate_label_to_curie(relation_label,
                                                       KEGG_RELATION_CURIE_PREFIX)
    edge = kg2_util.make_edge(format_id(subject_id),
                              object_id,
                              relation_curie,
                              relation_label,
                              KEGG_PROVIDED_BY,
                              update_date)
    return edge


def process_xref(xref):
    xref = xref.replace(': ', ':')
    prefix = xref.split(':')[0] + ':'
    xrefs = [prefix + xref_id.replace(prefix, '') for xref_id in xref.split(' ')]
    allowed_xrefs = {'ChEBI': CHEBI_CURIE_PREFIX,
                     'ChEMBL': CHEMBL_COMPOUND_CURIE_PREFIX,
                     'RHEA': RHEA_CURIE_PREFIX,
                     'GO': GO_CURIE_PREFIX}
    return_xrefs = []
    for xref in xrefs:
        if xref.split(':')[0] in allowed_xrefs:
            for allowed_xref in allowed_xrefs:
                xref = xref.replace(allowed_xref, allowed_xrefs[allowed_xref])
            return_xrefs.append(xref)
    return return_xrefs


def format_id(kegg_id):
    if len(kegg_id.split('.')) > 2:
        return KEGG_ENZYME_CURIE_PREFIX + ':' + kegg_id
    id_start_map = {'C': KEGG_COMPOUND_CURIE_PREFIX,
                    'D': KEGG_DRUG_CURIE_PREFIX,
                    'G': KEGG_GLYCAN_CURIE_PREFIX,
                    'R': KEGG_REACTION_CURIE_PREFIX}
    first_letter = kegg_id[0]
    if first_letter in id_start_map:
        return id_start_map[first_letter] + ':' + kegg_id
    return KEGG_PATHWAY_CURIE_PREFIX + ':' + kegg_id.strip('hsa').strip('map').strip('rn').strip('ec')


def add_unique_to_list(input_list, item):
    input_list = set(input_list)
    input_list.add(item)
    return sorted(list(input_list))


def pull_out_pathways(data_dict):
    pathways_return = data_dict.get('PATHWAY', [])
    pathways = []
    if isinstance(pathways_return, list):
        for pathway in pathways_return:
            pathways.append(format_id(pathway.split(' ')[0].strip()))
    else:
        pathways.append(format_id(pathways_return.split(' ')[0].strip()))
    return pathways


def pull_out_reactions(data_dict):
    reactions_return = data_dict.get('REACTION', [])
    reactions = []
    if isinstance(reactions_return, list):
        for reaction_list in reactions_return:
            reactions += [format_id(reaction.strip()) for reaction in reaction_list.split()]
    else:
        reactions += [format_id(reaction.strip()) for reaction in reactions_return.split()]
    return reactions


def pull_out_enzymes(data_dict):
    enzymes_return = data_dict.get('ENZYME', [])
    enzymes = []
    if isinstance(enzymes_return, list):
        for enzyme_list in enzymes_return:
            enzymes += [format_id(enzyme.strip()) for enzyme in enzyme_list.split() if '-' not in enzyme]
    else:
        enzymes += [format_id(enzyme.strip()) for enzyme in enzymes_return.split() if '-' not in enzyme]
    return enzymes


def pull_out_compounds(data_dict):
    compounds_return = data_dict.get('COMPOUND', [])
    compounds = []
    if isinstance(compounds_return, list):
        for compound in compounds_return:
            compounds.append(format_id(compound.split()[0].strip()))
    else:
        compounds.append(format_id(compounds_return.split()[0].strip()))
    return compounds


def pull_out_drugs(data_dict):
    drugs_return = data_dict.get('DRUG', [])
    drugs = []
    if isinstance(drugs_return, list):
        for drug in drugs_return:
            drugs.append(format_id(drug.split()[0].strip()))
    else:
        drugs.append(format_id(drugs_return.split()[0].strip()))
    return drugs


def pull_out_glycans(data_dict):
    glycans_return = data_dict.get('GLYCAN', [])
    glycans = []
    if isinstance(glycans_return, list):
        for glycan in glycans_return:
            glycans.append(format_id(glycan.split()[0].strip()))
    else:
        glycans.append(format_id(glycans_return.split()[0].strip()))
    return glycans


def process_sequence(data_dict):
    sequence_return = data_dict.get('SEQUENCE', None)
    sequence = ''
    if sequence_return is None:
        return None
    if isinstance(sequence_return, list):
        for sequence_string in sequence_return:
            if sequence_string.startswith('GENE') or sequence_string.startswith('ORGANISM') or sequence_string.startswith('TYPE'):
                break
            sequence += sequence_string + ' '
        return sequence.strip()
    else:
        return sequence_return


def process_references(data_dict):
    publications = []
    reference_list = data_dict.get('REFERENCE', [])
    for item in reference_list:
        if kg2_util.CURIE_PREFIX_PMID in item:
            publication = item.split(']')[0]
            try:
                publication = publication.split('[')[1]
            except IndexError:
                publication = publication
            publication = publication.replace('PMID:', kg2_util.CURIE_PREFIX_PMID + ':')
            publications.append(publication)
    return publications


def get_node_basics(data_dict):
    node_name = data_dict.get('name', '')
    synonym = [syn.strip() for syn in node_name.split(';')]
    node_name = synonym.pop(0)
    xrefs = data_dict.get('DBLINKS', '')
    if isinstance(xrefs, str):
        xrefs = [xrefs]
    processed_xrefs = []
    for xref in xrefs:
        processed_xrefs += process_xref(xref)
    return node_name, synonym, processed_xrefs


def process_compound(compound_dict, kegg_id, nodes_output, edges_output, update_date):
    node_id = kegg_id.replace('cpd:', '')
    node_name, synonym, processed_xrefs = get_node_basics(compound_dict)

    enzymes = pull_out_enzymes(compound_dict)
    reactions = pull_out_reactions(compound_dict)
    pathways = pull_out_pathways(compound_dict)
    sequence = process_sequence(compound_dict)

    node = format_node(node_id,
                       node_name,
                       kg2_util.BIOLINK_CATEGORY_SMALL_MOLECULE,
                       update_date,
                       sequence=sequence,
                       synonym=synonym)
    nodes_output.write(node)

    for xref in processed_xrefs:
        edges_output.write(format_same_as_edge(node_id,
                                         xref,
                                         update_date))
    for enzyme in enzymes:
        edges_output.write(format_kegg_edge(node_id, enzyme, update_date))
    for reaction in reactions:
        edges_output.write(format_kegg_edge(node_id, reaction, update_date))
    for pathway in pathways:
        edges_output.write(format_kegg_edge(node_id, pathway, update_date))


def process_reaction(reaction_dict, kegg_id, nodes_output, edges_output, update_date):
    node_id = kegg_id
    description = reaction_dict.get('DEFINITION', '').strip()
    node_name, synonym, xrefs = get_node_basics(reaction_dict)
    enzymes = pull_out_enzymes(reaction_dict)
    pathways = pull_out_pathways(reaction_dict)

    node = format_node(node_id,
                       node_name,
                       kg2_util.BIOLINK_CATEGORY_MOLECULAR_ACTIVITY,
                       update_date,
                       synonym=synonym,
                       description=description)
    nodes_output.write(node)

    for xref in xrefs:
        edges_output.write(format_same_as_edge(node_id,
                                         xref,
                                         update_date))
    for enzyme in enzymes:
        edges_output.write(format_kegg_edge(node_id, enzyme, update_date))
    for pathway in pathways:
        edges_output.write(format_kegg_edge(node_id, pathway, update_date))


def process_pathway(pathway_dict, kegg_id, nodes_output, edges_output, update_date):
    node_id = kegg_id.replace('hsa', '')
    node_name, synonym, processed_xrefs = get_node_basics(pathway_dict)
    compounds = pull_out_compounds(pathway_dict)
    drugs = pull_out_drugs(pathway_dict)
    glycans = pull_out_glycans(pathway_dict)
    edges = []

    human_string = ' - Homo sapiens (human)'
    if human_string in node_name:
        edges.append(format_in_taxon_edge(node_id,
                                          kg2_util.CURIE_PREFIX_NCBI_TAXON + ':'+ str(kg2_util.NCBI_TAXON_ID_HUMAN),
                                          update_date))
        node_name = node_name.replace(human_string, '')

    node = format_node(node_id,
                       node_name,
                       kg2_util.BIOLINK_CATEGORY_PATHWAY,
                       update_date,
                       synonym=synonym)
    node['publications'] = process_references(pathway_dict)
    nodes_output.write(node)
    
    for xref in processed_xrefs:
        edges_output.write(format_same_as_edge(node_id,
                                         xref,
                                         update_date))
    for compound in compounds:
        edges_output.write(format_kegg_edge(node_id, compound, update_date))
    for drug in drugs:
        edges_output.write(format_kegg_edge(node_id, drug, update_date))
    for glycan in glycans:
        edges_output.write(format_kegg_edge(node_id, glycan, update_date))


def process_drug(drug_dict, kegg_id, nodes_output, edges_output, update_date):
    node_id = kegg_id.replace('dr:', '')
    node_name, synonym, processed_xrefs = get_node_basics(drug_dict)
    description = drug_dict.get('COMMENT', '')
    if isinstance(description, list):
        description = ', '.join(description)
    description = description.strip()

    node = format_node(node_id,
                       node_name,
                       kg2_util.BIOLINK_CATEGORY_DRUG,
                       update_date,
                       synonym=synonym,
                       description=description)
    nodes_output.write(node)

    for xref in processed_xrefs:
        edges_output.write(format_same_as_edge(node_id,
                                         xref,
                                         update_date))


def process_glycan(glycan_dict, kegg_id, nodes_output, edges_output, update_date):
    node_id = kegg_id.replace('gl:', '')
    node_name, synonym, processed_xrefs = get_node_basics(glycan_dict)
    reactions = pull_out_reactions(glycan_dict)
    pathways = pull_out_pathways(glycan_dict)
    enzymes = pull_out_enzymes(glycan_dict)
    eq_id = glycan_dict.get('eq_id', None)
    equivalent_compounds = glycan_dict.get('REMARK', '').replace('Same as: ', '')
    if eq_id is not None and len(eq_id) > 0:
        eq_id = eq_id.replace('chebi', CHEBI_CURIE_PREFIX)
        processed_xrefs = add_unique_to_list(processed_xrefs, eq_id)
    for equivalent_compound in equivalent_compounds.split():
        processed_xrefs = add_unique_to_list(processed_xrefs, format_id(equivalent_compound))

    node = format_node(node_id,
                       node_name,
                       kg2_util.BIOLINK_CATEGORY_SMALL_MOLECULE,
                       update_date,
                       synonym=synonym)
    nodes_output.write(node)

    for xref in processed_xrefs:
        edges_output.write(format_same_as_edge(node_id,
                                         xref,
                                         update_date))
    for reaction in reactions:
        edges_output.write(format_kegg_edge(node_id, reaction, update_date))
    for pathway in pathways:
        edges_output.write(format_kegg_edge(node_id, pathway, update_date))
    for enzyme in enzymes:
        edges_output.write(format_kegg_edge(node_id, enzyme, update_date))


def pull_out_enzyme_reactions(data_dict):
    reactions = []
    reaction_return = data_dict.get('REACTION', None)
    if reaction_return is not None:
        if isinstance(reaction_return, list):
            for reaction in reaction_return:
                reaction = reaction.split('[')[-1].split(']')[0].replace('RN:', KEGG_REACTION_CURIE_PREFIX + ':')
                if reaction.startswith(KEGG_REACTION_CURIE_PREFIX):
                    reaction = [KEGG_REACTION_CURIE_PREFIX + ':' + reac.replace(KEGG_REACTION_CURIE_PREFIX + ':', '') for reac in reaction.split()]
                    reactions += reaction
        else:
            reaction = reaction_return.split('[')[-1].split(']')[0].replace('RN:', KEGG_REACTION_CURIE_PREFIX + ':')
            if reaction.startswith(KEGG_REACTION_CURIE_PREFIX):
                reaction = [KEGG_REACTION_CURIE_PREFIX + ':' + reac.replace(KEGG_REACTION_CURIE_PREFIX + ':' , '') for reac in reaction.split()]
                reactions += reaction
    return reactions


def process_enzyme(enzyme_dict, kegg_id, nodes_output, edges_output, update_date):
    node_id = kegg_id
    node_name, synonym, processed_xrefs = get_node_basics(enzyme_dict)
    description = enzyme_dict.get('COMMENT', '')
    if isinstance(description, list):
        description = ', '.join(description)
    description = description.strip()
    pathways = pull_out_pathways(enzyme_dict)
    reactions = pull_out_enzyme_reactions(enzyme_dict)

    publications = process_references(enzyme_dict)
    node = format_node(node_id,
                       node_name,
                       kg2_util.BIOLINK_CATEGORY_MOLECULAR_ENTITY,
                       update_date,
                       synonym=synonym)
    node['publications'] = publications
    nodes_output.write(node)

    for reaction in reactions:
        edges_output.write(format_kegg_edge(node_id, reaction, update_date))
    for pathway in pathways:
        edges_output.write(format_kegg_edge(node_id, pathway, update_date))


def make_kg2_graph(input_kegg, nodes_output, edges_output, update_date):
    version_number = "109.0"
    version_date = 'Jan-24'
    for kegg_input_dict in input_kegg:
        for single_item in kegg_input_dict:
            kegg_id = single_item
        if kegg_id == 'info':
            # version_number = kegg_input_dict[kegg_id]['version']
            # version_date = kegg_input_dict[kegg_id]['update_date']
            version_number = "109.0"
            version_date = 'Jan-24'
            continue
        kegg_dict = kegg_input_dict[kegg_id]
        if KEGG_COMPOUND_PREFIX.match(kegg_id) is not None:
            process_compound(kegg_dict, kegg_id, nodes_output, edges_output, update_date)

        if KEGG_REACTION_PREFIX.match(kegg_id) is not None:
            process_reaction(kegg_dict, kegg_id, nodes_output, edges_output, update_date)

        if KEGG_PATHWAY_PREFIX.match(kegg_id) is not None:
            process_pathway(kegg_dict, kegg_id, nodes_output, edges_output, update_date)

        if KEGG_DRUG_PREFIX.match(kegg_id) is not None:
            process_drug(kegg_dict, kegg_id, nodes_output, edges_output, update_date)

        if KEGG_GLYCAN_PREFIX.match(kegg_id) is not None:
            process_glycan(kegg_dict, kegg_id, nodes_output, edges_output, update_date)

        if KEGG_ENZYME_PREFIX.match(kegg_id) is not None:
            process_enzyme(kegg_dict, kegg_id, nodes_output, edges_output, update_date)

    kegg_kp_node = kg2_util.make_node(KEGG_PROVIDED_BY,
                                      KEGG_SOURCE_IRI,
                                      'Kyoto Encyclopedia of Genes and Genomes v' + version_number,
                                      kg2_util.SOURCE_NODE_CATEGORY,
                                      update_date,
                                      KEGG_PROVIDED_BY)
    nodes_output.write(kegg_kp_node)


if __name__ == '__main__':
    print("Start time: ", date())
    args = get_args()
    input_file_name = args.inputFile
    output_nodes_file_name = args.outputNodesFile
    output_edges_file_name = args.outputEdgesFile
    test_mode = args.test

    input_jsonlines_info = kg2_util.start_read_jsonlines(input_file_name)
    input_kegg = input_jsonlines_info[0]

    nodes_info, edges_info = kg2_util.create_kg2_jsonlines(test_mode)
    nodes_output = nodes_info[0]
    edges_output = edges_info[0]

    update_date = kg2_util.convert_date(os.path.getmtime(input_file_name))

    make_kg2_graph(input_kegg, nodes_output, edges_output, update_date)

    kg2_util.end_read_jsonlines(input_jsonlines_info)
    kg2_util.close_kg2_jsonlines(nodes_info, edges_info, output_nodes_file_name, output_edges_file_name)

    print("Finish time: ", date())
