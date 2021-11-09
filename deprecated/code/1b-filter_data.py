#!/usr/bin/env python2

import sys, argparse

## Filters out datapoints from outside certain bounds (as specified for the first two dimensions of each vector)

#################################
# Retired 2019/10/30
# The box funcionality has been replaced with r-scripts
# The removal of specific value(s) should be implemented with pandas if needed.
#
# Description removed from code/README.txt:
#
#    1b-filter_data.py
#        takes a tsv or csv data file and filters out any rows which are
#        not in a specified bounding box, or which contain an error value,    
#        if such a value is specified
#
#################################

class Rect:
    def __init__(self, left, right, bottom, top):
        self.left = left
        self.top = top
        self.right = right
        self.bottom = bottom

    def contains(self, x, y):
    #    print(x, y, self.left <= x, x <= self.right, self.bottom <= y, y <= self.top)
        return self.left <= x and \
               x <= self.right and \
               self.bottom <= y and \
               y <= self.top


def parse_args():
    parser = argparse.ArgumentParser()
    
    #positional args:    
    parser.add_argument('data_file', \
                        help='the name of the data file to load')    

    #optional args:
    parser.add_argument('-b', '--bounds', \
                        nargs=4, \
                        type=float, \
                        #default=[-180, 180, -90, 90], \
                        default=[-124.7844079, -66.9513812, 24.7433195, 49.3457868], \
                        help='left, right, bottom, and top lat/long bounds on the data [defaults to bounding box around the continental US]')
                        #CONUS bounds from https://gist.github.com/jsundram/1251783
    parser.add_argument('-d', '--delim', \
                        default=',', \
                        help='the delimiter which seperates values in the data file')
    parser.add_argument('-c', '--clean', \
                        type=float, \
                        help='if specified, filters out any rows containing matching values')
    parser.add_argument('-s', '--skip', \
                        type=int, \
                        default=0, \
                        help='number of header rows to skip in file, if any')
    parser.add_argument('-o', '--output', \
                        help='the name of the file to save the filtered results into [\'filtered_$DATA_FILE\' by default]')

    args = parser.parse_args()

    PREFIX='filtered_'
    if not args.output:
        path = args.data_file.split('/')
        path[-1] = PREFIX + path[-1]
        args.output = "/".join(path)
    
    args.bounds = sorted(args.bounds[:2]) + sorted(args.bounds[2:])
    args.bounds = Rect(*args.bounds)
        
    return args

def read_to_array(filename, delim=',', skip=0):
    temp = [[], []]
    with open(filename, 'rb') as file:
        count = 0
        for line in file:
            if count >= skip:
                row = line.strip().split(delim)
                try:
                    temp[1].append(map(float, row))
                except:
                    pass
            else:
                temp[0].append(line)
            count += 1
    return temp

def write_to_file(filename, array, delim=','):
    with open(filename, 'wb') as file:
        for row in array[0]:
            file.write(row)
        for row in array[1]:
            file.write(delim.join(map(str,row)) + '\n')

if __name__ == "__main__":
    args = parse_args()    
    data = read_to_array(args.data_file, \
                         delim=args.delim, \
                         skip=args.skip)
    #print(data)
    data[1] = filter(lambda row: args.bounds.contains(row[0], row[1]) \
                                 and not args.clean in row, \
                     data[1])
    #print(data)
    write_to_file(args.output, data, delim=args.delim)

