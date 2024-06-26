#!/usr/bin/env bash
# setup-kg2.sh:  setup the environment for building the KG2 knowledge graph for the RTX biomedical reasoning system
# Copyright 2019 Stephen A. Ramsey <stephen.ramsey@oregonstate.edu>

# Options:
# ./setup-kg2-build.sh test       Generates a logfile `setup-kg2-build-test.log` instead of `setup-kg2-build.log`
# ./setup-kg2-build.sh ci   Accommodate Travis CI's special runtime environment

set -o nounset -o pipefail -o errexit

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    echo Usage: "$0 [ci|test]" 
    exit 2
fi

# Usage: setup-kg2-build.sh [ci|test]

build_flag=${1:-""}

## setup the shell variables for various directories
config_dir=`dirname "$0"`
if [[ "${build_flag}" == "ci" ]]
then
    sed -i "\@CODE_DIR=~/kg2-code@cCODE_DIR=/home/runner/work/RTX-KG2/RTX-KG2/RTX-KG2" ${config_dir}/master-config.shinc
fi
source ${config_dir}/master-config.shinc

if [[ "${build_flag}" != "test" ]]
then
    test_str=""
else
    test_str="-test"
fi

mysql_user=ubuntu
mysql_password=1337
if [[ "${build_flag}" != "ci" ]]
then
    psql_user=ubuntu
fi

mkdir -p ${BUILD_DIR}
setup_log_file=${BUILD_DIR}/setup-kg2-build${test_str}.log
touch ${setup_log_file}

{

echo "================= starting setup-kg2.sh ================="
date

echo `hostname`

## sym-link into RTX-KG2/
if [ ! -L ${CODE_DIR} ]; then
    if [[ "${build_flag}" != "ci" ]]
    then
        ln -sf ~/RTX-KG2 ${CODE_DIR}
    fi
fi

## install the Linux distro packages that we need (python3-minimal is for docker installations)
sudo apt-get update

## handle weird tzdata install (this makes UTC the timezone)
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y tzdata

# install various other packages used by the build system
#  - curl is generally used for HTTP downloads
#  - wget is used by the neo4j installation script (some special "--no-check-certificate" mode)
sudo apt-get install -y \
     default-jre \
     zip \
     curl \
     wget \
     flex \
     bison \
     libxml2-dev \
     gtk-doc-tools \
     libtool \
     automake \
     git \
     libssl-dev \
     make

# Install Google Cloud SDK
echo "Installing Google Cloud SDK..."
# export CLOUD_SDK_REPO="cloud-sdk-$(lsb_release -c -s)"

# echo "deb http://packages.cloud.google.com/apt $CLOUD_SDK_REPO main" | sudo tee -a /etc/apt/sources.list.d/google-cloud-sdk.list
# sudo sh -c 'echo "deb http://packages.cloud.google.com/apt cloud-sdk-bionic main" > /etc/apt/sources.list.d/google-cloud-sdk.list'
# curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | sudo apt-key add -
sudo apt-get update && sudo apt-get install google-cloud-sdk 

# Authenticate and set project for GCP
# gcloud auth login
gcloud config set project ${gcp_project_id}

sudo debconf-set-selections <<< "mysql-server mysql-server/root_password password ${mysql_password}"
sudo debconf-set-selections <<< "mysql-server mysql-server/root_password_again password ${mysql_password}"

sudo apt-get install -y mysql-server \
     mysql-client \
     libmysqlclient-dev \
     python3-mysqldb

sudo service mysql start
if [[ "${build_flag}" != "ci" ]]
then
    ## this is for convenience when I am remote working
    sudo apt-get install -y emacs
fi

# we want python3.7 (also need python3.7-dev or else pip cannot install the python package "mysqlclient")
source ${CODE_DIR}/setup-python37-with-pip3-in-ubuntu.shinc
${VENV_DIR}/bin/pip3 install -r ${CODE_DIR}/requirements-kg2-build.txt

## install ROBOT (software: ROBOT is an OBO Tool) by downloading the jar file
## distribution and cURLing the startup script (note github uses URL redirection
## so we need the "-L" command-line option, and cURL doesn't like JAR files by
## default so we need the "application/zip")
${curl_get} -H "Accept: application/zip" https://github.com/RTXteam/robot/releases/download/v1.3.0/robot.jar > ${BUILD_DIR}/robot.jar 
curl -s https://raw.githubusercontent.com/RTXteam/robot/v1.3.0/bin/robot > ${BUILD_DIR}/robot
chmod +x ${BUILD_DIR}/robot

## setup owltools
${curl_get} ${BUILD_DIR} https://github.com/RTXteam/owltools/releases/download/v0.3.0/owltools > ${BUILD_DIR}/owltools
chmod +x ${BUILD_DIR}/owltools

} >${setup_log_file} 2>&1

