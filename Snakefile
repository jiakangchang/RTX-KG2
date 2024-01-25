configfile: "/home/jchang/kg2-code/snakemake-config.yaml"
rule Finish:
    input:
        merged_output_nodes_file = config['MERGED_OUTPUT_NODES_FILE'],
        final_output_edges_file = config['MERGED_OUTPUT_EDGES_FILE'],
        output_file_orphan_edges = config['OUTPUT_FILE_ORPHAN_EDGES'],
        report_file = config['REPORT_FILE'],
        simplified_output_nodes_file = config['SIMPLIFIED_OUTPUT_NODES_FILE'],
        simplified_output_edges_file = config['SIMPLIFIED_OUTPUT_EDGES_FILE'],
        simplified_report_file = config['SIMPLIFIED_REPORT_FILE'],
        slim_output_nodes_file = config['SLIM_OUTPUT_NODES_FILE'],
        slim_output_edges_file = config['SLIM_OUTPUT_EDGES_FILE'],
        placeholder = config['TSV_PLACEHOLDER']
    shell:
        "bash -x " + config['CODE_DIR'] + "/finish-snakemake.sh {input.merged_output_nodes_file} {input.final_output_edges_file} {input.output_file_orphan_edges} {input.report_file} {input.simplified_output_nodes_file} {input.simplified_output_edges_file} {input.simplified_report_file} {input.slim_output_nodes_file} {input.slim_output_edges_file} " + config['KG2_TSV_DIR'] + " \"" + config['GCS_CP_CMD'] + "\" " + config['KG2_TSV_TARBALL'] + " " + config['GCS_BUCKET'] + " " + config['GCS_BUCKET_PUBLIC'] + " " + config['CODE_DIR'] + " " + config['GCS_BUCKET_VERSIONED'] + " " + config['BUILD_DIR'] + " " + config['SIMPLIFIED_REPORT_FILE_BASE'] + " " + config['VENV_DIR']


include: "Snakefile-pre-etl"
include: "Snakefile-conversion"
include: "Snakefile-post-etl"
include: "Snakefile-extraction"
