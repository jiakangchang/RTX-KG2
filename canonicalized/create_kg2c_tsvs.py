#!/bin/env python3
"""
This script creates a canonicalized version of KG2 stored in TSV files, ready for import into neo4j. The TSVs are
created in the current working directory.
Usage: python3 create_kg2c_tsvs.py [--test]
"""
import argparse
import csv
import os
import sys
import time
import traceback

from datetime import datetime
from typing import List, Dict, Tuple, Union, Optional
from neo4j import GraphDatabase

sys.path.append(os.path.dirname(os.path.abspath(__file__))+"/../../")  # code directory
from RTXConfiguration import RTXConfiguration
sys.path.append(os.path.dirname(os.path.abspath(__file__))+"/../../ARAX/NodeSynonymizer/")
from node_synonymizer import NodeSynonymizer

ARRAY_NODE_PROPERTIES = ["all_categories", "publications", "equivalent_curies", "all_names"]
ARRAY_EDGE_PROPERTIES = ["provided_by", "publications"]


def _run_kg2_cypher_query(cypher_query: str) -> List[Dict[str, any]]:
    # This function sends a cypher query to the KG2 neo4j specified in config.json and returns the results
    rtxc = RTXConfiguration()
    rtxc.live = "KG2"
    try:
        driver = GraphDatabase.driver(rtxc.neo4j_bolt, auth=(rtxc.neo4j_username, rtxc.neo4j_password))
        with driver.session() as session:
            print(f"  Sending cypher query to KG2 neo4j..")
            query_results = session.run(cypher_query).data()
            print(f"  Got {len(query_results)} results back from neo4j")
        driver.close()
    except Exception:
        tb = traceback.format_exc()
        error_type, error, _ = sys.exc_info()
        print(f"ERROR: Encountered a problem interacting with {rtxc.neo4j_bolt}. {tb}")
        return []
    else:
        return query_results


def _convert_list_to_neo4j_format(input_list: List[str]) -> str:
    filtered_list = [item for item in input_list if item]  # Get rid of any None items
    non_str_items = [item for item in filtered_list if not isinstance(item, str)]
    if non_str_items:
        print(f"  WARNING: List contains non-str items (this is unexpected; I'll exclude them): {non_str_items}")
    str_items = [item for item in filtered_list if isinstance(item, str)]
    return "ǂ".join(str_items)  # Need to use a delimiter that does not appear in any list items


def _merge_two_lists(list_a: List[any], list_b: List[any]) -> List[any]:
    return list(set(list_a + list_b))


def _get_edge_key(subject: str, object: str, predicate: str) -> str:
    return f"{subject}--{predicate}--{object}"


