#!/usr/bin/env python3

# This script assumes that the non-numerical column headers
# in train and predi files are identical.
# Thus the sm header(s) in the train file must be numeric (day/month/year).

import sys
import numpy as np
import pandas as pd
from sklearn.decomposition import PCA #TruncatedSVD as SVD
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline


def mask(df, f):
    return df[f(df)]


def is_int(val):
    try:
        int(val)
        return True
    except:
        return False


def remove_sparse_rows(data, error=-99999.0):
    data_matrix = data.as_matrix()
    data_matrix = [row for row in data_matrix if error in row]
    return pd.DataFrame(data_matrix, columns=data.columns)

def fit_data(train_data, num_comps="mle"):
    # Build pipeline and fit it to training data.
    scaler = StandardScaler()
    # https://github.com/scikit-learn/scikit-learn/issues/9884
    pca = PCA(n_components=num_comps, svd_solver="full")
    pipeline = Pipeline([("scaler", scaler), ("pca", pca)])
    pipeline.fit(train_data)
    return pipeline


#Select the target number of components.
# Uses Avereage Eigenvalue technique from:
# http://pubs.acs.org/doi/pdf/10.1021/ie990110i
def choose_num_comps(train_data, bound=1):
    model = fit_data(train_data)
    eigenvals = model.named_steps['pca'].explained_variance_
    #print(f"eigenvals:\n{eigenvals}\n")
    return len([ev for ev in eigenvals if (ev >= bound)])


# Assumes the first two columns are x/y-coordinates
# and integer-headed columns are sm data, not covariates. 
def get_params(data):
    columns = list(data.columns)[2:]
    return [col for col in columns if not is_int(col)]

# Apply to {df} pca transformatio {model} 
# that maps {params}-headed data to {num_comps} new columns.
def apply_model(df, model, params, num_comps):
    pre_model = df[params]
    post_model = model.transform(pre_model)
    #print(f"one row of post_model:\n{post_model[0]}")
    new_cols = [f"Component{i}" for i in range(num_comps)]
    post_model = pd.DataFrame(post_model, columns=new_cols)
    #print(f"one row of post_model:\n{post_model.iloc[0]}")
    pre_base = df.drop(params, axis=1)
    #print(f"one row of pre_base:\n{pre_base.iloc[0]}")
    post_model.reset_index(drop=True, inplace=True)
    pre_base.reset_index(drop=True, inplace=True)
    post_full = pd.concat([pre_base, post_model], axis=1)
    #print(f"one row of post_fill:\n{post_full.iloc[0]}")
    #print(f"sizes:\npost_model: {post_model.shape}\npre_base: {pre_base.shape}\npost_full: {post_full.shape}\n")
    return post_full


def joint_pca(train_data, predi_data, params):

    # Run PCA on train_data to create a dimension-reduction model.
    pca_train = train_data[params]
    num_comps = choose_num_comps(pca_train)
    #print(f"num_comps:\n{num_comps}\n")
    model = fit_data(pca_train, num_comps)
    #print(f"model:\n{model}\n")
    
    #print(f"one row of train_data before:\n{train_data.iloc[1]}")
    #print(f"one row of predi_data before:\n{predi_data.iloc[1]}")

    # Apply the same model to both train and predi data.
    train_data = apply_model(train_data, model, params, num_comps)
    predi_data = apply_model(predi_data, model, params, num_comps)

    #print(f"one row of train_data after:\n{train_data.iloc[1]}")
    #print(f"one row of predi_data after:\n{predi_data.iloc[1]}")

    components = model.named_steps["pca"].components_

    return train_data, predi_data, components


if __name__ == "__main__":
    train_in = sys.argv[1]
    predi_in = sys.argv[2]
    train_out = sys.argv[3]
    predi_out = sys.argv[4]
    log_file = sys.argv[5]

    # Read in data files.
    train_data = pd.read_csv(train_in, header=0)
    predi_data = pd.read_csv(predi_in, header=0)

    # Find param names.
    params = get_params(train_data)

    # Do that pca stuff.
    train_pca, predi_pca, components = joint_pca(train_data, predi_data, params)

    # Write the results to specified files.
    train_pca.to_csv(path_or_buf=train_out, index=False)
    predi_pca.to_csv(path_or_buf=predi_out, index=False)

    # Log the pca components.
    with open(log_file, "a") as log:
        log.write("Component Eigenvalues:\n")
        for i in range(len(params)):
            log.write(f"{params[i]}:\n{[c[i] for c in components]}\n")


