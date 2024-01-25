#!/usr/bin/env bash
# build-kg2.sh:  script for downloading and importing repoDB 

set -o nounset -o pipefail -o errexit

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    echo Usage: "$0 <output_csv_dir>"
    exit 2
fi

echo "================= starting doenload-repodb-csv.sh ================="
date

## load the master config file
config_dir=`dirname "$0"`
source ${config_dir}/master-config.shinc

repodb_dir=${1:-"${BUILD_DIR}/repodb/"}
repodb_file=repodb.csv

mkdir -p ${repodb_dir}

${gcs_cp_cmd} gs://${gcs_bucket}/${repodb_file} ${repodb_dir}/${repodb_file}

date
echo "================= script finished ================="