def _canonicalize_nodes(neo4j_nodes: List[Dict[str, any]]) -> Tuple[Dict[str, Dict[str, any]], Dict[str, str]]:
    synonymizer = NodeSynonymizer()
    node_ids = [node.get('id') for node in neo4j_nodes if node.get('id')]
    print(f"  Sending NodeSynonymizer.get_canonical_curies() {len(node_ids)} curies..")
    canonicalized_info = synonymizer.get_canonical_curies(curies=node_ids, return_all_types=True)
    all_canonical_curies = {canonical_info['preferred_curie'] for canonical_info in canonicalized_info.values() if canonical_info}
    print(f"  Sending NodeSynonymizer.get_equivalent_nodes() {len(all_canonical_curies)} curies..")
    equivalent_curies_info = synonymizer.get_equivalent_nodes(all_canonical_curies)
    recognized_curies = {curie for curie in equivalent_curies_info if equivalent_curies_info.get(curie)}
    equivalent_curies_dict = {curie: list(equivalent_curies_info.get(curie)) for curie in recognized_curies}
    print(f"  Creating canonicalized nodes..")
    curie_map = dict()
    canonicalized_nodes = dict()
    for neo4j_node in neo4j_nodes:
        canonical_info = canonicalized_info.get(neo4j_node['id'])
        canonicalized_curie = canonical_info.get('preferred_curie', neo4j_node['id']) if canonical_info else neo4j_node['id']
        publications = neo4j_node['publications'] if neo4j_node.get('publications') else []
        description_in_list = [neo4j_node['description']] if neo4j_node.get('description') else []
        if canonicalized_curie in canonicalized_nodes:
            # Merge this node into its corresponding canonical node
            existing_canonical_node = canonicalized_nodes[canonicalized_curie]
            existing_canonical_node['publications'] = _merge_two_lists(existing_canonical_node['publications'], publications)
            existing_canonical_node['all_names'] = _merge_two_lists(existing_canonical_node['all_names'], [neo4j_node['name']])
            existing_canonical_node['description'] = _merge_two_lists(existing_canonical_node['description'], description_in_list)
            # Make sure any nodes subject to #1074-like problems still appear in equivalent curies
            existing_canonical_node['equivalent_curies'] = _merge_two_lists(existing_canonical_node['equivalent_curies'], [neo4j_node['id']])
            # Add the IRI for the 'preferred' curie, if we've found that node
            if neo4j_node['id'] == canonicalized_curie:
                existing_canonical_node['iri'] = neo4j_node.get('iri')
        else:
            # Initiate the canonical node for this synonym group
            name = canonical_info['preferred_name'] if canonical_info else neo4j_node['name']
            category = canonical_info['preferred_type'] if canonical_info else neo4j_node['category']
            if not category.startswith("biolink:"):
                print(f"  WARNING: Preferred category for {canonicalized_curie} doesn't start with 'biolink:': {category}")
            all_categories = list(canonical_info['all_types']) if canonical_info else [neo4j_node['category']]
            if not all(category.startswith("biolink:") for category in all_categories):
                print(f" WARNING: Categories for {canonicalized_curie} contain non 'biolink:' items: {all_categories}")
            iri = neo4j_node['iri'] if neo4j_node['id'] == canonicalized_curie else None
            all_names = [neo4j_node['name']]
            canonicalized_node = _create_node(preferred_curie=canonicalized_curie,
                                              name=name,
                                              category=category,
                                              all_categories=all_categories,
                                              publications=publications,
                                              equivalent_curies=equivalent_curies_dict.get(canonicalized_curie, [canonicalized_curie]),
                                              iri=iri,
                                              description=description_in_list,
                                              all_names=all_names)

            canonicalized_nodes[canonicalized_node['id']] = canonicalized_node
        curie_map[neo4j_node['id']] = canonicalized_curie  # Record this mapping for easy lookup later
    return canonicalized_nodes, curie_map


def _canonicalize_edges(neo4j_edges: List[Dict[str, any]], curie_map: Dict[str, str], is_test: bool) -> Dict[str, Dict[str, any]]:
    allowed_self_edges = ['positively_regulates', 'interacts_with', 'increase']
    canonicalized_edges = dict()
    for neo4j_edge in neo4j_edges:
        original_subject = neo4j_edge['subject']
        original_object = neo4j_edge['object']
        if not is_test:  # Make sure we have the mappings we expect
            assert original_subject in curie_map
            assert original_object in curie_map
        canonicalized_subject = curie_map.get(original_subject, original_subject)
        canonicalized_object = curie_map.get(original_object, original_object)
        edge_publications = neo4j_edge['publications'] if neo4j_edge.get('publications') else []
        edge_provided_by = neo4j_edge['provided_by'] if neo4j_edge.get('provided_by') else []
        if canonicalized_subject != canonicalized_object or neo4j_edge['predicate'] in allowed_self_edges:
            canonicalized_edge_key = _get_edge_key(canonicalized_subject, canonicalized_object, neo4j_edge['predicate'])
            if canonicalized_edge_key in canonicalized_edges:
                canonicalized_edge = canonicalized_edges[canonicalized_edge_key]
                canonicalized_edge['provided_by'] = _merge_two_lists(canonicalized_edge['provided_by'], edge_provided_by)
                canonicalized_edge['publications'] = _merge_two_lists(canonicalized_edge['publications'], edge_publications)
            else:
                new_canonicalized_edge = _create_edge(subject=canonicalized_subject,
                                                      object=canonicalized_object,
                                                      predicate=neo4j_edge['predicate'],
                                                      provided_by=edge_provided_by,
                                                      publications=edge_publications)
                canonicalized_edges[canonicalized_edge_key] = new_canonicalized_edge
    return canonicalized_edges


