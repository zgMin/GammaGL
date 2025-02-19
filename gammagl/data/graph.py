import warnings
import copy
import numpy as np
import tensorlayerx as tlx
from gammagl.sparse.sparse_adj import CSRAdj
from collections.abc import Mapping, Sequence
from typing import (Any, Callable, Dict, Iterable, List, NamedTuple, Optional,
                    Tuple, Union)
from gammagl.data.storage import (BaseStorage, EdgeStorage,
                                          GlobalStorage, NodeStorage)
from gammagl.utils.loop import add_self_loops
from gammagl.utils.check import check_is_numpy
from gammagl.typing import NodeType, EdgeType
from gammagl.utils.num_nodes import maybe_num_nodes


class BaseGraph:
    r"""
    base graph object that inherited by Graph and heteroGraph
    """
    # solve the problem of pickle Graph
    # https://stackoverflow.com/questions/50156118/recursionerror-maximum-recursion-depth-exceeded-while-calling-a-python-object-w
    def __getstate__(self) -> Dict[str, Any]:
        return self.__dict__

    def __setstate__(self, mapping: Dict[str, Any]):
        for key, value in mapping.items():
            self.__dict__[key] = value
            
    def __inc__(self, key: str, value: Any, *args, **kwargs) -> Any:
        r"""Returns the incremental count to cumulatively increase the value
        :obj:`value` of the attribute :obj:`key` when creating mini-batches
        using :class:`torch_geometric.loader.DataLoader`.
        .. note::
            This method is for internal use only, and should only be overridden
            in case the mini-batch creation process is corrupted for a specific
            attribute.
        """
        raise NotImplementedError


