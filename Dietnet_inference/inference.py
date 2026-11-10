import argparse
import time

import h5py
import numpy as np

import torch
from torch.utils.data import Dataset, DataLoader
import torch.nn as nn
import torch.nn.functional as F


class InferenceDataset(Dataset):
    """Dataset of samples and their genotypes for model inference.

    Number of SNPs, sample IDs and scaling factor are read from the
    HDF5 file at construction. Genotypes are read from disk one sample at a
    time in ``__getitem__``, and the file handle is opened on first access so
    the dataset is safe to use with multiple DataLoader workers.

    Args:
        inference_file (str): Path to the HDF5 file. Expected datasets:
            - ``snp_names``: SNP names, shape (nb_snps,).
            - ``samples``: Sample IDs as bytes, shape (n_samples,).
            - ``scale``: Scaling factor for non-missing genotypes, shape (1,).
            - ``inputs``: Genotypes, shape (n_samples, nb_snps).
        partition_idx (np.ndarray, optional): Indexes in HDF5 of fold test samples.
            If partition_idx is None all samples are used.
            Default: None.

    Attributes:
        h5_path (str): Path to the HDF5 file.
        partition_idx (np.ndarray, optional): Indexes in HDF5 of fold test samples. If None all samples are used.
        nb_snps (int): Number of SNPs.
        samples (list[str]): Decoded sample IDs.
        scale (float): Scaling factor for non-missing genotypes.
    
    Notes:
        For inference on 1KGP, a partition file is provided and only the test samples are used for inference.
        In this case, ``partition_idx`` is used to map the index to the corresponding HDF5 index.
        For independent inference sets (not 1KGP), all samples are used for inference and ``partition_idx`` is None. 
    
        The genotypes are loaded lazily in ``__getitem__`` to avoid loading the entire dataset into memory at once.
        The full genotype matrix does not fit in memory for large cohorts
    """
     
    def __init__(self, inference_file, partition_idx=None):
        self.h5_path = inference_file
        self.partition_idx = partition_idx

        # Load SNP names, sample IDs and scaling factor from the HDF5 file
        with h5py.File(inference_file, 'r') as f:
            self.nb_snps = f['snp_names'].shape[0]
            self.scale = f['scale'][0]

            # Not 1KGP : load all sample IDs
            if self.partition_idx is None:
                self.samples = [i.decode() for i in f['samples']]
            # 1KGP  : load only the test sample IDs using the partition indexes
            else:
                self.samples = [f['samples'][i].decode() for i in self.partition_idx]
            
        # To open lazily in _getitem_
        self.h5_file = None


    def open_file(self):
        """Open the HDF5 file on first call (once per DataLoader worker) and return the handle."""
        if self.h5_file is None:
            self.h5_file = h5py.File(self.h5_path, "r")
        
        return self.h5_file

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        """Load the genotypes of one sample from the HDF5 file.

        If ``partition_idx`` is not None (1KGP inference, where only the test samples of
        a fold are used), ``idx`` is first converted to the corresponding index
        in the HDF5 file.
        Otherwise (independent inference set), all samples are
        used and ``idx`` is the HDF5 index.

        Args:
            idx (int): Index of the sample in the dataset, between 0 and
                ``len(self) - 1``.

        Returns:
            torch.Tensor: Genotypes of the sample (0,1,2), shape (nb_snps,),
                dtype ``torch.int8``. Missing genotypes are encoded as -1.
        """
        # Opening the HDF5 file lazily and avoid issues with multiple DataLoader workers
        f = self.open_file()

        # Map the dataset index to the HDF5 index (see docstring)
        if self.partition_idx is not None:
            real_idx = self.partition_idx[idx]
        else:
            real_idx = idx

        # Load genotypes for the sample
        x = torch.from_numpy(
            f["inputs"][real_idx].astype(np.int8, copy=False)
        )
        
        return x

class AuxiliaryNetwork(nn.Module):
    def __init__(self, n_feats_emb):
        super(AuxiliaryNetwork, self).__init__()
        
        layers = []
        
        # First layer
        layers.append(nn.Linear(n_feats_emb, 100, bias=False))
        
        # Hidden layer
        layers.append(nn.Linear(100, 100, bias=False))
        
        self.layers = nn.ModuleList(layers)


    def forward(self, x):
        for i,layer in enumerate(self.layers):
            # Forward pass
            ze = layer(x)
            ae = torch.tanh(ze)
            x = ae

        return ae

