#!/bin/bash

year=$1
version=6.1
sm_dir=data/ESA_CCI

if [ ! -d ${sm_dir}/${year} ]; then
    mkdir -p ${sm_dir}/${year}

    for month in $(seq -f "%02g" 1 12); do
        for day in $(seq -f "%02g" 1 31); do
            wget ftp://anon-ftp.ceda.ac.uk/neodc/esacci/soil_moisture/data/daily_files/COMBINED/v0${version}/${year}/ESACCI-SOILMOISTURE-L3S-SSMV-COMBINED-${year}${month}${day}000000-fv0${version}.nc -nc -t 1 -P ${sm_dir}/${year}/
        done
    done
fi
