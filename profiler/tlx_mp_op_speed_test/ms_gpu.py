# !/usr/bin/env python3
# -*- coding:utf-8 -*-

# @Time    : 2022/04/14 08:36
# @Author  : clear
# @FileName: ms_gpu.py

import os
os.environ['TL_BACKEND'] = 'mindspore'
os.environ["CUDA_VISIBLE_DEVICES"] = "2"
import sys
sys.path.insert(0, os.path.abspath('../../'))
from pyinstrument import Profiler
import numpy as np
import tensorlayerx as tlx
import gammagl.mpops as mpops


edge_index = np.load('edge_index.npy')
num_nodes = int(np.max(edge_index))+1
src = edge_index[0,:]
dst = edge_index[1,:]
src = tlx.convert_to_tensor(src, tlx.int32)
dst = tlx.convert_to_tensor(dst, tlx.int32)
x = tlx.convert_to_tensor(np.random.randn(num_nodes, 1000), dtype=tlx.float32)
pf = Profiler()

pf.start()
for j in range(1000):
    msg = tlx.gather(x, src)
    # mpops.unsorted_segment_sum(msg, dst, num_nodes)
    # mpops.unsorted_segment_mean(msg, dst, num_nodes)
    mpops.unsorted_segment_max(msg, dst, num_nodes)
pf.stop()
print(pf.output_text(unicode=True, color=True))


dst = tlx.convert_to_numpy(dst)
idx = np.argsort(dst)
dst = tlx.gather(tlx.convert_to_tensor(dst, dtype=tlx.int32), tlx.convert_to_tensor(idx,dtype=tlx.int32))

pf.start()
for j in range(1000):
    msg = tlx.gather(x, src)
    # mpops.segment_sum(msg, dst, num_nodes)
    # mpops.segment_mean(msg, dst, num_nodes)
    mpops.segment_max(msg, dst, num_nodes)
pf.stop()
print(pf.output_text(unicode=True, color=True))