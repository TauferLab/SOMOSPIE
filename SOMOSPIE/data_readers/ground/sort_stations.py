#!/usr/bin/env python3

import pandas as pd

start_year = 2012 #1996
end_year = 2012 #2013

for year in range(start_year, end_year + 1):

    counts = pd.read_csv(f"stations_per_region/{year}.csv")
    counts["density"] = counts["area"]/counts["stations"]
    c_sorted = counts.sort_values(["level", "density"])
    #c_sorted = counts[counts["level"]==2].sort_values(["stations"], ascending=False)
    print(c_sorted)
    for L1 in [2,5,6,7,8,9,10,11,12,13,15]:
        sorted = c_sorted[c_sorted.apply(lambda x: x['region'][0]==str(L1), axis=1)]
        print(sorted)
