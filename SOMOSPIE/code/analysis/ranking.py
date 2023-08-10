import numpy as np
import matplotlib.pyplot as plt
from matplotlib import transforms
import seaborn as sns
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.feature_selection import f_regression
from sklearn.feature_selection import mutual_info_regression
from sklearn.ensemble import RandomForestRegressor
from sklearn.feature_selection import SelectKBest


def get_scores(X, Y, methods):
    scores = np.zeros((X.shape[1], len(methods)))
    for i, method in enumerate(methods):
        if method == 'LR':
            reg = LinearRegression().fit(X, Y)
            scores[:, i] = np.abs(reg.coef_)
        elif method == 'ULR':
            ureg = SelectKBest(score_func=f_regression, k='all').fit(X, Y)
            scores[:, i] = ureg.scores_
        elif method == 'MI':
            minfo = SelectKBest(score_func=mutual_info_regression, k='all').fit(X, Y)
            scores[:, i] = minfo.scores_       
        elif method == 'RF':
            reg = RandomForestRegressor(n_estimators=100, max_depth=None, random_state=0).fit(X, Y)
            scores[:, i] = np.abs(reg.feature_importances_)
        else:
            raise Exception('Method: <' + method + '> is not supported.')
    return scores


def plot_ranking(labels, scores, score_names, descending=True, fig_title='', filename=''):
    # Labels is a 1-d array of strings, Scores is a 2-d array of numbers
    labels = np.array([label if len(label.split()) < 2 else '. '.join([s[0:2] for s in label.split()]) for label in labels])

    scores = scores.reshape((scores.shape[0], 1 if scores.ndim == 1 else scores.shape[1]))
    labels_by_score = np.empty_like(scores, dtype=np.dtype('U100'))
    ranking = np.empty_like(scores, dtype=int)
    
    # Sort labels by score
    for j in range(scores.shape[1]):
        ranking[:, j] = scores[:, j].argsort()[::-1] if descending else scores[:, j].argsort()
        labels_by_score[:, j] = labels[ranking[:, j]]


    t = transforms.Affine2D().rotate_deg(90)  # Axis transformation
    
    width = 0.5 + 1 *(scores.shape[1] - 1)
    height = 1 + 0.2 * scores.shape[0]

    fig, ax = plt.subplots(figsize=(width, height), dpi=100)
    sns.heatmap(ranking, annot=labels_by_score, fmt='', cmap=sns.color_palette("Spectral", as_cmap=True),
                linewidths=0.1, cbar=False, xticklabels=score_names, yticklabels=scores.shape[0], ax=ax)
    ax.xaxis.tick_top()
    ax.set_ylabel('Ranking')
    ax.set_title(fig_title)
    plt.tight_layout()
    #plt.savefig(filename, bbox_inches='tight', dpi=150)


