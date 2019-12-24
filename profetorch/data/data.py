#AUTOGENERATED! DO NOT EDIT! File to edit: dev/data.ipynb (unless otherwise specified).

__all__ = ['tt', 'convert_date', 'get_moments', 'create_tensors', 'TimeSeries', 'DataFrame', 'create_db']

#Cell
import torch
from torch.utils.data import Dataset, DataLoader
from fastai.data_block import DataBunch, DatasetType

import warnings

torch.Tensor.ndim = property(lambda x: x.dim())
tt = torch.Tensor

#Cell
_MILISECONDS_IN_DAY = 1e9*3600*24
def convert_date(dates):
    """
    Converts pandas date format to torch Tensors (floats)
    """
    dates = dates.astype(int) / _MILISECONDS_IN_DAY
    return torch.Tensor(dates).reshape(-1,1)

def get_moments(df):
    """
    Gets the mean and variance of all columns.
    """
    df.ds = df.ds.astype(int) / _MILISECONDS_IN_DAY
    mean = df.mean()
    std = df.std()
    moments = {
        't': [mean['ds'], std['ds']],
        't_range': [df.ds.min(), df.ds.max()],
        'y': [mean['y'], std['y']]
        }
    mean.drop(['ds', 'y'], inplace=True)
    std.drop(['ds', 'y'], inplace=True)

    for k, v in moments.items():
        if v[1] == 0:
            warnings.warn(f'Standard deviation of {k} is 0. Resetting to 1.')
            moments[k][1] = 1.0

    if len(mean) > 0: # there are x variables
        moments['x'] = [tt(mean.values[None,:]),
                        tt(std.values[None,:])]
        if (moments['x'][1] == 0).any():
            idx = moments['x'][1] == 0
            moments['x'][1][idx] = 1
            warnings.warn('Standard deviation of some x feature is 0. Resetting to 1.')

    return moments

def create_tensors(df, moments, predict=False):
    """
    converts a pandas dataframe to pytorch tensors
    """
    # get time tensor
    t = convert_date(df['ds'].values)
    data = {'t': t}
    df.drop(['ds'], axis=1, inplace=True)

    # get y tensor (if not in predict stage)
    if not predict: # 'y' in df.columns and
        y = torch.Tensor(df['y'].values).reshape(-1, 1)
        df.drop(['y'], axis=1, inplace=True)
        data['y'] = y

    if predict and 'y' in df.columns:
        df.drop(['y'], axis=1, inplace=True)

    # add x if it's available
    if df.shape[1] > 0:
        x = torch.Tensor(df.values).float()
        data['x'] = x


    data = {k: (v - moments[k][0]) / moments[k][1] for k, v in data.items()}

    return data, moments

#Cell
class TimeSeries(Dataset):
    """
    Load raw x,y data
    """
    def __init__(self, x, y):
        super().__init__()
        self.x, self.y = x, y

    def __len__(self):
        return len(self.y)

    def __getitem__(self, i):
        return torch.Tensor([self.x[i]]), torch.Tensor([self.y[i]])

class DataFrame(Dataset):
    """
    Take a data frame with columns ds | y | other_cols and convert to pytorch tensors.
    """
    def __init__(self, df, moments=None):
        super().__init__()
        self.data, self.moments = create_tensors(df, moments)

    def __len__(self):
        return len(self.data['t'])

    def __getitem__(self, i):
        if 'x' in self.data:
            return (self.data['t'][i], self.data['x'][i]), self.data['y'][i]
        else:
            return self.data['t'][i], self.data['y'][i]

#Cell
def create_db(df, train_p=0.8, bs=96, moments=None):
    """
    Take dataframe and convert to Fastai databunch
    """
    train_len = int(train_p*len(df))
    df.reset_index(drop=True, inplace=True)
    train_ds = DataFrame(df.iloc[:train_len], moments)
    val_ds = DataFrame(df.iloc[train_len:], moments)

    bs = min(bs, len(train_ds))
    val_bs = min(bs, len(val_ds))
    return DataBunch.create(train_ds, val_ds, bs=bs, val_bs=val_bs)