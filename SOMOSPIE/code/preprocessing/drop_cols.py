#!/usr/bin/env python3

# Script by Danny Rorabaugh, 2018
# Read in specified in_file
# and save to specified out_file
# keeping/dropping specified columns

import argparse
import pandas as pd

parser = argparse.ArgumentParser()

parser.add_argument("in_file", 
                    help="Path for input csv file.")
parser.add_argument("out_file", 
                    help="Path for ouput file.")
parser.add_argument("-k", "--keep", 
                    help="Comma-seperated list of columns to keep. If -k/--keep is used, -d/--drop is ignored.")
parser.add_argument("-d", "--drop", 
                    help="Comma-seperated list of columns to drop, keeping the rest. Superceded by -k/--keep.")
parser.add_argument("-H", "--head", type=int, default=1, 
                    help="Boolean: does the file have header row(s), which are handled differently than data?")

args = parser.parse_args()
print(f"args: {args}")

if args.head:
    head = 'infer'
else:
    head = None
    
# Read in the in_file                    
df = pd.read_csv(args.in_file, header=head)
header = df.columns
n = len(header)

print(f"Old columns: {header}")

if args.keep:
    cols = [header[int(c)] for c in args.keep.split(",")]
elif args.drop:
    uncols = [int(c) for c in args.drop.split(",")]
    print(f"Dropping columns with these indices: {uncols}")
    cols = [header[c] for c in range(n) if c not in uncols]
else:
    print(f"You need to either specify columns to keep with -k or columns to drop with -d.")
    exit

print(f"Keeping columns: {cols}")
df = df[cols]

print(f"New columns: {df.columns}")

# Write out to the out_file
df.to_csv(args.out_file, index=False, header=args.head)
