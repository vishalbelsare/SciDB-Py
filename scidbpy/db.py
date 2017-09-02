"""DB, Array, and Operator
=======================

Classes for connecting to SciDB and executing queries.

"""

import copy
import enum
import itertools
import logging
import numpy
import os
import pandas
import re
import requests
import threading

try:
    from weakref import finalize
except ImportError:
    from backports.weakref import finalize

from .ops_hungry import ops_hungry
from .schema import Attribute, Dimension, Schema


class Shim(enum.Enum):
    cancel = 'cancel'
    execute_query = 'execute_query'
    new_session = 'new_session'
    read_bytes = 'read_bytes'
    release_session = 'release_session'
    upload = 'upload'


class Password_Placeholder(object):
    def __repr__(self):
        return 'PASSWORD_PROVIDED'


class DB(object):
    """SciDB Shim connection object.

    >>> DB()
    DB('http://localhost:8080', None, None, None, None, None)

    >>> print(DB())
    scidb_url  = 'http://localhost:8080'
    scidb_auth = None
    http_auth  = None
    role       = None
    namespace  = None
    verify     = None
    """

    _show_query = "show('{}', 'afl')"

    def __init__(
            self,
            scidb_url=None,
            scidb_auth=None,
            http_auth=None,
            role=None,
            namespace=None,
            verify=None):
        # scidb_url fallback to SCIDB_URL or http://localhost:8080
        if scidb_url is None:
            scidb_url = os.getenv('SCIDB_URL', 'http://localhost:8080')

        self.scidb_url = scidb_url
        self.role = role
        self.namespace = namespace
        self.verify = verify

        if http_auth:
            self._http_auth = requests.auth.HTTPDigestAuth(*http_auth)
            self.http_auth = (http_auth[0], Password_Placeholder())
        else:
            self._http_auth = self.http_auth = None

        if scidb_auth:
            if not self.scidb_url.lower().startswith('https'):
                raise Exception(
                    'SciDB credentials can only be used ' +
                    'with https connections')

            self._scidb_auth = {'user': scidb_auth[0],
                                'password': scidb_auth[1]}
            self.scidb_auth = (scidb_auth[0], Password_Placeholder())
        else:
            self._scidb_auth = self.scidb_auth = None

        self.arrays = Arrays(self)

        # get list of operators and macros
        id = self._shim(Shim.new_session).text

        self._id = self._shim(
            Shim.execute_query,
            id=id,
            query="project(list('operators'), name)",
            save='tsv').text  # set query ID as DB instance ID
        operators = self._shim_readlines(id=id)

        self._shim(
            Shim.execute_query,
            id=id,
            query="project(list('macros'), name)",
            save='tsv').content
        macros = self._shim_readlines(id=id)

        self._shim(Shim.release_session, id=id)

        self.operators = operators + macros
        self._dir = (self.operators +
                     ['arrays',
                      'gc',
                      'iquery',
                      'iquery_readlines',
                      'upload'])
        self._dir.sort()

        self._lock = threading.Lock()
        self._array_cnt = 0

    def __iter__(self):
        return (i for i in (
            self.scidb_url,
            self.scidb_auth,
            self.http_auth,
            self.role,
            self.namespace,
            self.verify))

    def __repr__(self):
        return '{}({!r}, {!r}, {!r}, {!r}, {!r}, {!r})'.format(
            type(self).__name__, *self)

    def __str__(self):
        return '''\
scidb_url  = '{}'
scidb_auth = {}
http_auth  = {}
role       = {}
namespace  = {}
verify     = {}'''.format(*self)

    def __getattr__(self, name):
        if name in self.operators:
            return Operator(self, name)
        else:
            raise AttributeError(
                '{.__name__!r} object has no attribute {!r}'.format(
                    type(self), name))

    def __dir__(self):
        return self._dir

    def iquery(self,
               query,
               fetch=False,
               atts_only=False,
               as_dataframe=False,
               dataframe_promo=True,
               schema=None,
               upload_data=None,
               upload_schema=None):
        """Execute query in SciDB

        :param bool fetch: If `True`, download SciDB array (default
          `False`)

        :param bool atts_only: If `True`, download only SciDB array
          attributes without dimensions (default `False`)

        :param bool as_dataframe: If `True`, return a Pandas
          DataFrame. If `False`, return a NumPy array (default
          `False`)

        :param bool dataframe_promo: If `True`, null-able types are
          promoted as per Pandas 'promotion scheme
          <http://pandas.pydata.org/pandas-docs/stable/gotchas.html
          #na-type-promotions>`_ If `False`, object records are used
          for null-able types (default `True`)

        :param schema: Schema of the SciDB array to use when
          downloading the array. Schema is not verified. If schema is
          a Schema instance, it is copied. Otherwise, a
          :py:class:`Schema` object is built using
          :py:func:`Schema.fromstring` (default `None`).

        >>> DB().iquery('build(<x:int64>[i=0:1; j=0:1], i + j)', fetch=True)
        ... # doctest: +NORMALIZE_WHITESPACE
        array([(0, 0, (255, 0)),
               (0, 1, (255, 1)),
               (1, 0, (255, 1)),
               (1, 1, (255, 2))],
              dtype=[('i', '<i8'), ('j', '<i8'),
                     ('x', [('null', 'u1'), ('val', '<i8')])])

        >>> DB().iquery("input({sch}, '{fn}', 0, '{fmt}')",
        ...             fetch=True,
        ...             upload_data=numpy.arange(3, 6))
        ... # doctest: +NORMALIZE_WHITESPACE
        array([(0, 3), (1, 4), (2, 5)],
              dtype=[('i', '<i8'), ('x', '<i8')])

        """

        id = self._shim(Shim.new_session).text

        if upload_data is not None:
            if isinstance(upload_data, numpy.ndarray):
                if upload_schema is None:
                    upload_schema = Schema.fromdtype(upload_data.dtype)

                # Convert upload data to bytes
                if upload_schema.is_fixsize():
                    upload_data = upload_data.tobytes()
                else:
                    upload_data = upload_schema.tobytes(upload_data)
            # TODO
            # Assume upload data is already in bytes format
            fn = self._shim(Shim.upload, id=id, data=upload_data).text
            query = query.format(
                sch=upload_schema,
                fn=fn,
                fmt=upload_schema.atts_fmt_scidb if upload_schema else None)

        if fetch:
            # Use provided schema or get schema from SciDB
            if schema:
                # Deep-copy schema since we might be mutating it
                if isinstance(schema, Schema):
                    if not atts_only:
                        schema = copy.deepcopy(schema)
                else:
                    schema = Schema.fromstring(schema)
            else:
                # Execute 'show(...)' and Download text
                self._shim(
                    Shim.execute_query,
                    id=id,
                    query=DB._show_query.format(query.replace("'", "\\'")),
                    save='tsv')
                schema = Schema.fromstring(
                    self._shim(Shim.read_bytes, id=id, n=0).text)

            # Attributes and dimensions can collide. Run make_unique to
            # remove any collisions.
            #
            # make_unique fixes any collision, but if we don't
            # download the dimensions, we don't need to fix collisions
            # between dimensions and attributes. So, we use
            # make_unique only if there are collisions within the
            # attribute names.
            if ((not atts_only or
                 len(set((a.name for a in schema.atts))) <
                 len(schema.atts)) and schema.make_unique()):
                # Dimensions or attributes were renamed due to
                # collisions. We need to cast.
                query = 'cast({}, {:h})'.format(query, schema)

            # Unpack
            if not atts_only:
                # apply: add dimensions as attributes
                # project: place dimensions first
                query = 'project(apply({}, {}), {})'.format(
                    query,
                    ', '.join('{0}, {0}'.format(d.name) for d in schema.dims),
                    ', '.join(i.name for i in itertools.chain(
                        schema.dims, schema.atts)))

                # update schema after apply
                schema.make_dims_atts()

            # Execute Query and Download content
            self._shim(Shim.execute_query,
                       id=id,
                       query=query,
                       save=schema.atts_fmt_scidb)
            buf = self._shim(Shim.read_bytes, id=id, n=0).content

            self._shim(Shim.release_session, id=id)

            if schema.is_fixsize() and (not as_dataframe or
                                        not dataframe_promo):
                data = numpy.frombuffer(buf, dtype=schema.atts_dtype)
            else:
                data = schema.frombytes(buf, as_dataframe, dataframe_promo)

            # Return NumPy array or Pandas dataframe
            if as_dataframe:
                return pandas.DataFrame.from_records(data)
            else:
                return data

        else:                   # fetch=False
            self._shim(Shim.execute_query, id=id, query=query, release=1)

    def iquery_readlines(self, query):
        """Execute query in SciDB

        >>> DB().iquery_readlines('build(<x:int64>[i=0:2], i * i)')
        ... # doctest: +ELLIPSIS
        [...'0', ...'1', ...'4']

        >>> DB().iquery_readlines(
        ...   'apply(build(<x:int64>[i=0:2], i), y, i + 10)')
        ... # doctest: +ELLIPSIS
        [[...'0', ...'10'], [...'1', ...'11'], [...'2', ...'12']]
        """
        id = self._shim(Shim.new_session).text
        self._shim(Shim.execute_query, id=id, query=query, save='tsv')
        ret = self._shim_readlines(id=id)
        self._shim(Shim.release_session, id=id)
        return ret

    def next_array_name(self):
        # Thread-safe counter
        with self._lock:
            self._array_cnt += 1
            return 'py_{}_{}'.format(self._id, self._array_cnt)

    def _shim(self, endpoint, **kwargs):
        """Make request on Shim endpoint"""
        if self._scidb_auth and endpoint in (Shim.cancel, Shim.execute_query):
            kwargs.update(self._scidb_auth)
        url = requests.compat.urljoin(self.scidb_url, endpoint.value)
        if endpoint == Shim.upload:
            req = requests.post(
                '{}?id={}'.format(url, kwargs['id']),
                data=kwargs['data'],
                auth=self._http_auth,
                verify=self.verify)
        else:
            req = requests.get(
                url,
                params=kwargs,
                auth=self._http_auth,
                verify=self.verify)
        req.reason = req.content
        req.raise_for_status()
        return req

    def _shim_readlines(self, id):
        """Read data from Shim and parse as text lines"""
        return [line.split('\t') if '\t' in line else line
                for line in self._shim(
                        Shim.read_bytes, id=id, n=0).text.splitlines()]


