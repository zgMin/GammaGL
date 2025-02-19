import json
import os
import os.path as osp
import pickle
from typing import Callable, List, Optional
import tensorlayerx as tlx
import numpy as np
import scipy.sparse as sp

from gammagl.data import InMemoryDataset, download_url, Graph


class Flickr(InMemoryDataset):
    r"""The Flickr dataset from the `"GraphSAINT: Graph Sampling Based
    Inductive Learning Method" <https://arxiv.org/abs/1907.04931>`_ paper,
    containing descriptions and common properties of images.

    Args:
        root (string): Root directory where the dataset should be saved.
        transform (callable, optional): A function/transform that takes in an
            :obj:`tlx_geometric.data.Data` object and returns a transformed
            version. The data object will be transformed before every access.
            (default: :obj:`None`)
        pre_transform (callable, optional): A function/transform that takes in
            an :obj:`tlx_geometric.data.Data` object and returns a
            transformed version. The data object will be transformed before
            being saved to disk. (default: :obj:`None`)

    Stats:
        .. list-table::
            :widths: 10 10 10 10
            :header-rows: 1

            * - #nodes
              - #edges
              - #features
              - #classes
            * - 89,250
              - 899,756
              - 500
              - 7
    """
    url = 'https://docs.google.com/uc?export=download&id={}&confirm=t'

    adj_full_id = '1crmsTbd1-2sEXsGwa2IKnIB7Zd3TmUsy'
    feats_id = '1join-XdvX3anJU_MLVtick7MgeAQiWIZ'
    class_map_id = '1uxIkbtg5drHTsKt-PAsZZ4_yJmgFmle9'
    role_id = '1htXCtuktuCW8TR8KiKfrFDAxUgekQoV7'

    def __init__(self, root: str, transform: Optional[Callable] = None,
                 pre_transform: Optional[Callable] = None):
        super().__init__(root, transform, pre_transform)
        with open(self.processed_paths[0], 'rb') as f:
            self.data, self.slices = pickle.load(f)

    @property
    def raw_file_names(self) -> List[str]:
        return ['adj_full.npz', 'feats.npy', 'class_map.json', 'role.json']

    @property
    def processed_file_names(self) -> str:
        return 'data.pt'

    def download(self):
        path = download_url(self.url.format(self.adj_full_id), self.raw_dir)
        os.rename(path, osp.join(self.raw_dir, 'adj_full.npz'))

        path = download_url(self.url.format(self.feats_id), self.raw_dir)
        os.rename(path, osp.join(self.raw_dir, 'feats.npy'))

        path = download_url(self.url.format(self.class_map_id), self.raw_dir)
        os.rename(path, osp.join(self.raw_dir, 'class_map.json'))

        path = download_url(self.url.format(self.role_id), self.raw_dir)
        os.rename(path, osp.join(self.raw_dir, 'role.json'))

    def process(self):
        f = np.load(osp.join(self.raw_dir, 'adj_full.npz'))
        adj = sp.csr_matrix((f['data'], f['indices'], f['indptr']), f['shape'])
        adj = adj.tocoo()
        row = adj.row
        col = adj.col
        edge_index = tlx.convert_to_tensor([row, col], dtype=tlx.int64)

        x = np.load(osp.join(self.raw_dir, 'feats.npy'))
        # x = tlx.convert_to_tensor(x, dtype=tlx.float32)
        x = normalize_feat(x)
        ys = [-1] * x.shape[0]
        with open(osp.join(self.raw_dir, 'class_map.json')) as f:
            class_map = json.load(f)
            for key, item in class_map.items():
                ys[int(key)] = item

        # y = np.array(ys, dtype=np.int32)
        # label = np.zeros((y.size, y.max() + 1), dtype=np.float32)
        # label[np.arange(y.size), y] = 1

        with open(osp.join(self.raw_dir, 'role.json')) as f:
            role = json.load(f)
        train_mask = np.zeros(x.shape[0], dtype=np.bool8)
        train_mask[role['tr']] = True
        val_mask = np.zeros(x.shape[0], dtype=np.bool8)
        val_mask[role['va']] = True
        test_mask = np.zeros(x.shape[0], dtype=np.bool8)
        test_mask[role['te']] = True


        data = Graph(x=x, edge_index=edge_index, y=ys)
        data.train_mask = train_mask
        data.val_mask = val_mask
        data.test_mask = test_mask
        data.num_classes = 7
        # get k layers feat


        data = data if self.pre_transform is None else self.pre_transform(data)

        calc_sign(adj, x, data)
        with open(self.processed_paths[0], 'wb') as f:
            pickle.dump(self.collate([data]), f)

def calc_sign(adj, feat, data):
    col = adj.col
    row = adj.row
    deg = np.array(adj.sum(1))
    deg_inv_sqrt = np.power(deg, -0.5).flatten()
    weight = np.ones_like(adj.col)
    new_weight = deg_inv_sqrt[row] * weight * deg_inv_sqrt[col]
    new_adj = sp.coo_matrix((new_weight, [col, row]))
    xs = [feat]
    K = 2
    # default K = 2, due to gammagl dont have pre_transform, so this place solid setting K = 2
    for i in range(1, K + 1):
        xs += [new_adj @ xs[-1]]
        data[f'x{i}'] = xs[-1]


def normalize_feat(feat):
    feat = feat - np.min(feat)
    feat = np.divide(feat, feat.sum(axis=-1, keepdims=True))
    return feat