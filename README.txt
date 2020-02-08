Setup instruction for the Jupyter Notebook file that runs 
 SOMOSPIE: SOil MOisture SPatial Inference Engine

Any command you are to run from the command-line are indicated in this document by $.
Open your terminal or other CLI, and clone this repository:
$ git clone --recursive https://github.com/TauferLab/SOMOSPIE 

Move into your new repository:
$ cd Src_SOMOSPIE

The `--recursive` tag above also downloaded any required submodules. If you left off that tag, you can use our makefile to do that now:
$ make submodules

To continue setup, we need to activate the anaconda evironment that will be used for SOMOSPIE.ipynb. On Jetstream, use the built-in "ez" method:
$ ezj

Once you see URL for accessing Jupyter Notebook, return to the command-line: force exit by pressing Ctrl+C twice. 

YOU SHOULD BE RUNNING THIS ON THE FOLLOWING JETSTREAM VM IMAGE: Ubuntu 18.04 for SOMOSPIE
If you are, the final setup step is simple:
$ make bash
If you are not, you can install everything yourself, but this takes over an hour:
$ make jetstream

You are now ready to start using SOMOSPIE! Launch Jupyter Notebooks with `ezj -q`, click the link provided, and open `SOMOSPIE.ipynb`.