class Graph(BaseGraph):
    r""" 
    A Graph object describe a homogeneous graph. The graph object 
    will hold node-level, link-level and graph-level attributes. In 
    general, :class:`~gammagl.data.Data` tries to mimic the behaviour 
    of a regular Python dictionary. In addition, it provides useful 
    functionality for analyzing graph structures, and provides basic 
    tensor functionalities.

    .. code-block:: python

        >>> from gammagl.data import Graph
        >>> import numpy
        >>> g = graph.Graph(x=numpy.random.randn(5, 16), edge_index=[[0, 0, 0], [1, 2, 3]], num_nodes=5,)
        >>> print(g)
        GNN Graph instance.
        number of nodes: 5
        number of edges: 2

        >>> print(g.indegree.numpy(), g.outdegree.numpy())
        [0. 1. 1. 1. 0.] [3. 0. 0. 0. 0.]
    
    Args:
        x (Tensor): Node feature matrix with shape :obj:`[num_nodes, num_node_features]`. (default: :obj:`None`)
        edge_index (LongTensor): Graph connectivity in COO format with shape :obj:`[2, num_edges]`.
            (default: :obj:`None`)
        edge_feat (Tensor): Edge feature matrix with shape
            :obj:`[num_edges, num_edge_features]`. (default: :obj:`None`)
        num_nodes (int): The specified number of nodes. (default: :obj:`None`)
        y (Tensor): Graph-level or node-level ground-truth labels with arbitrary shape. (default: :obj:`None`)
        spr_format (List(str)): Specify the other sparse storage format, like `csc` and `csr`. (default: :obj:`None`)
    """

    def __init__(self, x=None, edge_index=None, edge_feat=None, num_nodes=None, y=None, spr_format=None, is_tensor=None, **kwargs):
        self.__dict__['_store'] = GlobalStorage(_parent=self)
        self._is_tensor = is_tensor
        if edge_index is not None:
            self.edge_index = edge_index

        # if num_nodes is None:
        #     warnings.warn("_maybe_num_node() is used to determine the number of nodes."
        #               "This may underestimate the count if there are isolated nodes.")
        #     self._num_nodes = self._maybe_num_node(edge_index)
        # else:
        #     self._num_nodes = num_nodes
        #     max_node_id = self._maybe_num_node(edge_index) - 1 # max_node_id = num_nodes - 1
        #     if self._num_nodes <= max_node_id:
        #         raise ValueError("num_nodes=[{}] should be bigger than max node ID in edge_index.".format(self._num_nodes))
        
        if edge_feat is not None:
            self.edge_feat = edge_feat
        if x is not None:
            self.x = x
        if y is not None:
            self.y = y
        if spr_format is not None:
            if 'csr' in spr_format:
                self._csr_adj = CSRAdj.from_edges(self._edge_index[0], self._edge_index[1], self._num_nodes)
            if 'csc' in spr_format:
                self._csc_adj = CSRAdj.from_edges(self._edge_index[1], self._edge_index[0], self._num_nodes)
        self.num_nodes = num_nodes
        for key, value in kwargs.items():
            setattr(self, key, value)
            
    def __getitem__(self, key: str) -> Any:
        return self._store[key]

    def __setitem__(self, key: str, value: Any):
        self._store[key] = value

    def __getattr__(self, key: str) -> Any:
        # Called when the default attribute access fails, which means getattr
        return getattr(self._store, key)

    def __setattr__(self, key: str, value: Any):
        setattr(self._store, key, value)

    # def __repr__(self) -> str:
    #     cls = self.__class__.__name__
    #     has_dict = any([isinstance(v, Mapping) for v in self._store.values()])
    #
    #     if not has_dict:
    #         info = [size_repr(k, v) for k, v in self._store.items()]
    #         info = ', '.join(info)
    #         return f'{cls}({info})'
    #     else:
    #         info = [size_repr(k, v, indent=2) for k, v in self._store.items()]
    #         info = ',\n'.join(info)
    #         return f'{cls}(\n{info}\n)'
        
    def __cat_dim__(self, key: str, value: Any, *args, **kwargs) -> Any:
        # if isinstance(value, SparseTensor) and 'adj' in key:
        #     return (0, 1)
        if 'index' in key or 'face' in key:
            return -1
        else:
            return 0
    
    def __inc__(self, key: str, value: Any, *args, **kwargs) -> Any:
        if 'batch' in key:
            return int(value.max()) + 1
        elif 'index' in key or key == 'face':
            return self.num_nodes
        else:
            return 0
        
    @property
    def stores(self) -> List[BaseStorage]:
        return [self._store]
    
    @property
    def node_stores(self) -> List[NodeStorage]:
        return [self._store]

    @property
    def edge_stores(self) -> List[EdgeStorage]:
        return [self._store]
    
    def stores_as(self, data: 'Data'):
        return self

    @property
    def num_nodes(self):
        r"""
        Return the number of nodes.
        """
        # try:
        #     return sum([v.num_nodes for v in self.node_stores])
        # except TypeError:
        #     return None
        return self.x.shape[0]

    @property
    def num_edges(self):
        r"""
        Return the number of edges.
        """
        return self.edge_index.shape[-1]

    @property
    def x(self) -> Any:
        return self['x'] if 'x' in self._store else None

    @property
    def edge_index(self) -> Any:
        return self['edge_index'] if 'edge_index' in self._store else None

    @property
    def edge_weight(self) -> Any:
        return self['edge_weight'] if 'edge_weight' in self._store else None

    @property
    def edge_attr(self) -> Any:
        return self['edge_attr'] if 'edge_attr' in self._store else None

    @property
    def y(self) -> Any:
        return self['y'] if 'y' in self._store else None

    @property
    def indegree(self):
        r"""
        Graph property, return the node in-degree of the graph.
        """
        if self._csc_adj is not None:
            return self.csc_adj.degree
        return tlx.unsorted_segment_sum(tlx.ones(self.edge_index.shape[1]), self.edge_index[1], self.num_nodes)

    @property
    def outdegree(self):
        r"""
        Graph property, return the node out-degree of the graph.
        """
        if self._csr_adj is not None:
            return self._csr_adj.degree
        return tlx.unsorted_segment_sum(tlx.ones(self.edge_index.shape[1]), self.edge_index[0], self.num_nodes)

    @property
    def csc_adj(self):
        if self._csc_adj is not None:
            self._csc_adj = CSRAdj.from_edges(self._edge_index[1], self._edge_index[0], self._num_nodes)
        return self._csc_adj
    
    @property
    def csr_adj(self):
        if self._csr_adj is not None:
            self._csr_adj = CSRAdj.from_edges(self._edge_index[0], self._edge_index[1], self._num_nodes)
        return self._csr_adj

    @property
    def num_node_features(self) -> int:
        r"""Returns the number of features per node in the graph."""
        return self._store.num_node_features
    
    # def add_self_loop(self, n_loops=1):
    #     """
    #     Args:
    #         n_loops: number of self loops.
    #
    #     """
    #     self_loop_index = np.stack([np.arange(self.num_nodes), np.arange(self.num_nodes)])
    #     self._edge_index = np.concatenate([self._edge_index, self_loop_index], axis=1)

    # def node_mask(self):
    #     # return a subgraph based on index. (?)
    #     pass

    # def edge_mask(self):
    #     # return a subgraph based on index. (?)
    #     pass
    
    # def to_undirected(self):
    #     # convert the graph to an undirected graph.
    #     pass

    # def to_directed(self):
    #     # convert the graph to an directed graph.
    #     pass

    def add_self_loop(self, n_loops=1):
        """
        Args:
            n_loops (int):

        Returns:
            edge_index (Tensor) : original edges with self loop edges
            edge_feat (FloatTensor) : attributes of edges
        """
        return add_self_loops(self.edge_index, n_loops, self.edge_feat, num_nodes=self.num_nodes)

    def sorted_edges(self, sort_by="src"):
        """Return sorted edges with different strategies.
        This function will return sorted edges with different strategy.
        If :code:`sort_by="src"`, then edges will be sorted by :code:`src`
        nodes and otherwise :code:`dst`.
        Args:
            sort_by: The type for sorted edges. ("src" or "dst")
        Return:
            A tuple of (sorted_src, sorted_dst, sorted_eid).
        """
        if sort_by not in ["src", "dst"]:
            raise ValueError("sort_by should be in 'src' or 'dst'.")
        if sort_by == 'src':
            src, dst, eid = self._csr_adj.triples()
        else:
            dst, src, eid = self._csc_adj.triples()
        return src, dst, eid
    
    def generate_onehot_node_feat(self):
        self._node_feat = np.eye(self.num_nodes, dtype=np.float32)
   
    # def __repr__(self):
    #     description = "GNN {} instance.\n".format(self.__class__.__name__)
    #     description += "number of nodes: {}\n".format(self.num_nodes)
    #     description += "number of edges: {}\n".format(self.num_edges)
    #     return description

    # @classmethod
    def clone(self):
        r"""
        return a copy of the graph. This function will create a new instance 
        that incoperate the same infomation of input graph.
        """
        return Graph(edge_index=copy.deepcopy(self.edge_index), 
                     edge_feat=copy.deepcopy(self.edge_feat), 
                     num_nodes=copy.deepcopy(self.num_nodes), 
                     node_feat=copy.deepcopy(self.node_feat), 
                     node_label=copy.deepcopy(self.node_label))

    def _apply_to_tensor(self, key, value, inplace=True):
        if value is None:
            return value
    
        if key == '_is_tensor':
            # set is_tensor to True
            return True
    
        if isinstance(value, CSRAdj):
            value = value.tensor(inplace=inplace)
    
        elif isinstance(value, dict):
            if inplace:
                for k, v in value.items():
                    value[k] = tlx.ops.convert_to_tensor(v)
            else:
                new_value = {}
                for k, v in value.items():
                    new_value[k] = tlx.ops.convert_to_tensor(v)
                value = new_value
        else:
            if tlx.ops.is_tensor(value):
                pass
            elif check_is_numpy(value):
                if key in ['edge_index', 'y', 'edge_type', 'train_idx', 'test_idx', 'train_y']:
                    value = tlx.ops.convert_to_tensor(value, dtype=tlx.int64)
                elif key in ['train_mask', 'val_mask', 'test_mask', ]:
                    value = tlx.ops.convert_to_tensor(value, dtype=tlx.bool)
                else:
                    value = tlx.ops.convert_to_tensor(value, dtype=tlx.float32)
        return value
    
    def tensor(self, inplace=True):
        """Convert the Graph into paddle.Tensor format.
        In paddle.Tensor format, the graph edges and node features are in paddle.Tensor format.
        You can use send and recv in paddle.Tensor graph.

        Args:
            inplace: (Default True) Whether to convert the graph into tensor inplace.

        """
    
        if self._is_tensor is True:
            return self
    
        if inplace:
            for key in self._store:
                self._store[key] = self._apply_to_tensor(
                    key, self._store[key], inplace)
            self._is_tensor = True
            return self
        else:
            new_dict = {}
            for key in self.__dict__:
                new_dict[key] = self._apply_to_tensor(key, self.__dict__[key],
                                                      inplace)
        
            graph = self.__class__(
                num_nodes=new_dict["_num_nodes"],
                edges=new_dict["_edges"],
                node_feat=new_dict["_node_feat"],
                edge_feat=new_dict["_edge_feat"],
                adj_src_index=new_dict["_adj_src_index"],
                adj_dst_index=new_dict["_adj_dst_index"],
                **new_dict)
            return graph

    def _apply_to_numpy(self, key, value, inplace=True):
        if value is None:
            return value
    
        if key == '_is_tensor':
            # set is_tensor to True
            return False
    
        if isinstance(value, CSRAdj):
            value = value.numpy(inplace=inplace)
        elif isinstance(value, dict):
            if inplace:
                for k, v in value.items():
                    value[k] = v.numpy()
            else:
                new_value = {}
                for k, v in value.items():
                    new_value[k] = v.numpy()
                value = new_value
        else:
            if check_is_numpy(value):
                pass
            elif tlx.ops.is_tensor(value):
                # can't assign type of numpy
                value = tlx.ops.convert_to_numpy(value)
        return value

    def numpy(self, inplace=True):
        """Convert the Graph into numpy format.
        In numpy format, the graph edges and node features are in numpy.ndarray format.
        But you can't use send and recv in numpy graph.

        Args:
            inplace: (Default True) Whether to convert the graph into numpy inplace.

        """
        if self._is_tensor is False:
            return self
        
        if inplace:

            for key in self._store:
                self._store[key] = self._apply_to_numpy(
                    key, self._store[key], inplace)
            self._is_tensor = False
            return self
        else:
            new_dict = {}
            for key in self.__dict__:
                new_dict[key] = self._apply_to_numpy(key, self.__dict__[key],
                                                     inplace)
        
            graph = self.__class__(
                num_nodes=new_dict["_num_nodes"],
                edges=new_dict["_edges"],
                node_feat=new_dict["_node_feat"],
                edge_feat=new_dict["_edge_feat"],
                adj_src_index=new_dict["_adj_src_index"],
                adj_dst_index=new_dict["_adj_dst_index"],
                **new_dict)
            return graph


    def dump(self, path):
        r"""
        Dump the graph into a directory.

        This function will dump the graph information into the given directory path. 
        The graph can be read back with :code:`pgl.Graph.load`

        Args:
            path: The directory for the storage of the graph.
        """        
        pass

        # if self._is_tensor:
        #     # Convert back into numpy and dump.
        #     graph = self.numpy(inplace=False)
        #     graph.dump(path)
        # else:
        #     if not os.path.exists(path):
        #         os.makedirs(path)

        #     np.save(os.path.join(path, 'num_nodes.npy'), self._num_nodes)
        #     np.save(os.path.join(path, 'edges.npy'), self._edges)
        #     np.save(os.path.join(path, 'num_graph.npy'), self._num_graph)

        #     if self._adj_src_index is not None:
        #         self._adj_src_index.dump(os.path.join(path, 'adj_src'))

        #     if self._adj_dst_index is not None:
        #         self._adj_dst_index.dump(os.path.join(path, 'adj_dst'))

        #     if self._graph_node_index is not None:
        #         np.save(
        #             os.path.join(path, 'graph_node_index.npy'),
        #             self._graph_node_index)

        #     if self._graph_edge_index is not None:
        #         np.save(
        #             os.path.join(path, 'graph_edge_index.npy'),
        #             self._graph_edge_index)

        #     def _dump_feat(feat_path, feat):
        #         """Dump all features to .npy file.
        #         """
        #         if len(feat) == 0:
        #             return

        #         if not os.path.exists(feat_path):
        #             os.makedirs(feat_path)

        #         for key in feat:
        #             value = feat[key]
        #             np.save(os.path.join(feat_path, key + ".npy"), value)

        #     _dump_feat(os.path.join(path, "node_feat"), self.node_feat)
        #     _dump_feat(os.path.join(path, "edge_feat"), self.edge_feat)

    @classmethod
    def load(cls, path, mmap_mode="r"):
        """Load Graph from path and return a Graph in numpy. 

        Args:

            path: The directory path of the stored Graph.

            mmap_mode: Default :code:`mmap_mode="r"`. If not None, memory-map the graph.  
        """
        pass

        # num_nodes = np.load(
        #     os.path.join(path, 'num_nodes.npy'), mmap_mode=mmap_mode)
        # edges = np.load(os.path.join(path, 'edges.npy'), mmap_mode=mmap_mode)
        # num_graph = np.load(
        #     os.path.join(path, 'num_graph.npy'), mmap_mode=mmap_mode)
        # if os.path.exists(os.path.join(path, 'graph_node_index.npy')):
        #     graph_node_index = np.load(
        #         os.path.join(path, 'graph_node_index.npy'),
        #         mmap_mode=mmap_mode)
        # else:
        #     graph_node_index = None

        # if os.path.exists(os.path.join(path, 'graph_edge_index.npy')):
        #     graph_edge_index = np.load(
        #         os.path.join(path, 'graph_edge_index.npy'),
        #         mmap_mode=mmap_mode)
        # else:
        #     graph_edge_index = None

        # if os.path.isdir(os.path.join(path, 'adj_src')):
        #     adj_src_index = EdgeIndex.load(
        #         os.path.join(path, 'adj_src'), mmap_mode=mmap_mode)
        # else:
        #     adj_src_index = None

        # if os.path.isdir(os.path.join(path, 'adj_dst')):
        #     adj_dst_index = EdgeIndex.load(
        #         os.path.join(path, 'adj_dst'), mmap_mode=mmap_mode)
        # else:
        #     adj_dst_index = None

        # def _load_feat(feat_path):
        #     """Load features from .npy file.
        #     """
        #     feat = {}
        #     if os.path.isdir(feat_path):
        #         for feat_name in os.listdir(feat_path):
        #             feat[os.path.splitext(feat_name)[0]] = np.load(
        #                 os.path.join(feat_path, feat_name),
        #                 mmap_mode=mmap_mode)
        #     return feat

        # node_feat = _load_feat(os.path.join(path, 'node_feat'))
        # edge_feat = _load_feat(os.path.join(path, 'edge_feat'))
        # return cls(edges=edges,
        #            num_nodes=num_nodes,
        #            node_feat=node_feat,
        #            edge_feat=edge_feat,
        #            adj_src_index=adj_src_index,
        #            adj_dst_index=adj_dst_index,
        #            _num_graph=num_graph,
        #            _graph_node_index=graph_node_index,
        #            _graph_edge_index=graph_edge_index)


