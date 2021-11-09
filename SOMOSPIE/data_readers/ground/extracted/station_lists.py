#!/usr/bin/env python3

import pathlib
import csv

start_year = 2010 #1996
end_year = 2013 #2013

for y in range(start_year, end_year + 1):

    folder = pathlib.Path(str(y))
    #print(len(list(folder.iterdir())))
    stations = [stat.stem for stat in folder.iterdir()]
    #print(stations)
    out_file = folder.joinpath("station_list.csv")
    with open(out_file, "w") as out:
        writer = csv.writer(out, delimiter=",")
        writer.writerow(stations)