def _modify_column_headers_for_neo4j(plain_column_headers: List[str]) -> List[str]:
    modified_headers = []
    all_array_column_names = ARRAY_NODE_PROPERTIES + ARRAY_EDGE_PROPERTIES
    for header in plain_column_headers:
        if header in all_array_column_names:
            header = f"{header}:string[]"
        elif header == 'id':
            header = f"{header}:ID"
        elif header == 'category_for_conversion':
            header = ":LABEL"
        elif header == 'subject_for_conversion':
            header = ":START_ID"
        elif header == 'object_for_conversion':
            header = ":END_ID"
        elif header == 'predicate_for_conversion':
            header = ":TYPE"
        modified_headers.append(header)
    return modified_headers


def _create_node(preferred_curie: str, name: Optional[str], category: str, all_categories: List[str], equivalent_curies: List[str],
                 publications: List[str], all_names: List[str], iri: Optional[str], description: Union[str, List[str]]) -> Dict[str, any]:
    assert isinstance(preferred_curie, str)
    assert isinstance(name, str) or name is None
    assert isinstance(category, str)
    assert isinstance(all_names, list)
    assert isinstance(all_categories, list)
    assert isinstance(equivalent_curies, list)
    assert isinstance(publications, list)
    return {
        "id": preferred_curie,
        "name": name,
        "category": category,
        "all_names": all_names,
        "all_categories": all_categories,
        "iri": iri,
        "description": description,
        "equivalent_curies": equivalent_curies,
        "publications": publications
    }


def _create_edge(subject: str, object: str, predicate: str, provided_by: List[str], publications: List[str]) -> Dict[str, any]:
    assert isinstance(subject, str)
    assert isinstance(object, str)
    assert isinstance(predicate, str)
    assert isinstance(provided_by, list)
    assert isinstance(publications, list)
    return {
        "subject": subject,
        "object": object,
        "predicate": predicate,
        "provided_by": provided_by,
        "publications": publications
    }


def _write_list_to_neo4j_ready_tsv(input_list: List[Dict[str, any]], file_name_root: str, is_test: bool):
    print(f"  Creating {file_name_root} header file..")
    column_headers = list(input_list[0].keys())
    modified_headers = _modify_column_headers_for_neo4j(column_headers)
    with open(f"{'test_' if is_test else ''}{file_name_root}_header.tsv", "w+") as header_file:
        dict_writer = csv.DictWriter(header_file, modified_headers, delimiter='\t')
        dict_writer.writeheader()
    print(f"  Creating {file_name_root} file..")
    with open(f"{'test_' if is_test else ''}{file_name_root}.tsv", "w+") as data_file:
        dict_writer = csv.DictWriter(data_file, column_headers, delimiter='\t')
        dict_writer.writerows(input_list)


