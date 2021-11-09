#!/usr/bin/env python3

#Code by Danny Rorabaugh, 2018

#This is the general-use script for various steps of Stage 0: Pre-processing

#The following was removed from code/README.txt
'''
    0-preproc.py 
        A general-purpose pre-processing script
            * Converts between any delimiters
            * Keeps/removes specified columns
    
      Call with:
        ./0-preproc in_file [-i] [-k] [-c] [-m] [-y] [-d] [-o] [-s]

      Arguments:

        Required:
        in_file         Path of the file to be processed
                        Expects an array with the first line a header row and each successive line a row of data

        Optional:
        -i, --in_delim  The delimiter of the input file
        -k, --keep_n    Specify to keep the first n columns
        -c, --cut_cols  Specify to remove specific columns
        -m, --month     Specify a month to keep, and remove cols for all other months
        -y, --year      Specify a year to keep, and remove cols for all other years
                        At most one of -k, -c, -m, and -y should be used
        -d, --out_dir   Path of directory for processed file
        -o, --out_delim Delimiter to use for out file
                        ',' by default
        -s, --suffix    Attached to end of file name        
'''

import argparse
import re

if __name__ == "__main__":

    #configure parser for command line arguments
    parser = argparse.ArgumentParser()

    ##Arguments regarding the input file
    #The file to be processed is the only required parameter
    parser.add_argument('in_file', \
                        help='The name of the data file to be preprocessed')
    #If --in_delim is not specified, we will look at the first line of the file 
    parser.add_argument('-i', '--in_delim', \
                        help='The delimiter of the input file')

    ##Arguments regarding the pre-processing to do; 
    ##DON'T USE MORE THAN ONE OF THE FOLLOWING 3
    parser.add_argument('-k', '--keep_n', \
                        type = int, 
                        help='Just keep the first n columns of the file')
    parser.add_argument('-c', '--cut_cols', 
                        nargs='+',
                        type=int, 
                        help='If columns need to be cut, use this argument')
    parser.add_argument('-y', '--year', \
                        type=int, \
                        default=0, \
                        help='For cutting all years except the one specified')
    parser.add_argument('-m', '--month', \
                        type=int, \
                        default=0, \
                        help='For cutting all months except the one specified')

    ##Arguments regarding the output file
    #If --out_dir is not specified, we will use the dir of the in_file.
    parser.add_argument('-d', '--out_dir',\
                        help='The out directory of the pre-processed file')
    #If --out_delim is not specific, the default is ',' for a .csv
    parser.add_argument('-o', '--out_delim', \
                        default=',', \
                        help='The delimiter of the output file')
    #Should there be a header row in the output file?
    parser.add_argument('-H', '--out_header', \
                        default=1, \
                        type=int, \
                        help='Set to 0 to not have a header row in the output file.')
    #If --suffix is not specified, the default is to use the same name
    #... unless being placed in the same directory
    parser.add_argument('-s', '--suffix', \
                        default='', \
                        help='Affix this to the end of the output file')

    args = parser.parse_args()
    print("Running 0-preproc.py with args:\n{}".format(args))

    ################################################
    #Open up file to make sure we have data and in case we need the header line later
    in_path = args.in_file

    with open(in_path, 'r') as file_in:
        #Pull off the first few lines
        header = file_in.readline().strip('\n')
        line = file_in.readline().strip('\n')
        if not len(line):
            print('Your data file has no data!')
            exit()

    #################################################
    #Establish the delimiter of the input file
    delim_i = args.in_delim
    delim_dict = {',':'csv', '\t':'tsv'}

    if not delim_i:
        in_format = args.in_file.split('.')[-1]
        format_dict = {'csv':',', 'tsv':'\t'}
        if in_format in format_dict:
            delim_i = format_dict[in_format]
        else:
            #If the file format does not indicate the delimiter,
            # check if there is a consistant delimiter use between the header and first data row
            for d in delim_dict:
                h = header.count(d)
                l = line.count(d)
                if h>0 and h==l:
                    delim_i = d
                    break
            if not delim_i:
                print("Input file delimiter could not be determined. Please specify with -i.")
                exit()
    print("The delimiter of the input file is '{}'.".format(delim_i))

    ##########################################
    #Build path for the out_file
    in_split = in_path.split('/')

    #First, directory
    out_dir = args.out_dir
    if not out_dir:
        out_dir = '/'.join(in_split[:-1]) + '/'

    #Second, file name
    out_name = in_split[-1].split('.')
    out_name = '.'.join(out_name[:-1])
    suff = args.suffix
    out_name += bool(suff)*(str(suff))
    delim_o = args.out_delim
    out_name += '.' + delim_dict.get(delim_o, 'txt')

    #Third, stick them together
    out_path = out_dir + out_name
    if in_path==out_path:
        print("Specify --suffix or --out_dir to prevent overwriting your in_file.")
        exit()

    #########################################
    #See which of the columns to keep of columns 0 through M
    h_split = header.split(delim_i)
    M = len(h_split)

    #Make list of the starting indices of intervals of columns to save 
    cols_save_a = [0]

    #First check if only the first n columns are to be kept
    k = args.keep_n
    month = args.month
    if k:
        cols_save_b = [k]

    else:
        year = args.year
        #Then check if columns were specified to cut.
        cols_save_b = []
        cols_cut = args.cut_cols
        if cols_cut:
            cols_cut.sort()
            cols_save_a +=  map(lambda x: x+1, cols_cut)
            cols_save_b = cols_cut

        #Otherwise, check if a month was specified
        #This assumes that there are twelve months, in columns 1 through 13
        elif month:
            cols_save_a += [month + 1, 14]
            cols_save_b += [2, month + 2]
        #Otherwise, check if a year was specified
        #The following process makes a few assumptions:
        #   -The only headers that are 4-digit number are years
        #   -All year headers are in consecutive columns
        #   -A given year will only have one relevant column
        elif year:
            if str(year) not in h_split:
                print('The data does not include the specified year.')
                exit()

            #Go until we hit the first year-headed column 
            i = 0
            while not cols_save_b:
                head = h_split[i]
                try:
                    int(head)
                    if len(head)==4:
                        cols_save_b.append(i)
                except:
                    None
                i += 1
                
            #Add the desired year to the col_save's
            i = h_split.index(str(year))
            cols_save_a.append(i)
            i += 1
            cols_save_b.append(i)

            #Go until we pass the last year-headed column
            while i<M and len(cols_save_a)==2:
                head = h_split[i]
                try:
                    int(head)
                    if len(head)!=4:
                        cols_save_a.append(i)
                except:
                    cols_save_a.append(i)
                i += 1
        
        cols_save_b.append(M)
        
    #Zip a's and b's together for list of intervals to save
    cols_save = list(zip(cols_save_a, cols_save_b))
    print("The intervals of columns to be saved are: {}".format(cols_save))

    ###################################################
    #Transer desired data from file_in to file_out

    with open(in_path, 'r') as file_in:
        line_in = file_in.readline().strip('\n').split(delim_i)
        if not args.out_header:
            line_in = file_in.readline().strip('\n').split(delim_i)

        #The following removes non-alphanumeric characters from the header row
        #line_in = [re.sub(r'\W+', '', head) for head in line_in]
        #The following is to convert the month to a number
        if month:
            line_in[month + 1] = str(month)

        print("Writing data to {}".format(out_path))
        delim_o = args.out_delim
        with open(out_path, 'w') as file_out:
            while len(line_in)>1:
                line_out = []
                for a,b in cols_save:
                    line_out += line_in[a:b]
                line_out = delim_o.join(line_out) + '\n'
                file_out.write(line_out)

                line_in = file_in.readline().strip('\n').split(delim_i)

