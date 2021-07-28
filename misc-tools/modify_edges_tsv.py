import csv
import argparse
import sys
import json
import yaml
import io

EDGE_ID_HEADER_KEY = 'id'
SUBJECT_ID_HEADER_KEY = ':START_ID'
OBJECT_ID_HEADER_KEY = ':END_ID'
PREDICATE_HEADER_KEY_1 = 'predicate'
PREDICATE_HEADER_KEY_2 = 'predicate:TYPE'
PREDICATE_LABEL_HEADER_KEY = 'predicate_label'
RELATION_HEADER_KEY = 'relation'
RELATION_LABEL_HEADER_KEY = 'relation_label'
INFORES_HEADER_KEY = 'knowledge_source:string[]'

REPLACEMENT_KEY_FORMAT = '-\n' \
                         '  detection:\n' \
                         '    subject_start: null\n' \
                         '    object_start: null\n' \
                         '    relation: null\n' \
                         '    predicate: null\n' \
                         '    infores_curie: null\n' \
                         '  new_values:\n' \
                         '    predicate: null\n' \
                         '    relation: null\n' \
                         '    relation_label: null\n' \
                         '    infores_curie: null'
REPLACEMENT_KEY_EXAMPLE = '-\n' \
                          '  detection:\n' \
                          '    subject_start: "DrugCentral:"\n' \
                          '    object_start: "ATC:"\n' \
                          '    relation: null\n' \
                          '    predicate: biolink:same_as\n' \
                          '    infores_curie: infores:drugcentral\n' \
                          '  new_values:\n' \
                          '    predicate: biolink:close_match\n' \
                          '    relation: DrugCentral:struct2atc\n' \
                          '    relation_label: struct2atc\n' \
                          '    infores_curie: null'


csv.field_size_limit(sys.maxsize)

def get_args():
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument('--inputFile', type=str, help="Input edges TSV file")
    arg_parser.add_argument('--inputHeaderFile', type=str, help="Input edges header TSV file")
    arg_parser.add_argument('--outputFile', type=str, help="Output edges TSV file")
    
    arg_parser.add_argument('--replacementKey', type=str, help="YAML file detailing which edges need adjustments and how they should be adjusted.")
    arg_parser.add_argument('--YAMLFormat', dest='YAMLFormat', action="store_true", default=False)
    return arg_parser.parse_args()


def check_edge(replacement_key, subject_id, object_id, infores, relation, predicate):
    detection = replacement_key['detection']
    new_values = replacement_key['new_values']
    subject_start = detection.get('subject_start', None)
    object_start = detection.get('object_start', None)
    old_infores = detection.get('infores_curie', None)
    new_infores = new_values.get('infores_curie', None)
    old_relation = detection.get('relation', None)
    new_relation = new_values.get('relation', None)
    new_relation_label = new_values.get('relation_label', None)
    old_predicate = detection.get('predicate', None)
    new_predicate = new_values.get('predicate', None)

    if subject_start is not None and not subject_id.startswith(subject_start):
        return False
    if object_start is not None and not object_id.startswith(subject_start):
        return False
    if old_infores is not None and old_infores != infores and infores not in old_infores:
        return False
    if old_relation is not None and old_relation != relation:
        return False
    if old_predicate is not None and old_predicate != predicate:
        return False
    return_dict = {}
    if new_predicate is not None:
        return_dict['predicate'] = new_predicate
    if new_relation is not None:
        return_dict['relation'] = new_relation
        if new_relation_label is not None:
            return_dict['relation_label'] = new_relation_label
        else:
            return_dict['relation_label'] = new_relation.split(':')[1]
    if new_infores is not None:
        if old_infores is not None:
            return_dict['infores'] = infores.replace(old_infores, new_infores)
        else:
            return_dict['infores'] = new_infores
    return return_dict


