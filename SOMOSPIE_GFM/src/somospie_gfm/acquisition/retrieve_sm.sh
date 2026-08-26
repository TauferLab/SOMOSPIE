#!/usr/bin/env bash

# Download one year of daily ESA-CCI combined soil-moisture files.
# Usage: retrieve_sm.sh YEAR OUTPUT_ROOT [MONTH]

set -u

if [[ $# -lt 2 || $# -gt 3 ]]; then
    echo "Usage: $0 YEAR OUTPUT_ROOT [MONTH]" >&2
    exit 2
fi

year="$1"
output_root="$2"
requested_month="${3:-}"
version="9.2"
year_dir="${output_root}/${year}"
base_url="ftp://anon-ftp.ceda.ac.uk/neodc/esacci/soil_moisture/data/daily_files/COMBINED/v0${version}/${year}"

command -v wget >/dev/null 2>&1 || { echo "wget is required" >&2; exit 1; }
mkdir -p "${year_dir}"

if [[ -n "${requested_month}" ]]; then
    [[ "${requested_month}" =~ ^(0[1-9]|1[0-2])$ ]] || {
        echo "MONTH must be two digits from 01 through 12" >&2
        exit 2
    }
    months=("${requested_month}")
else
    months=($(seq -f "%02g" 1 12))
fi

downloaded=0
failed=0
for month in "${months[@]}"; do
    days=$(date -u -d "${year}-${month}-01 +1 month -1 day" +%d)
    for day in $(seq -f "%02g" 1 "${days}"); do
        name="ESACCI-SOILMOISTURE-L3S-SSMV-COMBINED-${year}${month}${day}000000-fv0${version}.nc"
        if wget --no-clobber --tries=1 --timeout=60 --directory-prefix "${year_dir}" \
            "${base_url}/${name}"; then
            downloaded=$((downloaded + 1))
        else
            failed=$((failed + 1))
            echo "[warn] ESA-CCI download failed: ${name}" >&2
        fi
    done
done

echo "ESA-CCI download pass complete: ${downloaded} available, ${failed} failed"
find "${year_dir}" -type f -name '*.nc' -print -quit | grep -q . || {
    echo "No ESA-CCI files are available under ${year_dir}" >&2
    exit 1
}
