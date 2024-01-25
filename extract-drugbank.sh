#!/usr/bin/env bash
# extract-drugbank.sh: Download the gzipped DrugBank XML file from the S3 Bucket
# Copyright 2019 Stephen A. Ramsey
# Author Erica Wood

set -o nounset -o pipefail -o errexit

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    echo Usage: "$0 <output-xml-file>"
    exit 2
fi

# Usage: extract-drugbank.sh <output_xml_file>

echo "================= starting extract-drugbank.sh =================="
date

config_dir=`dirname "$0"`
source ${config_dir}/master-config.shinc

drugbank_version=5.1.10
output_file=${1:-"${BUILD_DIR}/drugbank.xml"}

xml_filename=drugbank_${drugbank_version}.xml.gz

${gcs_cp_cmd} gs://${gcs_bucket}/${xml_filename} ${BUILD_DIR}
gzip -cdf ${BUILD_DIR}/${xml_filename} > ${output_file}

date
echo "================= finished extract-drugbank.sh =================="
