#!/usr/bin/env bash
# build-kg2-snakemake.sh: Create KG2 JSON file from scratch using snakemake
# Copyright 2019 Stephen A. Ramsey
# Author Erica C. Wood

set -o nounset -o pipefail -o errexit

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    echo Usage: "$0 [test|all|-n|graphic|-R_*|-F] [-n|graphic|-R_*|-F] "
    echo "[-n|graphic|-R_*|-F|ci] [ci|-n] [ci]"
    exit 2
fi

# Usage: build-kg2-snakemake.sh [test|all|-n|graphic|-R_*|-F] [-n|graphic|-R_*|-F] 
#                               [-n|graphic|-R_*|-F|ci] [ci|-n] [ci]

config_dir=`dirname "$0"`
source ${config_dir}/master-config.shinc

build_flag=${1-""}
secondary_build_flag=${2-""}
tertiary_build_flag=${3-""}
quaternary_build_flag=${4-""}
quinary_build_flag=${5-""}

ci_flag=""
if [[ "${tertiary_build_flag}" == "ci" || "${quaternary_build_flag}" == "ci" || "${quinary_build_flag}" == "ci" ]]
then
    ci_flag="ci"
fi

if [[ "${build_flag}" == "test" ]]
then
    # The test argument for bash scripts (ex. extract-semmeddb.sh test)
    test_flag="test"
    # The test argument for file names (ex. kg2-ont-test.json)
    test_suffix="-test"
    # The test argument for python scripts (ex. python3 uniprotkb_dat_to_json.py --test)
    test_arg="--test"
else
    test_flag=""
    test_suffix=""
    test_arg=""
fi

dryrun=""
if [[ "${build_flag}" == "-n" || "${secondary_build_flag}" == "-n" || "${tertiary_build_flag}" == "-n" || "${quaternary_build_flag}" == "-n" ]]
then
    dryrun="-n"
fi

run_flag=""
if [[ "${build_flag:0:2}" == "-R" ]]
then
    run_flag=`echo "${build_flag}" | sed "s/_/ /"`
elif [[ "${secondary_build_flag:0:2}" == "-R" ]]
then
    run_flag=`echo "${secondary_build_flag}" | sed "s/_/ /"`
elif [[ "${tertiary_build_flag:0:2}" == "-R" ]]
then
    run_flag=`echo "${tertiary_build_flag}" | sed "s/_/ /"`
elif [[ "${build_flag}" == "-F" || "${secondary_build_flag}" == "-F" || "${tertiary_build_flag}" == "-F" ]]
then
    run_flag="-F"
fi

build_kg2_log_file=${BUILD_DIR}/build-kg2-snakemake${dryrun}${test_suffix}.log
touch ${build_kg2_log_file}
if [[ "${ci_flag}" == "ci" ]]
then
    trap "cat ${build_kg2_log_file}" EXIT
fi

{
echo "================= starting build-kg2-snakemake.sh =================="
date

snakemake_config_file=${CODE_DIR}/snakemake-config.yaml
snakefile=${CODE_DIR}/Snakefile

${python_command} ${CODE_DIR}/generate_snakemake_config_file.py ${test_arg} ${config_dir}/master-config.shinc \
                            ${CODE_DIR}/snakemake-config-var.yaml ${snakemake_config_file}

# Run snakemake from the virtualenv but run the snakefile in kg2-code
# -F: Run all of the rules in the snakefile
# -R Finish: Run all of the rules in the snakefile that generate an unmet dependency
# -R Merge: Generate any missing KG2 JSON files (ex. kg2-ont.json), merge them, then finish the workflow
#           (more likely to be the flag you need than -R Finish depending on the fail point)
# -j: Run the rules in parallel
# -config: Give the test arguments to the snakefile (NO LONGER USED)
# --dag | dot -Tpng > ~/kg2-build/snakemake_diagram.png: Creates Snakemake workflow diagram (when combined with -F and -j)
# -n: dry run REMOVE THIS BEFORE BUILDING

export PATH=$PATH:${BUILD_DIR}

graphic=""
if [[ "${build_flag}" == "graphic" || "${secondary_build_flag}" == "graphic" || "${tertiary_build_flag}" == "graphic" ]]
then
    graphic="--dag | dot -Tpng > ~/kg2-build/snakemake_diagram.png"
fi

echo configfile: \"${snakemake_config_file}\" > ${snakefile}

cat ${CODE_DIR}/Snakefile-finish >> ${snakefile}

echo 'include: "Snakefile-pre-etl"' >> ${snakefile}

echo 'include: "Snakefile-conversion"' >> ${snakefile}

echo 'include: "Snakefile-post-etl"' >> ${snakefile}

if [[ "${build_flag}" == "all" ]]
then
    echo 'include: "Snakefile-extraction"' >> ${snakefile}
fi

# cd ~ && ${VENV_DIR}/bin/snakemake --snakefile ${snakefile} ${run_flag} -R Finish -j 32 ${dryrun} ${graphic}
cd ~ && ${VENV_DIR}/bin/snakemake --snakefile ${snakefile} -R Finish -j

date
echo "================ script finished ============================"
} > ${build_kg2_log_file} 2>&1

if [[ "${ci_flag}" != "ci" && "${dryrun}" != "-n" ]]
then
    ${gcs_cp_cmd} ${build_kg2_log_file} gs://${gcs_bucket_public}/
    ${gcs_cp_cmd} ${build_kg2_log_file} gs://${gcs_bucket_versioned}/
fi
