#!/usr/bin/env bash

# Download the official CEC North American terrestrial ecoregion shapefiles.
# Usage: retrieve_ecoregion_shapefiles.sh [output_directory]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
OUTPUT_DIR="${1:-${PROJECT_ROOT}/resources/shapefiles}"

LEVEL_1_URL="https://www.cec.org/wp-content/uploads/wpallimport/files/Atlas/Files/Terrestrial_Ecoregions_L1/NA_Terrestrial_Ecoregions_Level_I_Shapefile.zip"
LEVEL_2_URL="https://www.cec.org/wp-content/uploads/wpallimport/files/Atlas/Files/Terrestrial_Ecoregions_L2/NA_Terrestrial_Ecoregions_Level_II_Shapefile.zip"
LEVEL_3_URL="https://www.cec.org/wp-content/uploads/wpallimport/files/Atlas/Files/Terrestrial_Ecoregions_L3/NA_Terrestrial_Ecoregions_v2_Level_III_Shapefile.zip"

if ! command -v unzip >/dev/null 2>&1; then
    echo "unzip is required" >&2
    exit 1
fi
if command -v curl >/dev/null 2>&1; then
    DOWNLOADER="curl"
elif command -v wget >/dev/null 2>&1; then
    DOWNLOADER="wget"
else
    echo "curl or wget is required" >&2
    exit 1
fi

TEMP_DIR="$(mktemp -d)"
trap 'rm -rf -- "${TEMP_DIR}"' EXIT

download() {
    local url="$1"
    local destination="$2"
    if [[ "${DOWNLOADER}" == "curl" ]]; then
        curl --fail --location --retry 3 --output "${destination}" "${url}"
    else
        wget --tries=3 --output-document="${destination}" "${url}"
    fi
}

complete_shapefile() {
    local directory="$1"
    local shapefile stem suffix complete
    while IFS= read -r shapefile; do
        stem="${shapefile%.*}"
        complete=true
        for suffix in dbf prj shp shx; do
            if [[ ! -f "${stem}.${suffix}" ]]; then
                complete=false
                break
            fi
        done
        [[ "${complete}" == true ]] && return 0
    done < <(find "${directory}" -type f -iname '*.shp' 2>/dev/null)
    return 1
}

fetch_level() {
    local level="$1"
    local url="$2"
    local destination="${OUTPUT_DIR}/level${level}"
    local archive="${TEMP_DIR}/level${level}.zip"
    local staging="${TEMP_DIR}/level${level}"

    if complete_shapefile "${destination}"; then
        echo "[ecoregions] Level ${level} already present: ${destination}"
        return
    fi

    echo "[ecoregions] Downloading Level ${level}"
    download "${url}" "${archive}"
    mkdir -p "${staging}"
    unzip -q "${archive}" -d "${staging}"
    if ! complete_shapefile "${staging}"; then
        echo "Level ${level} archive contains no complete shapefile" >&2
        exit 1
    fi

    mkdir -p "${destination}"
    cp -a "${staging}/." "${destination}/"
    echo "[ecoregions] Installed Level ${level}: ${destination}"
}

mkdir -p "${OUTPUT_DIR}"
fetch_level 1 "${LEVEL_1_URL}"
fetch_level 2 "${LEVEL_2_URL}"
fetch_level 3 "${LEVEL_3_URL}"
echo "[ecoregions] Shapefiles available under ${OUTPUT_DIR}"