def create_canonicalized_tsvs(is_test=False):
    """
    This function extracts all nodes/edges from the regular KG2 Neo4j endpoint (specified in your config.json),
    canonicalizes the nodes, merges edges (based on subject, object, predicate), and saves the resulting canonicalized
    graph in two tsv files (nodes_c.tsv and edges_c.tsv) that are ready for import into Neo4j.
    """
    print(f" Extracting nodes from KG2..")
    nodes_query = f"match (n) return n.id as id, n.name as name, n.category as category, " \
                  f"n.publications as publications, n.iri as iri, n.description as description{' limit 20000' if is_test else ''}"
    neo4j_nodes = _run_kg2_cypher_query(nodes_query)
    if neo4j_nodes:
        print(f" Canonicalizing nodes..")
        canonicalized_nodes_dict, curie_map = _canonicalize_nodes(neo4j_nodes)
        print(f"  Number of KG2 nodes was reduced to {len(canonicalized_nodes_dict)} ({round((len(canonicalized_nodes_dict) / len(neo4j_nodes)) * 100)}%)")
    else:
        print(f"ERROR: Couldn't get node data from KG2 neo4j.")
        return
    print(f" Extracting edges from KG2..")
    edges_query = f"match (n)-[e]->(m) return n.id as subject, m.id as object, e.predicate as " \
                  f"predicate, e.provided_by as provided_by, e.publications as publications" \
                  f"{' limit 20000' if is_test else ''}"
    neo4j_edges = _run_kg2_cypher_query(edges_query)
    if neo4j_edges:
        print(f" Canonicalizing edges..")
        canonicalized_edges_dict = _canonicalize_edges(neo4j_edges, curie_map, is_test)
        print(f"  Number of KG2 edges was reduced to {len(canonicalized_edges_dict)} ({round((len(canonicalized_edges_dict) / len(neo4j_edges)) * 100)}%)")
    else:
        print(f"ERROR: Couldn't get edge data from KG2 neo4j.")
        return

    # Create a node containing information about this KG2C build
    kg2_build_node = canonicalized_nodes_dict.get('RTX:KG2')
    if kg2_build_node:
        kg2c_build_node = _create_node(preferred_curie=f"{kg2_build_node['id']}c",
                                       name=f"{kg2_build_node['name']}c",
                                       all_categories=kg2_build_node['all_categories'],
                                       category=kg2_build_node['category'],
                                       equivalent_curies=[],
                                       publications=[],
                                       iri=f"{kg2_build_node['iri']}c",
                                       all_names=[f"{kg2_build_node['name']}c"],
                                       description=[f"This KG2c build was created from {kg2_build_node['name']} on "
                                                    f"{datetime.now().strftime('%Y-%m-%d %H:%M')}."])
        canonicalized_nodes_dict[kg2c_build_node['id']] = kg2c_build_node
    else:
        print(f"  WARNING: No build node detected in the regular KG2, so I'm not creating a KG2c build node.")

    # Convert array fields into the format neo4j wants and do some final processing
    for canonicalized_node in canonicalized_nodes_dict.values():
        for list_node_property in ARRAY_NODE_PROPERTIES:
            canonicalized_node[list_node_property] = _convert_list_to_neo4j_format(canonicalized_node[list_node_property])
        # Grab the five longest descriptions and join them into one string
        sorted_description_list = sorted(canonicalized_node['description'], key=len, reverse=True)
        # Get rid of any redundant descriptions (e.g., duplicate 'UMLS Semantic Type: UMLS_STY:T060')
        filtered_description_list = [description for description in sorted_description_list if not any(description in other_description
                                     for other_description in sorted_description_list if description != other_description)]
        canonicalized_node['description'] = " --- ".join(filtered_description_list[:5])
        canonicalized_node['category_for_conversion'] = canonicalized_node['category']
    for canonicalized_edge in canonicalized_edges_dict.values():
        if not is_test:  # Make sure we don't have any orphan edges
            assert canonicalized_edge['subject'] in canonicalized_nodes_dict
            assert canonicalized_edge['object'] in canonicalized_nodes_dict
        for list_edge_property in ARRAY_EDGE_PROPERTIES:
            canonicalized_edge[list_edge_property] = _convert_list_to_neo4j_format(canonicalized_edge[list_edge_property])
        canonicalized_edge['predicate_for_conversion'] = canonicalized_edge['predicate']
        canonicalized_edge['subject_for_conversion'] = canonicalized_edge['subject']
        canonicalized_edge['object_for_conversion'] = canonicalized_edge['object']

    # Finally dump all our nodes/edges into TSVs (formatted for neo4j)
    print(f" Saving data to TSVs..")
    _write_list_to_neo4j_ready_tsv(list(canonicalized_nodes_dict.values()), "nodes_c", is_test)
    _write_list_to_neo4j_ready_tsv(list(canonicalized_edges_dict.values()), "edges_c", is_test)


def main():
    arg_parser = argparse.ArgumentParser(description="Creates a canonicalized KG2, stored in TSV files")
    arg_parser.add_argument('--test', dest='test', action='store_true', default=False)
    args = arg_parser.parse_args()

    print(f"Starting to create canonicalized KG..")
    start = time.time()
    create_canonicalized_tsvs(args.test)
    print(f"Done! Took {round((time.time() - start) / 60, 2)} minutes.")


if __name__ == "__main__":
    main()
