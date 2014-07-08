__all__ = ['change_axis_schema']

import numpy as np
from .utils import _new_attribute_label


def change_axis_schema(datashape, axis, start=None, stop=None,
                       chunk=None, overlap=None, name=None):
    """
    Create a new DataShape by modifying the parameters of one axis

    Parameters
    ----------
    datashape : SciDBDataShape
        The template data shape
    axis : int
        Which axis to modify
    stop : int (optional)
        New axis upper bound
    chunk : int (optional)
        New chunk size
    overlap : int (optional)
        New chunk overlap
    name : str (optional)
        New dimension name

    Returns
    -------
    A new SciDBDataShape, obtained by overriding the input parameters
    of the template datashape along the specified axis
    """
    from .scidbarray import SciDBDataShape

    if start is not None:
        raise NotImplementedError("start is not supported")
    names = list(datashape.dim_names)
    stops = list(datashape.shape)
    chunks = list(datashape.chunk_size)
    overlaps = list(datashape.chunk_overlap)
    if stop is not None:
        stops[axis] = stop + 1
    if chunk is not None:
        chunks[axis] = chunk
    if overlap is not None:
        overlaps[axis] = overlap
    if name is not None:
        names[axis] = name
    return SciDBDataShape(stops, datashape.dtype, dim_names=names,
                          chunk_size=chunks, chunk_overlap=overlaps)


def _unique(val, taken):
    if val not in taken:
        return val
    offset = 2
    while '%s_%i' % (val, offset) in taken:
        offset += 1
    return '%s_%i' % (val, offset)


def _rename_att(datashape, index, name):
    from scidbpy import SciDBDataShape, sdbtype

    atts = datashape.sdbtype.names
    if atts[index] == name:
        return datashape

    rep = [list(x) for x in datashape.sdbtype.full_rep]
    rep[index][0] = name
    rep = [tuple(x) for x in rep]

    schema = "tmp%s%s" % (sdbtype(np.dtype(rep)).schema, datashape.dim_schema)
    return SciDBDataShape.from_schema(schema)


def _rename_dim(datashape, index, name):
    from scidbpy import SciDBDataShape

    names = datashape.dim_names
    if names[index] == name:
        return datashape

    schema = "tmp" + datashape.schema
    # XXX doesn't work if fixing non-first duplicate dim name
    schema = schema.replace('%s=' % names[index], '%s=' % name, 1)
    return SciDBDataShape.from_schema(schema)


def disambiguate(*arrays):
    """
    Process a list of arrays with calls to cast as needed, to avoid
    any name collisions in dimensions or attributes
    """
    from .scidbarray import SciDBArray

    all_names = [name for a in arrays if isinstance(a, SciDBArray)
                 for nameset in [a.dim_names, a.att_names]
                 for name in nameset]

    # no collisions, return unmodified
    if len(set(all_names)) == len(all_names):
        return arrays

    taken = set()
    result = []
    afl = None

    for a in arrays:
        if not isinstance(a, SciDBArray):
            result.append(a)
            continue

        afl = afl or a.afl

        ds = a.datashape
        for i, att in enumerate(a.att_names):
            att = _unique(att, taken)
            taken.add(att)
            ds = _rename_att(ds, i, att)
        for i, dim in enumerate(a.dim_names):
            dim = _unique(dim, taken)
            taken.add(dim)
            ds = _rename_dim(ds, i, dim)
        if ds.schema == a.datashape.schema:
            result.append(a)
        else:
            result.append(afl.cast(a, ds.schema))
    return tuple(result)


def _att_schema_item(rep):
    name, typ, nullable = rep
    result = '{0}:{1}'.format(name, typ)
    if nullable:
        result = result + ' NULL DEFAULT null'
    return result


def _dim_schema_item(name, limit):
    return '{0}={1}:{2},1000,0'.format(name, limit[0], limit[1])


def limits(array, names):
    """
    Compute the lower/upper bounds for a set of attributes

    Parameters
    ----------
    array : SciDBArray
        The array to consider
    names : list of strings
        Names of attributes to consider

    Returns
    -------
    limits : dict mapping name->(lo, hi)
        Contains the minimum and maximum value for each attribute

    Notes
    -----
    This performs a full scan of the array
    """

    args = ['%s(%s)' % (f, n)
            for n in names
            for f in ['min', 'max']]
    result = array.afl.aggregate(array, *args).toarray()
    return dict((n, (int(result['%s_min' % n][0]), int(result['%s_max' % n][0])))
                for n in names)


def as_dimensions(array, *dims):
    """
    Redimension an array as needed, ensuring that the arguments
    are dimensions of the result

    Parameters
    ----------
    array: SciDBArray
        The array to redimension
    dims : One or more strings
        The names of attributes or dimensions in ``array`` which
        *must* be stored as dimensions in the output

    Returns
    -------
    result : SciDBArray
       A possibly-redimensioned version of ``array``.
    """
    if set(array.att_names) == set(dims):
        dummy = _new_attribute_label('__dummy', array)
        array = array.apply(dummy, 0)

    to_promote = set(dims) & set(array.att_names)
    if not to_promote:
        return array
    lim = limits(array, to_promote)
    atts = ','.join([_att_schema_item(r)
                    for r in array.sdbtype.full_rep
                    if r[0] not in to_promote])
    dims = [array.datashape.dim_schema[1:-1]]
    dims.extend(_dim_schema_item(k, v)
                for k, v in lim.items())
    dims = ','.join(dims)
    schema = '<{0}> [{1}]'.format(atts, dims)
    return array.redimension(schema)
