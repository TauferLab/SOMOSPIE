#!/bin/sh

for i in {2010..2010}; do
    for j in {01..12}; do
	python3 ./parallel_hyppo.py\
	 -t /work/spac/rllamas/SOMOSPIE_regions_of_interest_prediction_1km/Monthly_train_csv/Midwest/midwest_region_train_monthly_1km_${i}_${j}.csv\
	 -e /work/spac/rllamas/SOMOSPIE_regions_of_interest_prediction_1km/Eval_csv_files/Midwest/midwest_region_evaluation_1km.csv\
	 -o /work/spac/rllamas/SOMOSPIE_regions_of_interest_prediction_1km/3_Surrogate_Based_Model/Midwest/Monthly_prediction_outputs/midwest_region_sbm_output_monthly_1km_K28_D2_${i}_${j}.csv\
	 -l /work/spac/rllamas/SOMOSPIE_regions_of_interest_prediction_1km/3_Surrogate_Based_Model/Midwest/Monthly_log_reports/midwest_region_sbm_output_monthly_1km_K28_D2_log_report_${i}_${j}.csv\
	 -m "SBM"\
	 -k 28\
	 -D 2
    done
done
