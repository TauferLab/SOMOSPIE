log="make.log"
.PHONY: all list tellico bash

all:
	@echo "## make all ##" | tee -a $(log)
	@echo "Type 'make list' for available make targets." | tee -a $(log)

jetstream:
	@echo "## make jetstream ##" | tee -a $(log)
	@echo "Installing all necessary software for SOMOSPIE on your Jetstream vm." | tee -a $(log)
	@echo "This assumes you have run ezj at some point and conda is currently activated or in your path." | tee -a $(log)
	@echo "This may take an hour." | tee -a $(log)
	cd install; ./install.sh
    
tellico:
	@echo "## make tellico ##" | tee -a $(log)
	@echo "Apologies, but tellico support is still under development." | tee -a $(log)

bash:
	@echo "## make bash ##" | tee -a $(log)
	@echo "Setting up Spark, Java, and Conda in ~/.bashrc." | tee -a $(log)
	echo 'export SPARK_HOME=/usr/local/spark' >> ~/.bashrc
	echo 'export JAVA_HOME=/usr/local/java' >> ~/.bashrc
	echo 'export CONDA_HOME=/opt/anaconda3' >> ~/.bashrc
	echo 'export PATH=$$JAVA_HOME/bin:$$SPARK_HOME/bin:$$CONDA_HOME/bin:$$PATH' >> ~/.bashrc
	echo 'export SPARK_LOCAL_IP="127.0.0.1"' >> ~/.bashrc
	@echo "Be sure to 'source ~/.bashrc'." | tee -a $(log)

eco: 
	@echo "## make eco ##" | tee -a $(log)
	@echo "Fetching ecoregion data for Src_SOMOSPIE/data/" | tee -a $(log)
	cd data; ./fetch_ecoregions.sh

submodules:
	@echo "## make submodules ##" | tee -a $(log)
	@echo "Loading and updating all git submodules for Src_SOMOSPIE" | tee -a $(log)
	git submodule update --init --recursive
	touch SOMOSPIE/modules/ipywe/ipywe/__init__.py

list:
	@$(MAKE) -pRrq -f $(lastword $(MAKEFILE_LIST)) : 2>/dev/null | awk -v RS= -F: '/^# File/,/^# Finished Make data base/ {if ($$1 !~ "^[#.]") {print $$1}}' | sort | egrep -v -e '^[^[:alnum:]]' -e '^$@$$'
