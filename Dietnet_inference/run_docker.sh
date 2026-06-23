## How to run with docker

docker build -t dietnet-infer -f Dockerfile .

docker run --rm --gpus all \
  -v /path/to/Dietnet_inference/additional-files:/data/dietnet_files \
  -v /path/to/Dietnet_inference/models:/data/models \
  -v /path/to/Dietnet_inference/samples:/data/plink:ro \
  -v /path/to/dietnet_results:/out \
  -w /out \
  dietnet-infer


## How to run with singularity

apptainer build dietnet_inference.sif dietnet_inference.def

salloc --time=0:30:0 --mem-per-cpu=48G --ntasks=1 --account=<account_name>

singularity run \
  --bind /path/to/additional-files:/data/dietnet_files \
  --bind /path/to/models:/data/models \
  --bind /path/to/samples:/data/plink:ro \
  --bind /path/to/dietnet_results:/out \
  --pwd /out \
  /path/to/dietnet_inference.sif