#!/bin/bash

# If "data" is a subfolder to the working directory, 
#  we want to move inside the "data" folder before fetching the shapefiles. 
[ -d "data" ] && cd data

# Fetching Eco-Region level 1
#
ECO=NA_Terrestrial_Ecoregions_Level_I_Shapefile
### Check for dir, if not found create it using the mkdir ##

if [ ! -d "ECO" ]; then

    wget http://www.cec.org/wp-content/uploads/wpallimport/files/Atlas/Files/Terrestrial_Ecoregions_L1/NA_Terrestrial_Ecoregions_Level_I_Shapefile.zip
    unzip -o NA_Terrestrial_Ecoregions_Level_I_Shapefile.zip
    rm -r NA_Terrestrial_Ecoregions_Level_I_Shapefile.zip
    echo $(date) > $ECO/downloaded.txt
    find $ECO/ -name "NA_Terrestrial_Ecoregions_v2_level1.shp" -exec echo {} > path_CEC.txt \;
fi

# Fetching Eco-Region level 2
#
ECO=NA_Terrestrial_Ecoregions_Level_II_Shapefile
### Check for dir, if not found create it using the mkdir ##
if [ ! -d "ECO" ]; then

    wget http://www.cec.org/wp-content/uploads/wpallimport/files/Atlas/Files/Terrestrial_Ecoregions_L2/NA_Terrestrial_Ecoregions_Level_II_Shapefile.zip
    unzip -o NA_Terrestrial_Ecoregions_Level_II_Shapefile.zip
    rm -r NA_Terrestrial_Ecoregions_Level_II_Shapefile.zip
    echo $(date) > $ECO/downloaded.txt
    find $ECO/ -name "NA_Terrestrial_Ecoregions_v2_level2.shp" -exec echo {} > path_CEC.txt \;
fi

# Fetching Eco-Region level 3
#
ECO=NA_Terrestrial_Ecoregions_v2_Level_III_Shapefile
if [ ! -d "ECO" ]; then
    wget http://www.cec.org/wp-content/uploads/wpallimport/files/Atlas/Files/Terrestrial_Ecoregions_L3/NA_Terrestrial_Ecoregions_v2_Level_III_Shapefile.zip
    unzip -o NA_Terrestrial_Ecoregions_v2_Level_III_Shapefile.zip
    rm -r NA_Terrestrial_Ecoregions_v2_Level_III_Shapefile.zip
    echo $(date) > $ECO/downloaded.txt
    find $ECO/ -name "NA_Terrestrial_Ecoregions_v2_level3.shp" -exec echo {} > path_CEC.txt \;
fi
# The following two lines were used once to update .gitignore, which was updated in the repo,
#  so these two lines were commented out and need not be run again.
#echo $ECO >> .gitignore
#echo path\*.txt >> .gitignore

NEON=NEONDomains_0
wget https://www.neonscience.org/sites/default/files/$NEON.zip
if [ ! -d "NEON" ]; then
mkdir $NEON
fi

cd $NEON
unzip -o ../$NEON.zip
cd ../
rm $NEON.zip
echo $NEON/NEON_Domains.shp > path_NEON.txt
# The following two lines were used once to update .gitignore, which was updated in the repo,
#  so these two lines were commented out and need not be run again.
#echo $NEON >> .gitignore
#echo path\*.txt >> .gitignore
