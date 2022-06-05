import sys
import pandas as pd
import matplotlib.pyplot as plt


def visualization (prediction_filename, min, max, title, output_filename):
    # Creating the Data Frame with the values to visualize  
    prediction_values = pd.read_csv(prediction_filename, header=0, names = ['x','y','sm'])
    fig, ax = plt.subplots()
    prediction_values.plot.scatter(x='x', y='y', c='sm', cmap=plt.cm.get_cmap('RdBu'), title=title, vmin=min, vmax=max, figsize=(5,4), ax=ax)
    plt.savefig(output_filename, bbox_inches='tight', dpi=150)
    
    
if __name__ == "__main__":	
    # Reading the file to visualize
    prediction_filename = str(sys.argv[1])
    output_filename = str(sys.argv[2])
    min        = str(sys.argv[3])
    max        = str(sys.argv[4])
    title = str(sys.argv[5])