class BatchGraph(Graph):
    r"""
    Batch of graph objects that describe batched graphs.

    Parameters:
        edge_index (array_like, optional): list of edges of shape :math:`(|E|, 2)` or :math:`(|E|, 3)`.
            Each tuple is (node_in, node_out) or (node_in, node_out, relation).
        edge_feat (array_like, optional): edge weights of shape :math:`(|E|,)`
        num_nodes (array_like, optional): number of nodes in each graph
            By default, it will be inferred from the largest id in `edge_index`
        num_edges (array_like, optional): number of edges in each graph
        num_relation (int, optional): number of relations
        node_feat (array_like, optional): node features of shape :math:`(|V|, ...)`
        edge_feat (array_like, optional): edge features of shape :math:`(|E|, ...)`
        graph_label (array_like, optional): graph label.
        offsets (array_like, optional): node id offsets of shape :math:`(|E|,)`.
            If not provided, nodes in `edge_index` should be relative index, i.e., the index in each graph.
            If provided, nodes in `edge_index` should be absolute index, i.e., the index in the packed graph.
    """
    def __init__(self, edge_index, edge_feat=None, num_nodes=None, num_edges=None, node_feat=None, node_label=None, graph_label=None, offsets=None):
        # super().__init__(edge_index, edge_feat=edge_feat, num_nodes=num_nodes, node_feat=node_feat, node_label=node_label, graph_label=graph_label)
        
        if offsets is None:
            offsets = self._cal_offsets()
    
    @property

    def _calculate_offsets(self):
        r"""
        calculate offsets if offset is not given.
        """
        pass

    def unpack(self):
        r"""
        unpack batch graph to graph list.

        Returns:
            list[Graph]
        """
        pass

    @classmethod
    def pack(self, graphs):
        r"""
        classmethod that pack Graph list to BatchGraph.

        Return:
            BatchGraph
        """
        pass

    def merge(self, graph2graph):
        """
        Merge multiple graphs into a single graph.

        Parameters:
            graph2graph (array_like): ID of the new graph each graph belongs to
        """
        pass

    def repeat_interleave(self):
        r"""
        Repeat this packed graph. This function behaves similarly to `torch.repeat_interleave`_.

        .. _torch.repeat_interleave: https://pytorch.org/docs/stable/generated/torch.repeat_interleave.html

        Parameters:
            repeats (Tensor or int): number of repetitions for each graph

        Returns:
            BatchGraph
        """
        pass
    
