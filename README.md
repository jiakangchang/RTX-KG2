
# How to build RTX kg2

## General notes:

The KG2 build system is designed only to run in an Ubuntu 18.04 environment
(i.e., either (i) an Ubuntu 18.04 host OS or (ii) Ubuntu 18.04 running in a
Docker container with a host OS that has `bash` and `sudo`). Currently, KG2 is
built using a set of `bash` scripts that are designed to run in Amazon's Elastic
Compute Cloud (EC2), and thus, configurability and/or coexisting with other
installed software pipelines was not a design consideration for the build
system. The KG2 build system's `bash` scripts create three subdirectories
`~/kg2-build`, `~/kg2-code`, and `~/kg2-venv` under the `${HOME}` directory of
whatever Linux user account you use to run the KG2 build software (if you run on
an EC2 Ubuntu instance, this directory would by default be `/home/ubuntu`). The
various directories used by the KG2 build system are configured in the `bash`
include file `master-config.shinc`.

Note about atomicity of file copying: The build software is designed to run with
the `kg2-build` directory being in the same file system as the Python temporary
file directory (i.e., the directory name that is returned by the variable
`tempfile.tempdir` in Python). If you modify the KG2 software or runtime
environment so that `kg2-build` is in a different file system from the file
system in which the directory `tempfile.tempdir` resides, then the file copying
operations that are performed by the KG2 build software will not be atomic and
interruption of `build-kg2.py` could then leave a source data file in a
half-downloaded (i.e., broken) state.

## Setup your computing environment

The computing environment where you will be running the KG2 build should be
running Ubuntu 18.04 with `git` installed and configured in your shell path.
Your build environment should have the following minimum specifications:

- 128 GB of system RAM
- 500 GB of disk space in the root file system 
- high-speed network access
- ideally, AWS zone `us-west-2` since that is where the S3 buckets are located

The KG2 build system has been tested *only* under Ubuntu 18.04. If you want to
build KG2 but don't have a native installation of Ubuntu 18.04 available, your
best bet would be to use Docker (see the `Dockerfile` for this project). You'll
need to have an Amazon Web Services (AWS) authentication key that is configured
to be able to read from the `s3://rtx-kg2` Amazon Simple Cloud Storage Service
(S3) bucket (ask Stephen Ramsey to set this up) and to write to the S3 bucket
`rtx-kg2-public`. The KG2 build script downloads the UMLS and SNOMED CT
distributions from a private S3 bucket `rtx-kg2` (these distributions are
encumbered by licenses so they cannot be put on a public server for download) and
it uploads the `kg2.json` file to the public S3 bucket `rtx-kg2-public`.

## My normal EC2 instance

- AMI: Ubuntu Server 18.04 LTS (HVM), SSD Volume Type - `ami-005bdb005fb00e791` (64-bit x86)
- Instance type: `r5.4xlarge` 
- Storage: 500 GiB General Purpose SSD
- Security Group: `http+ssh`

## Build instructions

### Option 1: build KG2 directly on an Ubuntu system, not via ssh:

Run these commands in the `bash` shell, in order:

    cd
    
    sudo apt-get update -y
    
    sudo apt-get install -y screen git
    
    git clone https://github.com/RTXteam/RTX.git
    
    screen

Within the `screen` session, run:

    RTX/code/kg2/setup-kg2.sh > setup-kg2.log 2>&1
    
Then exit screen (`ctrl-a d`). You can watch the progress of `setup-kg2.sh` by
using the command:

    tail -f setup-kg2.log

Next, build `snomed.owl` (an OWL representation of the SNOMED CT US English
distribution), as follows: rejoin the `screen` session using `screen -r`.
In the `screen` session, do this:

    ~/kg2-code/build-snomed.sh > ~/kg2-build/build-snomed.log 2>&1
    
Then exit screen (`ctrl-a d`). You can watch the progress via:

    tail -f ~/kg2-build/build-snomed.log

The build process for `snomed.owl` takes about 10 minutes.  Next, build
`umls.owl` (an OWL representation of the UMLS Level 0 ontologies plus SNOMED
CT), as follows: rejoin the `screen` session using `screen -r`.  In the `screen`
session, do this:

    ~/kg2-code/build-umls.sh > ~/kg2-build/build-umls.log 2>&1
    
You can watch the progress via:

    tail -f ~/kg2-build/build-umls.log

The build process for `umls.owl` takes about XX hours. Next, rejoin the screen
session using `screen -r`.  Within the `screen` session, run:

    ~/kg2-code/build-kg2.sh

Then exit screen (`ctrl-a d`). You can watch the progress of your KG2 build by using these
two commands (run them in separate bash shell terminals):

    tail -f /home/ubuntu/kg2-build/build-kg2-stdout.log
    tail -f /home/ubuntu/kg2-build/build-kg2-stderr.log
    
### Option 2: remotely build KG2 in an EC2 instance via ssh, orchestrated from your local computer

Run these commands in the `bash` shell, in order:

    git clone https://github.com/RTXteam/RTX.git
    
    RTX/code/kg2/ec2-setup-remote-instance.sh

This should initiate a `bash` session on the remote instance. Within that `bash`
session, continue to follow the instructions for Option 1 (from the beginning).

### Option 3: in an Ubuntu container in Docker (UNTESTED, IN DEVELOPMENT)

If you are on Ubuntu and you need to install Docker, you can run this script:
   
    RTX/code/kg2/install-docker.sh
    
(otherwise, the subsequent commands in this section assume that Docker is installed
on whatever host OS you are running). Then run these commands in the `bash` shell:

    cd
    
    sudo docker build -t kg2 RTX/code/kg2/

    screen
    
    sudo docker run -it --name kg2 kg2:latest su - ubuntu -c "RTX/code/kg2/setup-kg2.sh > setup-kg2.log 2>&1"
    
Then exit screen (`ctrl-a d`). You can watch the progress of your KG2 setup using the command:

    sudo docker exec kg2 "tail -f setup-kg2.log"

Then again inside screen, run:

    sudo docker exec kg2 "kg2-code/build-kg2.sh"

Then exit screen (`ctrl-a d`). You can watch the progress of your KG2 setup using the
following two commands (in two two separate terminals):

    sudo docker exec -it kg2 tail -f /home/ubuntu/kg2-build/build-kg2-stdout.log
    sudo docker exec -it kg2 tail -f /home/ubuntu/kg2-build/build-kg2-stderr.log

## The output KG

The `build-kg2.sh` script (run via one of the three methods shown above) creates
a JSON file `kg2.json` and copies it to a publicly accessible S3 bucket
`rtx-kg2-public`. You can access the JSON file via HTTP, as shown here:

    curl https://s3-us-west-2.amazonaws.com/rtx-kg2-public/kg2.json > kg2.json

Or using the AWS command-line interface (CLI) tool `aws` with the command

    aws s3 cp s3://rtx-kg2-public/kg2.json .

You can access the various artifacts from the KG2 build (config file, log file,
etc.) at the AWS static website endpoint for the 
`rtx-kg2-public` S3 bucket: <http://rtx-kg2-public.s3-website-us-west-2.amazonaws.com/>
