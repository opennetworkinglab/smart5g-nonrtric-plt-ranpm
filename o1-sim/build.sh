#!/bin/bash

#  ============LICENSE_START===============================================
#  Copyright (C) 2023 Tietoevry. All rights reserved.
#  ========================================================================
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#  ============LICENSE_END=================================================
#

# Build image from Dockerfile located in external directory with/without custom image tag
# Optionally push to external image repo

print_usage() {
    echo "Usage: build.sh no-push|<docker-hub-repo-name> [--tag <image-tag>]"
    exit 1
}

if [ $# -ne 1 ] && [ $# -ne 3 ]; then
    print_usage
fi

IMAGE_TAG="latest"
REPO=""
RAN_O1_SIM_PATH_FILE=".ran-o1-sim.path"

if [ $1 == "no-push" ]; then
    echo "Only local image build"
else
    REPO=$1
    echo "Attempt to push built image to: "$REPO
fi

shift
while [ $# -ne 0 ]; do
    if [ $1 == "--tag" ]; then
        shift
        if [ -z "$1" ]; then
            print_usage
        fi
        IMAGE_TAG=$1
        echo "Setting image tag to: "$IMAGE_TAG
        shift
    else
        echo "Unknown parameter: $1"
        print_usage
    fi
done

export DOCKER_DEFAULT_PLATFORM=linux/amd64
CURRENT_PLATFORM=$(docker system info --format '{{.OSType}}/{{.Architecture}}')
if [ $CURRENT_PLATFORM != $DOCKER_DEFAULT_PLATFORM ]; then
    echo "Image may not work on the current platform: $CURRENT_PLATFORM, only platform $DOCKER_DEFAULT_PLATFORM supported"
fi

ranpm_dir=$(pwd)
if [ -f $RAN_O1_SIM_PATH_FILE ]; then
    o1_sim_path=$(cat $RAN_O1_SIM_PATH_FILE)
    cd $o1_sim_path/ntsimulator
else
    echo "O1 Simulator path cannot be restored."
    is_path_valid=false
    while  [ $is_path_valid == false ]
    do
        read -p "Please enter a valid ABSOLUTE path to O1 Sim repository: " o1_sim_path 
        ls $o1_sim_path/ntsimulator && is_path_valid=true
    done

    echo $o1_sim_path > $RAN_O1_SIM_PATH_FILE
    cd $o1_sim_path/ntsimulator
fi

echo "Building image nts-ng-base"
./nts_build.sh nts-ng-base
if [ $? -ne 0 ]; then
    echo "BUILD FAILED"
    exit 1
fi
echo "BUILD OK"

if [ "$REPO" != "" ]; then
    echo "Tagging image"
    IMAGE=nts-ng-base:$IMAGE_TAG
    NEW_IMAGE=$REPO/$IMAGE
    docker tag nts-ng-base $NEW_IMAGE
    if [ $? -ne 0 ]; then
        echo "RE-TAGGING FAILED"
        exit 1
    fi
    echo "RE-TAG OK"

    echo "Pushing image $NEW_IMAGE"
    docker push $NEW_IMAGE
    if [ $? -ne 0 ]; then
        echo "PUSHED FAILED"
        echo " Perhaps not logged into docker-hub repo $REPO?"
        exit 1
    fi
    echo "PUSH OK"
fi

echo "Building image nts-ng-o-ran-du"
./nts_build.sh nts-ng-o-ran-du
if [ $? -ne 0 ]; then
    echo "BUILD FAILED"
    exit 1
fi
echo "BUILD OK"

if [ "$REPO" != "" ]; then
    echo "Tagging image"
    IMAGE=nts-ng-o-ran-du:$IMAGE_TAG
    NEW_IMAGE=$REPO/$IMAGE
    docker tag nts-ng-o-ran-du:1.8.1 $NEW_IMAGE
    if [ $? -ne 0 ]; then
        echo "RE-TAGGING FAILED"
        exit 1
    fi
    echo "RE-TAG OK"

    echo "Pushing image $NEW_IMAGE"
    docker push $NEW_IMAGE
    if [ $? -ne 0 ]; then
        echo "PUSHED FAILED"
        echo " Perhaps not logged into docker-hub repo $REPO?"
        exit 1
    fi
    echo "PUSH OK"
fi

echo $o1_sim_path > $ranpm_dir/$RAN_O1_SIM_PATH_FILE

echo "DONE"