import tensorflow as tf
def size_repr(key: Any, value: Any, indent: int = 0) -> str:
    pad = ' ' * indent
    if isinstance(value, tf.Tensor) and value.shape == 0:
        out = value.item()
    elif isinstance(value, tf.Tensor):
        out = str(list(value.shape))
    elif isinstance(value, np.ndarray):
        out = str(list(value.shape))
    # elif isinstance(value, SparseTensor):
    #     out = str(value.sizes())[:-1] + f', nnz={value.nnz()}]'
    elif isinstance(value, str):
        out = f"'{value}'"
    elif isinstance(value, Sequence):
        out = str([len(value)])
    elif isinstance(value, Mapping) and len(value) == 0:
        out = '{}'
    elif (isinstance(value, Mapping) and len(value) == 1
          and not isinstance(list(value.values())[0], Mapping)):
        lines = [size_repr(k, v, 0) for k, v in value.items()]
        out = '{ ' + ', '.join(lines) + ' }'
    elif isinstance(value, Mapping):
        lines = [size_repr(k, v, indent + 2) for k, v in value.items()]
        out = '{\n' + ',\n'.join(lines) + '\n' + pad + '}'
    else:
        out = str(value)

    key = str(key).replace("'", '')
    if isinstance(value, BaseStorage):
        return f'{pad}\033[1m{key}\033[0m={out}'
    else:
        return f'{pad}{key}={out}'

