from typing import Dict, Optional

import torch
from torch import nn
import numpy as np
import math

def select_most_energetic(
    x: torch.Tensor, num: int, dim: Optional[int] = -2, dim_reduc: Optional[int] = -1
):
    """
    Selects the `num` indices with most power

    Parametes
    ----------
    x: torch.Tensor  (n_batch, n_channels, n_samples)
        The input tensor
    num: int
        The number of signals to select
    dim:
        The axis where the selection should occur
    dim_reduc:
        The axis where to perform the reduction
    """

    power = x.abs().square().mean(axis=dim_reduc, keepdim=True)

    index = torch.argsort(power.transpose(dim, -1), axis=-1, descending=True)
    index = index[..., :num]

    # need to broadcast to target size
    x_tgt = x.transpose(dim, -1)[..., :num]
    _, index = torch.broadcast_tensors(x_tgt, index)

    # reorder index axis
    index = index.transpose(dim, -1)

    ret = torch.gather(x, dim=dim, index=index)
    return ret


def module_from_config(name: str, kwargs: Optional[Dict] = None, **other):
    """
    Get a model by its name

    Parameters
    ----------
    name: str
        Name of the model class
    kwargs: dict
        A dict containing all the arguments to the model
    """

    if kwargs is None:
        kwargs = {}

    parts = name.split(".")
    obj = None

    if len(parts) == 1:
        raise ValueError("Can't find object without module name")

    else:
        module = __import__(".".join(parts[:-1]), fromlist=(parts[-1],))
        if hasattr(module, parts[-1]):
            obj = getattr(module, parts[-1])

    if obj is not None:
        return obj(**kwargs)
    else:
        raise ValueError(f"The model {name} could not be found")




def cartesian_to_spherical_torch(p):
    """
    Parameters
    ----------
    p: array_like, shape (..., n_dim, n_points)
        A collection of vectors
    Returns
    -------
    doa: ndarray, shape (..., n_dim-1, n_points)
        The (colatitude, azimuth) pairs or only (azimuth) giving the direction of the vectors
    r: ndarray, shape (...., n_points,)
        The norms of the vectors
    """

    n_dim = p.shape[-2]

    r = torch.linalg.norm(p, dim=-2, keepdim=True)
    u = p / r

    doa = torch.zeros_like(p, device=p.device)
    doa = doa[..., :n_dim-1, :]

    if n_dim == 3:
        # colatitude
        doa[..., 0, :] = torch.atan2(torch.sqrt(p[..., 0, :] ** 2 + p[..., 1, :] ** 2), p[..., 2, :])

        # azimuths
        doa[..., 1, :] = torch.atan2(p[..., 1, :], p[..., 0, :])
        doa[..., 1, :] = (2 * math.pi + doa[..., 1, :]) % (2 * math.pi)
    
    elif n_dim==2:
        # azimuths
        doa[..., 0, :] = torch.atan2(p[..., 1, :], p[..., 0, :])
        doa[..., 0, :] = (2 * math.pi + doa[..., 0, :]) % (2 * math.pi)
 
    return doa, r


def spherical_to_cartesian_torch(doa, distance, ref=None):
    """
    Transform spherical coordinates to cartesian
    Parameters
    ----------
    doa: (n_points, 2)
        The doa of the sources as (colatitude, azimuth) pairs
    distance: float or array (n_points)
        The distance of the source from the reference point
    ref: ndarray, shape (3,)
        The reference point, defaults to zero if not specified
    Returns
    -------
    R: array (3, n_points)
        An array that contains the cartesian coordinates of the points
        in its columns
    """

    #doa = torch.tensor(doa)
    distance = torch.tensor(distance, device=doa.device)

    if distance.ndim == 0:
        distance = distance[None]

    assert doa.ndim == 2
    assert doa.shape[1] == 2
    assert distance.ndim < 3

    R = torch.zeros((3, doa.shape[0]), dtype=doa.dtype, device=doa.device)

    R[0, :] = torch.cos(doa[:, 1]) * torch.sin(doa[:, 0])
    R[1, :] = torch.sin(doa[:, 1]) * torch.sin(doa[:, 0])
    R[2, :] = torch.cos(doa[:, 0])

    R *= distance[None, :]

    if ref is not None:
        assert ref.ndim == 1
        assert ref.shape[0] == 3
        R += ref[:, None]

    return R.T


def cartesian_to_spherical(p):
    """
    Parameters
    ----------
    p: array_like, shape (3, n_points)
        A collection of vectors
    Returns
    -------
    doa: ndarray, shape (2, n_points)
        The (colatitude, azimuth) pairs giving the direction of the vectors
    r: ndarray, shape (n_points,)
        The norms of the vectors
    """

    r = np.linalg.norm(p, axis=0)
    u = p / r[None, :]

    doa = np.zeros((2, p.shape[1]), dtype=p.dtype)

    # colatitude
    doa[0, :] = np.arctan2(np.sqrt(p[0, :] ** 2 + p[1, :] ** 2), p[2, :])

    # azimuths
    doa[1, :] = np.arctan2(p[1, :], p[0, :])
    I = doa[1, :] < 0
    doa[1, I] = 2 * np.pi + doa[1, I]

    return doa, r


def spherical_to_cartesian(doa, distance, ref=None):
    """
    Transform spherical coordinates to cartesian
    Parameters
    ----------
    doa: (n_points, 2)
        The doa of the sources as (colatitude, azimuth) pairs
    distance: float or array (n_points)
        The distance of the source from the reference point
    ref: ndarray, shape (3,)
        The reference point, defaults to zero if not specified
    Returns
    -------
    R: array (3, n_points)
        An array that contains the cartesian coordinates of the points
        in its columns
    """

    doa = np.array(doa)
    distance = np.array(distance)

    if distance.ndim == 0:
        distance = distance[None]

    assert doa.ndim == 2
    assert doa.shape[1] == 2
    assert distance.ndim < 3

    R = np.zeros((3, doa.shape[0]), dtype=doa.dtype)

    R[0, :] = np.cos(doa[:, 1]) * np.sin(doa[:, 0])
    R[1, :] = np.sin(doa[:, 1]) * np.sin(doa[:, 0])
    R[2, :] = np.cos(doa[:, 0])
    R *= distance[None, :]

    if ref is not None:
        assert ref.ndim == 1
        assert ref.shape[0] == 3
        R += ref[:, None]

    return R