def edit_relation(edge, old_edge_id, old_relation, new_value_dict, header):
    new_relation = new_value_dict['relation']
    edge[header[EDGE_ID_HEADER_KEY]] = old_edge_id.replace(old_relation, new_relation)
    edge[header[RELATION_HEADER_KEY]] = new_relation
    edge[header[RELATION_LABEL_HEADER_KEY]] = new_value_dict['relation_label']
    return edge


def edit_predicate(edge, new_value_dict, header):
    new_predicate = new_value_dict['predicate']
    edge[header[PREDICATE_HEADER_KEY_1]] = new_predicate
    edge[header[PREDICATE_HEADER_KEY_2]] = new_predicate
    return edge


def edit_infores(edge, new_value_dict, header):
    edge[header[INFORES_HEADER_KEY]] = new_value_dict['infores']
    return edge

def process_header_file(header_file):
    header_dict = {}
    with open(header_file, 'r') as header:
        line_count = 0
        for line in header:
            line_count += 1
            if line_count > 1:
                break
            line = line.split('\t')
            element_count = 0
            for element in line:
                header_dict[element.strip()] = element_count
                element_count += 1
    return header_dict


if __name__ == '__main__':
    args = get_args()
    if args.YAMLFormat:
        print('Format:')
        print(REPLACEMENT_KEY_FORMAT)
        print('\nExample:')
        print(REPLACEMENT_KEY_EXAMPLE)
        detection_description = 'Detection elements are used to match the existing edges with a set of criteria that determine if they should be changed. ' \
                                'In this example, edges are checked to see if their subject starts with "DrugCentral:", their object starts with "ATC:", ' \
                                'their predicate is "biolink:same_as", and their infores_curie is "infores:drugcentral". All detection elements must be ' \
                                'true for an edge to be changed. If a detection element is not needed, set it to `null`.'
        new_values_description = 'New Values elements are used to replace existing edge values. For example, in this example, matching edges would have ' \
                                 'their predicate changed to "biolink:close_match", their relation changed to "DrugCentral:struct2atc" (and the relation ' \
                                 'embedded in their edge id), and their relation label changed to "struct2atc". Any properties you do not want changed ' \
                                 'should be set to `null`.'
        print('\nInformation:')
        print(detection_description)
        print(new_values_description)
        exit(0)
    output_file = open(args.outputFile, 'w+')
    new_edges = csv.writer(output_file, delimiter='\t')
    header = process_header_file(args.inputHeaderFile)
    replacement_keys = dict()
    with open(args.replacementKey) as replacement_key_file:
        replacement_keys = yaml.safe_load(io.StringIO(replacement_key_file.read()))
    with open(args.inputFile, 'r') as edgesfile:
        edges = csv.reader(edgesfile, delimiter='\t')
        edge_count = 0
        for edge in edges:
            if len(edge) < 1:
                continue
            edge_id = edge[header[EDGE_ID_HEADER_KEY]]
            subject_id = edge[header[SUBJECT_ID_HEADER_KEY]]
            object_id = edge[header[OBJECT_ID_HEADER_KEY]]
            relation = edge[header[RELATION_HEADER_KEY]]
            infores = edge[header[INFORES_HEADER_KEY]]
            predicate = edge[header[PREDICATE_HEADER_KEY_1]]
            checked_edge = False
            for replacement_key in replacement_keys:
                checked_edge_local = check_edge(replacement_key, subject_id, object_id, infores, relation, predicate)
                if checked_edge_local != False:
                    checked_edge = checked_edge_local
            if checked_edge != False:
                if "relation" in checked_edge:
                    edge = edit_relation(edge, edge_id, relation, checked_edge, header)
                if "predicate" in checked_edge:
                    edge = edit_predicate(edge, checked_edge, header)
                if "infores" in checked_edge:
                    edge = edit_infores(edge, checked_edge, header)
            new_edges.writerow(edge)
            edge_count += 1
            if edge_count % 1000000 == 0:
                print('Finished', edge_count, 'edges')
    print('Finished adjusting file')
    output_file.close()