class Arrays(object):
    """Access to arrays available in SciDB"""
    def __init__(self, db):
        self.db = db

    def __repr__(self):
        return '{}({!r})'.format(
            type(self).__name__, self.db)

    def __str__(self):
        return '''DB:
{}'''.format(self.db)

    def __getattr__(self, name):
        return Array(self.db, name)

    def __dir__(self):
        """Download the list of SciDB arrays. Use 'project(list(), name)' to
        download only names and schemas
        """
        return self.db.iquery_readlines('project(list(), name)')


class Array(object):
    """Access to individual array"""
    def __init__(self, db, name, gc=False):
        self.db = db
        self.name = name

        if gc:
            finalize(self,
                     self.db.iquery,
                     'remove({})'.format(self.name))

    def __repr__(self):
        return '{}({!r}, {!r})'.format(
            type(self).__name__, self.db, self.name)

    def __str__(self):
        return self.name

    def __getattr__(self, key):
        return ArrayExp('{}.{}'.format(self.name, key))

    def __getitem__(self, key):
        return self.fetch()[key]

    def __dir__(self):
        """Download the schema of the SciDB array, using `show()`"""
        sh = Schema.fromstring(
            self.db.iquery_readlines('show({})'.format(self))[0])
        ls = [i.name for i in itertools.chain(sh.atts, sh.dims)]
        ls.sort()
        return ls

    def fetch(self, as_dataframe=False):
        return self.db.iquery(
            'scan({})'.format(self), fetch=True, as_dataframe=as_dataframe)