class MainNetwork(nn.Module):

    def __init__(self, n_feats, n_targets):
        super(MainNetwork, self).__init__()

        # --- Layers and batchnorm ---
        # Main net is n_feats (SNPs) -> 100 -> 100 -> n_targets (populations)
        layers = []
        batch_norms = []
        
        # Fat layer
        layers.append(nn.Linear(n_feats,100))
        batch_norms.append(nn.BatchNorm1d(num_features=100))
        
        # Hidden layer
        layers.append(nn.Linear(100,100))
        batch_norms.append(nn.BatchNorm1d(num_features=100))
        
        # Last layer
        layers.append(nn.Linear(100,n_targets))

        self.layers = nn.ModuleList(layers)
        self.bn = nn.ModuleList(batch_norms)


    def forward(self, x):
        # Hidden layers
        next_input = x
        for i,(layer, bn) in enumerate(zip(self.layers, self.bn)):
            # Forward pass
            z = layer(next_input)
            a = torch.relu(z)
            a = bn(a)
            next_input = a
            
            # Last layer
            out = self.layers[-1](next_input)

        return next_input, out


def main():
    NB_POP=24
    
    # Start time
    stime = time.time()
    
    # Parse line command arguments
    args = parse_args()

    print('Cuda available:', torch.cuda.is_available())
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print('Device:', device)


    #-------------
    # Dataset
    #-------------
    # Inference set (pytorch Dataset)
    # Inference in 1KGP: partition file is provided and only the test samples are used for inference
    if args.partition is not None:
        partition = np.load(args.partition, allow_pickle=True)
        which_fold = args.fold
        if which_fold < 0:
            raise ValueError('Expected a fold number when inferring on 1KGP. Got the default {} value'.format(which_fold))
        
        test_idx = partition['folds_indexes'][which_fold][2] # 2 = test samples
        
        inference_set = InferenceDataset(args.test_h5, partition_idx=test_idx)

    # Inference in independent dataset (not 1KGP): all samples are used for inference
    else:
        inference_set = InferenceDataset(args.test_h5)

    print('Inference set: {} genotypes and {} samples'.format(
        inference_set.nb_snps, len(inference_set.samples)
    ))

    # Pytorch Dataloader
    inference_loader = DataLoader(inference_set, batch_size=args.batch_size, shuffle=False)

    #-------------
    # Model
    #-------------
    # SNPs embedding : used by aux net to compute fat layer parameters
    emb = torch.from_numpy(np.load(args.snps_emb)['emb']).to(device).float()
    emb_norm = (emb ** 2).sum(0) ** 0.5 # Normalize embedding
    emb = emb/emb_norm
    
    # Aux net : Used once to compute the fat layer parameters
    aux_net = AuxiliaryNetwork(emb.shape[1])
    
    # Main net : Used to do the inference
    main_net = MainNetwork(n_feats=inference_set.nb_snps, n_targets=NB_POP)

    # Load the dietnetwork parameters
    checkpoint = torch.load(args.model_param, map_location=device, weights_only=False)
    state_dict = checkpoint['model_state_dict']
    
    aux_state_dict = make_statedict_aux_network(state_dict)
    aux_net.load_state_dict(aux_state_dict)
    aux_net.to(device)
    
    # Get the fat layer parameters from the aux net
    fatlayer_weights = torch.transpose(aux_net(emb),1,0)
    
    # Main net state dict
    main_state_dict = make_statedict_main_network(state_dict, fatlayer_weights)
    main_net.load_state_dict(main_state_dict)
    main_net.to(device)
    
    # Data for normalization of genotypes
    norm_stats = np.load(args.norm_stats)
    mus = torch.from_numpy(norm_stats['mean']).float().to(device)
    sigmas = torch.from_numpy(norm_stats['std']).float().to(device)
    
    #-------------
    # Inference
    #-------------
    results = {}
    results['preds'] = np.ones(len(inference_set))*-1
    results['scores'] = np.ones((len(inference_set), NB_POP))*-1
    results['last_hidden_layer'] = np.ones((len(inference_set), 100))*-1
    
    # Main net forward pass
    main_net.eval()
    batch_start=0
    for i,batch in enumerate(inference_loader):
        batch_end = batch_start + batch.shape[0]
        
        batch = batch.to(device).float()
        
        # Replace missing values with mean
        mask = (batch >= 0)
        for i in range(batch.shape[0]):
            batch[i] =  mask[i]*batch[i] + (~mask[i])*mus

        # Normalize (missing values become 0)
        batch = (batch - mus) / sigmas

        # Scale non-missing values
        batch = batch * inference_set.scale

        # Forward pass
        last_hidden_layer, out = main_net(batch)

        # Compile results
        with torch.no_grad():
            # Scores : 1 value per class, 24 values for each sample
            # (softmax = all values for a sample sum to 1)
            scores = F.softmax(out, dim=1).detach().cpu().numpy()
            results['scores'][batch_start:batch_end] = scores
            
            # Pred : 1 prediction for each sample
            preds = np.argmax(scores, axis=1)
            results['preds'][batch_start:batch_end] = preds
            
            # Last hidden layer : 100 values for each sample
            results['last_hidden_layer'][batch_start:batch_end] = last_hidden_layer.detach().cpu().numpy()
            
            # Update batch start index for next batch
            batch_start = batch_end

    # Write results to npz file
    np.savez(args.out,
             samples=inference_set.samples,
             preds=results['preds'],
             scores=results['scores'],
             last_hidden_layer=results['last_hidden_layer'])
    print('Inference results saved to {}'.format(args.out))