# Scores Scatterplot
def plot_scores(labels, scores, score_names, legend=None, shading=True, shading_int=1, xlabel='x', ylim=None, title='',filename=None):
    # Scores is a 2d array: each row has a score for a single feature and each column represents a score from a different method or month
    x_ticks = range(len(score_names))

    # Change the shape of the data to plot: https://stackoverflow.com/questions/37490771/seaborn-categorical-plot-with-hue-from-dataframe-rows
    df = pd.DataFrame(scores, columns=x_ticks, index=labels if legend is None else legend)
    df.index.name = 'Features'
    df.columns.name = xlabel

    s = df.stack()
    s.name = 'Scores'
    df_tidy = s.reset_index()

    # Figure parameters
    width = scores.shape[1]
    height = scores.shape[1] // 2
    fig, ax = plt.subplots(figsize=(width, height), dpi=100)

    # Plot: plot with different markers for each feature and trendline, plot with same markers but different colors, scatterplot without trend lines
    ax = sns.lineplot(data=df_tidy, hue='Features', x=xlabel, y='Scores', markers=True, style='Features', linewidth=0.5,
                      markersize=8)
    # ax = sns.lineplot(data=df_tidy, hue='Features', x=xlabel, y='Scores', marker='o', linewidth=0.5, markersize=6)
    # ax = sns.scatterplot(data=df_tidy, hue='Features', x=xlabel, y='Scores')

    # Legend, custom ticks and title
    sns.move_legend(ax, "upper left", bbox_to_anchor=(1, 1))
    ax.set_xticks(x_ticks)
    ax.set_xticklabels(score_names)
    ax.set_title(title)
    ax.set_axisbelow(True)
    # ax.xaxis.grid(which='major', alpha=0.5) # set vertical grid lines

    # Plot Feature name next to its marker if the score is above a certain threshold
    scores_tresh = np.percentile(scores, 70)
    # df_tidy.loc[df_tidy['Scores'] <= scores_tresh, 'Features'] = ''

    for i, row in df_tidy.iterrows():
        if row['Scores'] > scores_tresh:
            ax.text(row[xlabel] + 0.05, row['Scores'], row['Features'][0:3], fontsize=9)

    # Shading
    delta = 0.5
    for i in range(len(score_names) // shading_int):
        if not i % 2:
            ax.axvspan(i * shading_int - delta, i * shading_int + shading_int - delta, facecolor='gainsboro', alpha=0.2)

    ax.set_xlim([-delta, x_ticks[-1] + delta])
    ax.set_ylim(ylim)
    plt.tight_layout()
    plt.show()
    

 #Scores heatmap
def plot_scores2(labels, scores, score_names, fig_title, filename):
    # Labels is a 1-d array of strings, Scores is a 2-d array of numbers
    labels = np.array([label if len(label.split()) < 2 else '. '.join([s[0:2] for s in label.split()]) for label in labels])

    scores = scores.reshape((scores.shape[0], 1 if scores.ndim == 1 else scores.shape[1]))
    #labels = np.repeat(labels.reshape(labels.shape[0], 1), scores.shape[1], axis=1)


    t = transforms.Affine2D().rotate_deg(90)  # Axis transformation
    
    width = scores.shape[1]//2 # For full name 2, for 1 letter 0.5
    height = 4 * scores.shape[0] / 15

    fig, ax = plt.subplots(figsize=(width, height), dpi=100)
    sns.heatmap(scores, fmt='', cmap=sns.color_palette("viridis", as_cmap=True),
                linewidths=0.1, cbar=True, xticklabels=score_names, yticklabels=labels, ax=ax)
    ax.xaxis.tick_top()
    ax.set_ylabel('Features')
    ax.set_title(fig_title)
    plt.tight_layout()
    #plt.savefig(filename, bbox_inches='tight', dpi=150)


def get_feature_names(terrain_params):
    feature_names = {'Hillshading': 'Hillshading',
    'Aspect': 'Aspect',
    'Channel Network Base Level': 'Channel Network Base Level',
    'Channel Network Distance': 'Channel Network Distance',
    'Closed Depressions': 'Closed Depressions',
    'Convergence Index': 'Convergence Index',
    'Elevation': 'Elevation',
    'LS Factor': 'LS Factor',
    'Plan Curvature': 'Plan Curvature',
    'Profile Curvature': 'Profile Curvature',
    'Relative Slope Position': 'Relative Slope Position',
    'Slope': 'Slope',
    'TWI': 'TWI',
    'Total Catchment Area': 'Total Catchment Area',
    'Valley Depth': 'Valley Depth',
    'CONUS_DEM1km': 'Elevation',
    'Aspect': 'Aspect',
    'Analytical_Hillshading': 'Hillshading',
    'Channel_Network_Base_Level': 'Channel Network Base Level',
    'Closed_Depressions': 'Closed Depressions',
    'Convergence_Index': 'Convergence Index',
    'Cross-Sectional_Curvature': 'Plan Curvature',
    'Flow_Accumulation': 'Total Catchment Area',
    'Longitudinal_Curvature': 'Profile Curvature',
    'LS_Factor': 'LS Factor',
    'Relative_Slope_Position': 'Relative_Slope_Position',
    'Slope': 'Slope',
    'Topographic_Wetness_Index': 'TWI',
    'Valley_Depth': 'Valley Depth',
    'Vertical_Distance_to_Channel_Network': 'Channel Network Distance'}

    feature_to_abrev = {'Hillshading': 'Hill',
    'Aspect': 'Asp',
    'Channel Network Base Level': 'CNBL',
    'Channel Network Distance': 'CND',
    'Closed Depressions': 'CD',
    'Convergence Index': 'CI',
    'Elevation': 'Ele',
    'LS Factor': 'LSF',
    'Plan Curvature': 'PlCu',
    'Profile Curvature': 'PrCu',
    'Relative Slope Position': 'RSP',
    'Slope': 'Slo',
    'TWI': 'TWI',
    'Total Catchment Area': 'TCA',
    'Valley Depth': 'VD'}


    names = [feature_names[param] for param in terrain_params]
    abreviations = [feature_to_abrev[name] for name in names]


    return names, abreviations