# SOMOSPIE workflow

SOMOSPIE.ipynb

    The wrapper for the full SOMOSPIE workflow

    Run via Jupyter Notebook

For testing and development, this has been split into:

    SOMOSPIE_input.ini
    SOMOSPIE_input_parser.py
    curate.py
    model.py
    analyze.py
    visualize.py
    utils.py
    SOMOSPIE_wrapper.py

Mid May 2019:

    Modify arguments in SOMOSPIE_input.py 
    Then execute ./SOMOSPIE_wrapper.py from the commandline

Late May 2019:

    Modify arguments in SOMOSPIE_input.ini
    Then execute from the commandline: ./SOMOSPIE_wrapper.py, which uses ./SOMOSPIE_input_parser.py
        or
    Create new argument file file_name.ini
    Then execute from the commanline: ./SOMOSPIE_wrapper.py file_name.ini

Late October 2019:

    Begin development of new SOMOSPIE.ipynb in repository's main directory
     as wrapper for both data acquisition and SOMOSPIE execution.

Late 2019 -- January 2020:

    Major development of widgets and data acquisition procedures.

Late 2021 -- January 2022:

    Major development in structure of the workflow