def make_statedict_aux_network(state_dict):
    new_state = {}

    for k, v in state_dict.items():
        if k.startswith("aux_net.hidden_layers"):
            new_key = k.replace("aux_net.hidden_", "")
            new_state[new_key] = v
    
    return new_state


def make_statedict_main_network(state_dict, fatlayer_weights):
    new_state = {}
    
    new_state["layers.0.weight"] = fatlayer_weights

    for k, v in state_dict.items():

        # ---- Fat layer ----
        if k == "main_net.fat_bias":
            new_state["layers.0.bias"] = v

        elif k.startswith("main_net.bn_fatLayer"):
            new_key = k.replace("main_net.bn_fatLayer", "bn.0")
            new_state[new_key] = v

        # ---- Hidden layer ----
        elif k.startswith("main_net.hidden_layers.0"):
            new_key = k.replace("main_net.hidden_layers.0", "layers.1")
            new_state[new_key] = v

        elif k.startswith("main_net.bn.0"):
            # this was hidden layer BN
            new_key = k.replace("main_net.bn.0", "bn.1")
            new_state[new_key] = v

        # ---- Output layer ----
        elif k.startswith("main_net.out"):
            new_key = k.replace("main_net.out", "layers.2")
            new_state[new_key] = v
    
    return new_state


def parse_args():
    parser = argparse.ArgumentParser(
            description='Test a trained model in another dataset'
            )

    parser.add_argument(
            '--partition',
            type=str,
            default=None,
            help='Numpy file of partition of 1KGP samples (use only when inferring on 1KGP). Default: %(default)s'
            )

    parser.add_argument(
            '--fold',
            type=int,
            default=-1,
            help='Fold number (use only when inferring on 1KGP). Default: %(default)s'
            )
    
    parser.add_argument(
            '--test-h5',
            type=str,
            required=True,
            help='Hdf5 file of inference set samples and their genotypes. Provide full path'
            )
    
    parser.add_argument(
            '--batch-size',
            type=int,
            default=128,
            help='Batch size for inference. Default: %(default)i'
            )
    
    parser.add_argument(
            '--model-param',
            type=str,
            required=True,
            help='Pt file of params of the trained model.'
            )
    
    parser.add_argument(
            '--snps-emb',
            type=str,
            required=True,
            help='SNPs embedding. Provide full path'
            )
    
    parser.add_argument(
            '--norm-stats',
            type=str,
            required=True,
            help=('Statistics used for normalization.'
                  'Provide full path')
            )
    
    parser.add_argument(
            '--out',
            type=str,
            required=True,
            help='Output filename of test results. Provide full path'
            )

    return parser.parse_args()


if __name__ == '__main__':
    main()