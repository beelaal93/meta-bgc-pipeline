# Conda Environments Required

The following Conda environments are needed for this pipeline.  
They are **not included** in this repository due to size, but you can recreate them using the provided YAML files (if available) or manually.

List of environments:
- BiG-SCAPE
- antismash_env
- assembly_env
- benchmark_env
- bigscape_env
- bigscape_py311
- binning_env
- checkm2_env
- deepbgc_env
- dfast_qc_db_env
- fetch_env
- kingfisher_env
- qc_env
- streamlit_env
- viz_env

To export an environment: `conda env export -n <name> > <name>.yaml`  
To create from YAML: `conda env create -f <name>.yaml`