if [[ "${build_flag}" != "ci" ]]
then
    ## setup AWS CLI
    if ! ${gcs_cp_cmd} gs://${gcs_bucket}/test-file-do-not-delete/ /tmp/; then
        echo "Error: Unable to access GCS bucket. Please check your GCP configuration."
    else
        rm -f /tmp/test-file-do-not-delete
    fi
fi

{
RAPTOR_NAME=raptor2-2.0.15
# setup raptor (used by the "checkOutputSyntax.sh" script in the umls2rdf package)
${curl_get} -o ${BUILD_DIR}/${RAPTOR_NAME}.tar.gz http://download.librdf.org/source/${RAPTOR_NAME}.tar.gz
rm -r -f ${BUILD_DIR}/${RAPTOR_NAME}
tar xzf ${BUILD_DIR}/${RAPTOR_NAME}.tar.gz -C ${BUILD_DIR} 
cd ${BUILD_DIR}/${RAPTOR_NAME}
./autogen.sh --prefix=/usr/local
make
make check
sudo make install
sudo ldconfig

if [[ "${build_flag}" != "ci" ]]
then
    # setup MySQL
    MYSQL_PWD=${mysql_password} mysql -u root -e "CREATE USER IF NOT EXISTS '${mysql_user}'@'localhost' IDENTIFIED BY '${mysql_password}'"
    MYSQL_PWD=${mysql_password} mysql -u root -e "GRANT ALL PRIVILEGES ON *.* to '${mysql_user}'@'localhost'"

    cat >${mysql_conf} <<EOF
[client]
user = ${mysql_user}
password = ${mysql_password}
host = localhost
[mysqld]
skip-log-bin
EOF

    ## set mysql server variable to allow loading data from a local file
    mysql --defaults-extra-file=${mysql_conf} \
          -e "set global local_infile=1"

    ## setup PostGreSQL
    # sudo sh -c 'echo "deb https://apt-archive.postgresql.org/pub/repos/apt bionic-pgdg main" > /etc/apt/sources.list.d/pgdg.list'
    # wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | sudo apt-key add -
    # sudo apt-get update
    # sudo apt-get -y install postgresql
    # Set the PostgreSQL version you want to install
    postgresql_version=15

    # Add the correct PostgreSQL repository for Ubuntu 22.04 (Jammy)
    sudo sh -c 'echo "deb [signed-by=/usr/share/keyrings/postgresql-archive-keyring.gpg] https://apt.postgresql.org/pub/repos/apt jammy-pgdg main" > /etc/apt/sources.list.d/pgdg.list'
    wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | gpg --dearmor | sudo tee /usr/share/keyrings/postgresql-archive-keyring.gpg > /dev/null
    sudo apt-get update
    sudo apt-get -y install postgresql-$postgresql_version
    
    # Addresses permission issues
    # https://stackoverflow.com/questions/38470952/postgres-can-not-change-directory-in-ubuntu-14-04
    cd ~postgres/

    sudo -u postgres psql -c "DO \$do\$ BEGIN IF NOT EXISTS ( SELECT FROM pg_catalog.pg_roles WHERE rolname = '${psql_user}' ) THEN CREATE ROLE ${psql_user} LOGIN PASSWORD null; END IF; END \$do\$;"
    sudo -u postgres psql -c "ALTER USER ${psql_user} WITH password null"
else
    export PATH=$PATH:${BUILD_DIR}
fi

date

echo "================= script finished ================="
} >> ${setup_log_file} 2>&1

if [[ "${build_flag}" != "ci" ]]
then
    ${gcs_cp_cmd} ${setup_log_file} gs://${gcs_bucket_versioned}/
fi
