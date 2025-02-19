# !/usr/bin/env python3
# -*- coding:utf-8 -*-

# @Time    : 2022/04/10 11:57
# @Author  : clear
# @FileName: rgcn_conv.py.py

import tensorlayerx as tlx
from gammagl.layers.conv import MessagePassing


def masked_edge_index(edge_index, edge_mask):
    if tlx.BACKEND == 'mindspore':
        idx = tlx.convert_to_tensor([i for i, v in enumerate(edge_mask) if v], dtype=tlx.int64)
        return tlx.gather(edge_index, idx)
    else:
        return (edge_index.T[edge_mask]).T


class RGCNConv(MessagePassing):
    """
    The relational graph convolutional operator from the `"Modeling
    Relational Data with Graph Convolutional Networks"
    <https://arxiv.org/abs/1703.06103>`_ paper
    .. math::
        \mathbf{x}^{\prime}_i = \mathbf{\Theta}_{\textrm{root}} \cdot
        \mathbf{x}_i + \sum_{r \in \mathcal{R}} \sum_{j \in \mathcal{N}_r(i)}
        \frac{1}{|\mathcal{N}_r(i)|} \mathbf{\Theta}_r \cdot \mathbf{x}_j,
    where :math:`\mathcal{R}` denotes the set of relations, *i.e.* edge types.
    Edge type needs to be a one-dimensional :obj:`torch.long` tensor which
    stores a relation identifier
    :math:`\in \{ 0, \ldots, |\mathcal{R}| - 1\}` for each edge.
    """

    def __init__(self,
                 in_channels,
                 out_channels,
                 num_relations: int,
                 num_bases = None,
                 num_blocks = None,
                 root_weight: bool = True,
                 add_bias=True):
        super().__init__()
        if num_bases is not None and num_blocks is not None:
            raise ValueError('Can not apply both basis-decomposition and '
                             'block-diagonal-decomposition at the same time.')

        self.in_channels = in_channels
        self.out_channels = out_channels
        self.num_relations = num_relations
        self.num_bases = num_bases
        self.num_blocks = num_blocks

        if isinstance(in_channels, int):
            in_channels = (in_channels, in_channels)
        self.in_channels_l = in_channels[0]

        initor = tlx.initializers.truncated_normal()
        if num_bases is not None:
            self.weight = self._get_weights(var_name="weight",
                                            shape=(num_bases, in_channels[0], out_channels),
                                            init=initor)
            self.base_att = self._get_weights(var_name="base_att",
                                              shape=(num_relations, num_bases),
                                              init=initor)
        elif num_blocks is not None:
            assert (in_channels[0] % num_blocks == 0
                    and out_channels % num_blocks == 0)
            self.weight = self._get_weights(var_name="weight",
                                            shape=(num_relations,
                                                   num_blocks,
                                                   in_channels[0] // num_blocks,
                                                   out_channels // num_blocks),
                                            init=initor)
        else:
            self.weight = self._get_weights(var_name="weight",
                                            shape=(out_channels, in_channels[0], num_relations,),
                                            init=initor)

        if root_weight:
            self.root = self._get_weights(var_name="root",
                                            shape=(in_channels[1], out_channels),
                                            init=initor)

        if add_bias:
            self.bias = self._get_weights(var_name="bias", shape=(out_channels,),  init=initor)

    def forward(self, x, edge_index, edge_type = None):
        r"""
        Args:

            x: The input node features. Can be either a :obj:`[num_nodes,
               in_channels]` node feature matrix, or an optional
               one-dimensional node index tensor (in which case input features
               are treated as trainable node embeddings).
               Furthermore, :obj:`x` can be of type :obj:`tuple` denoting
               source and destination node features.
            edge_index: edge index
            edge_type: The one-dimensional relation type/index for each edge in
               :obj:`edge_index`.
               Should be only :obj:`None` in case :obj:`edge_index` is of type
               :class:`torch_sparse.tensor.SparseTensor`.
               (default: :obj:`None`)
        """
        x_l = None
        if isinstance(x, tuple):
            x_l = x[0]
        else:
            x_l = x
        if x_l is None:
            x_l = tlx.arange(0, self.in_channels_l, dtype=tlx.int64)
        x_r = x_l
        if isinstance(x, tuple):
            x_r = x[1]
        size = (x_l.shape[0], x_r.shape[0])
        out = tlx.zeros(shape=(x_r.shape[0], self.out_channels), dtype=tlx.float32)

        weight = self.weight
        if self.num_bases is not None:  # Basis-decomposition =================
            weight = (self.comp @ weight.view(self.num_bases, -1)).view(
                self.num_relations, self.in_channels_l, self.out_channels)

        if self.num_blocks is not None:  # Block-diagonal-decomposition =====
            if x_l.dtype == tlx.int64 and self.num_blocks is not None:
                raise ValueError('Block-diagonal decomposition not supported '
                                 'for non-continuous input features.')

            for i in range(self.num_relations):
                edges = masked_edge_index(edge_index, edge_type == i)
                h = self.propagate(x_l, edges, size[1])
                h = tlx.reshape(h, (-1, weight.shape[1], weight.shape[2]))
                h = tlx.ops.einsum('abc,bcd->abd', h, weight[i]) # tlx还不支持，因为ms没有这个算子。
                out += h.contiguous().view(-1, self.out_channels)

        else:  # No regularization/Basis-decomposition ========================
            for i in range(self.num_relations):
                edges = masked_edge_index(edge_index, edge_type==i)

                if x_l.dtype == tlx.int64 or str(x_l.dtype) == 'paddle.int64': # paddle 报错
                    # paddle 的做法
                    # bucketed_msg = Message(msg, segment_ids)
                    # output = reduce_func(bucketed_msg)
                    # output_dim = output.shape[-1]
                    # init_output = paddle.zeros(
                    #     shape=[self._num_nodes, output_dim], dtype=output.dtype)
                    # final_output = scatter(init_output, uniq_ind, output)
                    #
                    # return final_output
                    out += self.propagate(weight[i][x_l], edges, num_nodes=size[1])
                else:
                    h = self.propagate(x, edges, num_nodes=size[1])
                    out = out + (h @ weight[i])

        root = self.root
        if root is not None:
            out += root[x_r] if x_r.dtype == tlx.int64 else x_r @ root

        if self.bias is not None:
            out += self.bias

        return out

