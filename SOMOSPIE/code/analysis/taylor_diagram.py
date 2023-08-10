import pandas as pd
import skill_metrics as sm
from matplotlib import rcParams
import matplotlib.pyplot as plt
from matplotlib import lines
import numpy as np
import os


def taylorDiagram(reference, predictions, labels, title, out_file, axislim=0, normalize=False, n_panels=1):
    # All prediction vectors must have the same reference, that is to compare different models that predict the same
    # variable in the same units, otherwise function should be modified to always normalize by each reference SD.
    # Predictions is a list of vectors (numpy arrays): predictions = [pred1, pred2]

    # Use colors from matplotlib selected style
    colors = plt.rcParams["axes.prop_cycle"].by_key()["color"]

    # Set the figure properties
    rcParams["figure.figsize"] = [6, 6]
    rcParams['lines.linewidth'] = 1
    plt.rcParams['figure.titlesize'] = 20
    plt.rcParams['font.size'] = 12
    plt.rcParams['xtick.labelsize'] = 12
    plt.rcParams['ytick.labelsize'] = 12

    models_legend = []
    iter0 = True

    for i, pred in enumerate(predictions):
        taylor_stats = sm.taylor_statistics(pred, reference)

        sdev = np.array(taylor_stats['sdev'])
        crmsd = np.array(taylor_stats['crmsd'])
        ccoef = np.array(taylor_stats['ccoef'])

        if normalize:
            crmsd = np.divide(crmsd, sdev[0])
            sdev = np.divide(sdev, sdev[0])

        # On the first iteration the axis and reference point are set, then each point representing each model is overlayed on top
        if iter0:
            sm.taylor_diagram(sdev, crmsd, ccoef, colcor='#919191', colrms='#2ca02c', stylecor='-', stylestd='--',
                              styleOBS='-', markerobs='.', axisMax=axislim,
                              titleOBS='Reference', markercolor=colors[i],
                              markersize=15, colobs='k', numberpanels=n_panels)

            # Other arguments that could be set:
            # tickSTD = np.arange(0, 1.25, 0.25),
            # tickRMS = np.arange(0, 1.2, 0.2),\
            # rmsLabelFormat = ':.1f', axisMax = 1.2,
            # titlermsdangle = 65,
            # tickrmsangle = 115,

            plt.text(sdev[0], 0.09, "Reference", verticalalignment="top", horizontalalignment="center", fontweight="bold")
            iter0 = False
        else:
            sm.taylor_diagram(np.array([sdev[0], sdev[-1]]), np.array([crmsd[0], crmsd[-1]]),
                              np.array([ccoef[0], ccoef[-1]]), overlay='on', markersize=15,
                              markercolor=colors[i % len(colors)])

        models_legend.append(
            lines.Line2D([], [], linestyle='None', marker='.', markersize=15, c=colors[i % len(colors)]))

    plt.legend(models_legend, labels)
    plt.title(title, y=1.04)
    plt.ylabel('Standard Deviation{}'.format(' (normalized)' if normalize else ''))
    plt.xlabel('Standard Deviation{}'.format(' (normalized)' if normalize else ''))

    plt.tight_layout()
    plt.savefig(out_file + '.png', bbox_inches='tight', dpi=150)
    plt.close()


if __name__ == '__main__':
    # Ground truth validation Taylor Diagram for 1 month
    region = 'west'
    model = 'knn'
    time_res = 'monthly'
    gt_out_folder = os.path.join("/home/exouser/SOMOSPIE/SOMOSPIE/data", region, time_res, model, "ground_truth_validation")


    results_df = pd.read_csv(os.path.join(gt_out_folder, "01.csv"), index_col=0)
    taylor_labels = ['KNN']
    taylor_title = 'Ground Truth Validation (January 2010) \n SOMOSPIE'
    taylor_file = os.path.join(gt_out_folder, 'taylor_01.csv')

    taylorDiagram(results_df['Ref'], [results_df['Pred']], labels=taylor_labels, title=taylor_title, out_file=taylor_file, axislim=2, normalize=True)