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

# example.csv
#
# Cell_1_PrbTotDl;Cell_2_PrbTotDl
# 80;70
# 70;60

# usage:  <script>.sh /path/to/example.csv

# path to input csv file
input_csv_file=$1

create_pm_report () {
    file_name=$1
    prb_usage_1=$2
    prb_usage_2=$3

    cat > $file_name << EOF
<?xml version="1.0" encoding="UTF-8"?>
<?xml-stylesheet type="text/xsl" href="MeasDataCollection.xsl"?>
<measCollecFile xmlns="http://www.3gpp.org/ftp/specs/archive/32_series/32.435#measCollec"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xsi:schemaLocation="http://www.3gpp.org/ftp/specs/archive/32_series/32.435#measCollec">
    <fileHeader fileFormatVersion="32.435 V10.0"
        vendorName="Tietoevry"
        dnPrefix="SubNetwork=SMaRT-5G-VM-Test">
        <fileSender localDn="NODE_NAME"
            elementType="RadioNode" />
        <measCollec beginTime="BEGINTIME" />
    </fileHeader>
    <measData>
        <managedElement localDn="NODE_NAME"
            swVersion="SMaRT-5G-v0.0.1" />
        <measInfo measInfoId="PM=1,PmGroup=NRCellDU_GNBDU">
            <job jobId="nr_all" />
            <granPeriod duration="PT900S"
                endTime="ENDTIME" />
            <repPeriod duration="PT900S" />
            <measType p="1">prb_usage</measType>
            <measValue measObjLdn="ManagedElement=NODE_NAME,GNBDUFunction=1,NRCellDU=14550001">
                <r p="1">$prb_usage_1</r>
            </measValue>
            <measValue measObjLdn="ManagedElement=NODE_NAME,GNBDUFunction=1,NRCellDU=1454c001">
                <r p="1">$prb_usage_2</r>
            </measValue>
        </measInfo>
    </measData>
    <fileFooter>
        <measCollec endTime="ENDTIME" />
    </fileFooter>
</measCollecFile>
EOF

    gzip $file_name
}

skip_headers=1
id=0

while IFS=',' read -r cell1 cell2
do
    if ((skip_headers))
    then
        ((skip_headers--))
    else
        file_name="ran-sim-$id.xml"
        create_pm_report $file_name $cell1 $cell2
        ((id++))
    fi
done < $input_csv_file