class ArrayExp(object):
    """Access to individual attribute or dimension"""
    def __init__(self, exp):
        self.exp = exp

    def __repr__(self):
        return '{}({!r})'.format(type(self).__name__, self.exp)

    def __str__(self):
        return '{}'.format(self.exp)

    def __add__(self, other):
        return ArrayExp('{} + {}'.format(self, other))


class Operator(object):
    """Store SciDB operator and arguments. Hungry operators (e.g., remove,
    store, etc.) evaluate immediately. Lazy operators evaluate on data
    fetch.

    """
    def __init__(self, db, name, upload_data=None, upload_schema=None, *args):
        self.db = db
        self.name = name
        self.upload_data = upload_data
        self.upload_schema = upload_schema

        self.args = list(args)
        self.is_lazy = self.name.lower() not in ops_hungry

        self._dir = self.db.operators + ['fetch']
        self._dir.sort()

    def __repr__(self):
        return '{}(db={!r}, name={!r}, args=[{}])'.format(
            type(self).__name__,
            self.db,
            self.name,
            ', '.join('{!r}'.format(i) for i in self.args))

    def __str__(self):
        args_fmt_scidb = ('{}'.format(i) for i in self.args)
        return '{}({})'.format(self.name, ', '.join(args_fmt_scidb))

    def __call__(self, *args, **kwargs):
        """Returns self for lazy expressions. Executes immediate expressions.
        """
        self.args.extend(args)

        # Special case: -- - create_array - --
        if self.name.lower() == 'create_array' and len(self.args) < 3:
            # Set "temporary"
            self.args.append(False)

        # Special case: -- - input & load - --
        elif self.name.lower() in ('input', 'load'):
            ln = len(self.args)

            # Set upload data
            if 'upload_data' in kwargs.keys():
                self.upload_data = kwargs['upload_data']
            # Set upload schema
            if 'upload_schema' in kwargs.keys():
                # Pass through if provided as argument
                self.upload_schema = kwargs['upload_schema']
            else:
                # Try to infer upload schema from the first argument,
                # if present
                if self.name.lower() == 'input' and ln > 1:
                    try:
                        self.upload_schema = Schema.fromstring(args[0])
                    except:
                        pass

            # Set defaults if arguments are missing
            # Check if "format" is present (4th argument)
            if ln < 4:
                # Check if "instance_id" is present (3rd argument)
                if ln < 3:
                    # Check if "input_file" is present (2nd argument)
                    if ln < 2:
                        # Check if "existing_array|anonymous_schema"
                        # is present (1st argument)
                        if ln < 1:
                            self.args.append('{sch}')  # anonymous_schema
                        self.args.append("'{fn}'")     # input_file
                    self.args.append(0)                # instance_id
                self.args.append("'{fmt}'")            # format

        # Special case: -- - store - --
        elif self.name.lower() == 'store' and len(self.args) < 2:
            # Set "named_array"
            self.args.append(self.db.next_array_name())
            # Garbage collect (if not specified)
            if 'gc' not in kwargs.keys():
                kwargs['gc'] = True

        # Lazy or hungry
        if self.is_lazy:
            return self
        else:
            self.db.iquery(str(self),
                           upload_data=self.upload_data,
                           upload_schema=self.upload_schema)

            # Special case: -- - store - --
            if self.name.lower() == 'store':
                if isinstance(self.args[1], Array):
                    return self.args[1]
                else:
                    return Array(self.db,
                                 self.args[1],
                                 kwargs.get('gc', False))

    def __getitem__(self, key):
        return self.fetch()[key]

    def __getattr__(self, name):
        if name in self.db.operators:
            return Operator(
                self.db, name, self.upload_data, self.upload_schema, self)
        else:
            raise AttributeError(
                '{.__name__!r} object has no attribute {!r}'.format(
                    type(self), name))

    def __dir__(self):
        return self._dir

    def fetch(self, as_dataframe=False):
        if self.is_lazy:
            return self.db.iquery(str(self),
                                  fetch=True,
                                  as_dataframe=as_dataframe,
                                  upload_data=self.upload_data,
                                  upload_schema=self.upload_schema)
        else:
            None

connect = DB
iquery = DB.iquery


if __name__ == "__main__":
    # logging.basicConfig(level=logging.DEBUG)
    import doctest
    doctest.testmod(optionflags=doctest.REPORT_ONLY_FIRST_FAILURE)
