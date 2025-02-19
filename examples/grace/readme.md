# GammaGL Implementation of GRACE
This GammaGL example implements the model proposed in the paper [Deep Graph Contrastive Representation Learning](https://arxiv.org/abs/2006.04131).

Author's code: https://github.com/CRIPAC-DIG/GRACE

## Example Implementor

This example was implemented by Siyuan Zhang

## Datasets

##### Unsupervised Node Classification Datasets:

'Cora', 'Citeseer' and 'Pubmed'

| Dataset  | # Nodes | # Edges | # Classes |
| -------- | ------- | ------- | --------- |
| Cora     | 2,708   | 10,556  | 7         |
| Citeseer | 3,327   | 9,228   | 6         |
| Pubmed   | 19,717  | 88,651  | 3         |


## Arguments

```
--dataset               str     The graph dataset name.                Default is 'cora'.
--epochs                int     Number of training periods.            Default is 500.
--lr                    float   Learning rate.                         Default is 0.001.
--l2                    float   Weight decay.                          Default is 1e-5.
--temp                  float   Temperature.                           Default is 1.0.
--hid_dim               int     Hidden dimension.                      Default is 256.
--out_dim               int     Output dimension.                      Default is 256.
--num_layers            int     Number of GNN layers.                  Default is 2.
--drop_edge_rate_1      float   Drop edge ratio 1.                     Default is 0.2. 
--drop_edge_rate_2      float   Drop edge ratio 2.                     Default is 0.2. 
--drop_feature_rate_1   float   Drop feature ratio 1.                  Default is 0.2. 
--drop_feature_rate_2   float   Drop feature ratio 2.                  Default is 0.2. 
--dataset_path          str     path to save dataset.                  Default is r'../'
--best_model_path       str     path to save best model                Default is r'./'
```

## How to run examples

In the paper(as well as authors' repo), the training set and testing set are split randomly with 1:9 ratio. In order to fairly compare it with other methods with the public split (20 training nodes each class), in this repo we also provide its results using the public split (with fine-tuned hyper-parameters). To run the examples, follow the following instructions.

```python
# Cora with random split in paper
python main.py --dataset cora --epochs 200 --lr 5e-4 --l2 1e-5 --hid_dim 256 --drop_edge_rate_1 0.2 --drop_edge_rate_2 0.2 --drop_feature_rate_1 0.2 --dfr2 0.2 --temp 1

# Cora by GammaGL
python main.py --dataset cora --epochs 500 --lr 5e-4 --l2 1e-5 --hid_dim 128 --drop_edge_rate_1 0.2 --drop_edge_rate_2 0.4 --drop_feature_rate_1 0.3 --dfr2 0.4 --temp 0.4

# Citeseer with random split
python main.py --dataset citeseer --epochs 200 --lr 1e-3 --l2 1e-5 --hid_dim 256 --drop_edge_rate_1 0.2 --drop_edge_rate_2 0.0 --drop_feature_rate_1 0.3 --dfr2 0.2 --temp 0.9

# Pubmed with random split
python main.py --dataset pubmed --epochs 1500 --lr 1e-3 --l2 1e-5 --hid_dim 256 --drop_edge_rate_1 0.4 --drop_edge_rate_2 0.1 --drop_feature_rate_1 0.0 --drop_feature_rate_2 0.2 --temp 0.7

```

## 	Performance

For random split, we use the hyper-parameters as stated in the paper. For public split,  we find the given hyper-parameters lead to poor performance, so we select the hyperparameters via a small grid search.

Random split (Train/Test = 1:9)

|      Dataset      | Cora | Citeseer | Pubmed |
| :---------------: | :--: | :------: | :----: |
|        DGL        | 83.3 |   72.1   |  86.7  |
|   Author's Code   | 83.1 |   71.0   |  86.3  |
|     GammaGL       | 83.1 |   --.-   |  --.-  |

