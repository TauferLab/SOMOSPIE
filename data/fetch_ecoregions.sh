#!/bin/bash

# If "data" is a subfolder to the working directory, 
#  we want to move inside the "data" folder before fetching the shapefiles. 
[ -d "data" ] && cd data

ECO=TerrestrialEcoregions_L2_Shapefile
wget http://www.cec.org/wp-content/uploads/wpallimport/files/Atlas/Files/Terrestrial_Ecoregions_L2/TerrestrialEcoregions_L2_Shapefile.zip
unzip -o TerrestrialEcoregions_L2_Shapefile.zip
rm -r TerrestrialEcoregions_L2_Shapefile.zip
echo $(date) > $ECO/downloaded.txt
find $ECO/ -name "terrestrial_Ecoregions_updated.shp" -exec echo {} > path_CEC.txt \;
# The following two lines were used once to update .gitignore, which was updated in the repo,
#  so these two lines were commented out and need not be run again.
#echo $ECO >> .gitignore
#echo path\*.txt >> .gitignore

NEON=NEONDomains_0
wget https://www.neonscience.org/sites/default/files/$NEON.zip
mkdir $NEON
cd $NEON
unzip -o ../$NEON.zip
cd ../
rm $NEON.zip
echo $NEON/NEON_Domains.shp > path_NEON.txt
# The following two lines were used once to update .gitignore, which was updated in the repo,
#  so these two lines were commented out and need not be run again.
#echo $NEON >> .gitignore
#echo path\*.txt >> .gitignore
