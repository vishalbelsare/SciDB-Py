"""
Connect to SciDB
----------------

Connect to SciDB using "connect()" or "DB()":

>>> db = connect()
>>> db = DB()


Display information about the "db" object:

>>> db
DB('http://localhost:8080', None, None, None, None, None)

>>> print(db)
scidb_url  = 'http://localhost:8080'
scidb_auth = None
http_auth  = None
role       = None
namespace  = None
verify     = None


Provide Shim credentials:

>>> db_ha = connect(http_auth=('foo', 'bar'))

>>> db_ha
DB('http://localhost:8080', None, ('foo', PASSWORD_PROVIDED), None, None, None)

>>> print(db_ha)
scidb_url  = 'http://localhost:8080'
scidb_auth = None
http_auth  = ('foo', PASSWORD_PROVIDED)
role       = None
namespace  = None
verify     = None

To prompt the user for the password, use:

# >>> import getpass
# >>> db_ha = connect(http_auth=('foo', getpass.getpass()))
# Password:


Use SSL:

>>> db_ssl = connect('https://localhost:8083', verify=False)

>>> print(db_ssl)
scidb_url  = 'https://localhost:8083'
scidb_auth = None
http_auth  = None
role       = None
namespace  = None
verify     = False

See Python "requests" library SSL Cert Verification section [1] for
details on the "verify" parameter.

[1] http://docs.python-requests.org/en/master/user/advanced/
    #ssl-cert-verification


Use SSL and SciDB credentials:

>>> db_sdb = connect(
...   'https://localhost:8083', scidb_auth=('foo', 'bar'), verify=False)

>>> print(db_sdb)
scidb_url  = 'https://localhost:8083'
scidb_auth = ('foo', PASSWORD_PROVIDED)
http_auth  = None
role       = None
namespace  = None
verify     = False


Access SciDB Arrays
-------------------

Access SciDB arrays using "db.arrays":

>>> iquery(db, 'store(build(<x:int64>[i=0:2], i), foo)')

>>> dir(db.arrays)
... # doctest: +ELLIPSIS
[...'foo']

>>> dir(db.arrays.foo)
... # doctest: +ELLIPSIS
[...'i', ...'x']

>>> db.arrays.foo[:]
... # doctest: +NORMALIZE_WHITESPACE
array([(0, (255, 0)), (1, (255, 1)), (2, (255, 2))],
      dtype=[('i', '<i8'), ('x', [('null', 'u1'), ('val', '<i8')])])

>>> iquery(db, 'remove(foo)')

>>> dir(db.arrays)
[]

Arrays specified explicitly are not checked:

>>> print(db.arrays.foo)
foo
>>> print(db.arrays.bar)
bar

In IPython, you can use <TAB> for auto-completion of array names,
array dimensions, and array attributes:

# In []: db.arrays.<TAB>
# In []: db.arrays.foo
# In []: db.arrays.foo.<TAB>
# In []: db.arrays.foo.x


Use "iquery" function
---------------------

Use "iquery" to execute queries:

>>> iquery(db, 'store(build(<x:int64>[i=0:2], i), foo)')


Use "iquery" to download array data:

>>> iquery(db, 'scan(foo)', fetch=True)
... # doctest: +NORMALIZE_WHITESPACE
array([(0, (255, 0)), (1, (255, 1)), (2, (255, 2))],
      dtype=[('i', '<i8'), ('x', [('null', 'u1'), ('val', '<i8')])])

Optionally, download only the attributes:

>>> iquery(db, 'scan(foo)', fetch=True, atts_only=True)
... # doctest: +NORMALIZE_WHITESPACE
array([((255, 0),), ((255, 1),), ((255, 2),)],
      dtype=[('x', [('null', 'u1'), ('val', '<i8')])])

>>> iquery(db, 'remove(foo)')


Download operator output directly:

>>> iquery(db, 'build(<x:int64 not null>[i=0:2], i)', fetch=True)
... # doctest: +NORMALIZE_WHITESPACE
array([(0, 0), (1, 1), (2, 2)],
      dtype=[('i', '<i8'), ('x', '<i8')])

Optionally, download only the attributes:

>>> iquery(db,
...        'build(<x:int64 not null>[i=0:2], i)',
...        fetch=True,
...        atts_only=True)
... # doctest: +NORMALIZE_WHITESPACE
array([(0,), (1,), (2,)],
      dtype=[('x', '<i8')])


If dimension names collide with attribute names, unique dimension
names are created:

>>> iquery(db, 'apply(build(<x:int64 not null>[i=0:2], i), i, i)', fetch=True)
... # doctest: +NORMALIZE_WHITESPACE
array([(0, 0, 0), (1, 1, 1), (2, 2, 2)],
      dtype=[('i_1', '<i8'), ('x', '<i8'), ('i', '<i8')])


If schema is known, it can be provided to "iquery":

>>> iquery(db,
...        'build(<x:int64 not null>[i=0:2], i)',
...        fetch=True,
...        schema=Schema(None,
...                      (Attribute('x', 'int64', not_null=True),),
...                      (Dimension('i', 0, 2),)))
... # doctest: +NORMALIZE_WHITESPACE
array([(0, 0), (1, 1), (2, 2)],
      dtype=[('i', '<i8'), ('x', '<i8')])

>>> iquery(db,
...        'build(<x:int64 not null>[i=0:2], i)',
...        fetch=True,
...        atts_only=True,
...        schema=Schema.fromstring('<x:int64 not null>[i=0:2]'))
... # doctest: +NORMALIZE_WHITESPACE
array([(0,), (1,), (2,)],
      dtype=[('x', '<i8')])


Download as Pandas DataFrame:

>>> iquery(db,
...        'build(<x:int64>[i=0:2], i)',
...        fetch=True,
...        as_dataframe=True)
... # doctest: +NORMALIZE_WHITESPACE
   i x
0  0 0.0
1  1 1.0
2  2 2.0

>>> iquery(db,
...        'build(<x:int64>[i=0:2], i)',
...        fetch=True,
...        atts_only=True,
...        as_dataframe=True)
... # doctest: +NORMALIZE_WHITESPACE
   x
0  0.0
1  1.0
2  2.0

>>> iquery(db,
...        'build(<x:int64>[i=0:2], i)',
...        fetch=True,
...        atts_only=True,
...        as_dataframe=True,
...        dataframe_promo=False)
... # doctest: +NORMALIZE_WHITESPACE
   x
0  (255, 0)
1  (255, 1)
2  (255, 2)


Upload to SciDB
---------------

>>> import numpy

>>> db.iquery_upload("store(input(<x:int64>[i], '{}', 0, '(int64)'), foo)",
...                  numpy.arange(3).tobytes())

>>> db.arrays.foo[:]
... # doctest: +NORMALIZE_WHITESPACE
array([(0, (255, 0)), (1, (255, 1)), (2, (255, 2))],
      dtype=[('i', '<i8'), ('x', [('null', 'u1'), ('val', '<i8')])])

>>> db.iquery_upload("insert(input(foo, '{}', 0, '(int64)'), foo)",
...                  numpy.arange(3).tobytes())

>>> db.iquery_upload("load(foo, '{}', 0, '(int64)')",
...                  numpy.arange(3).tobytes())

>>> db.iquery_upload("load(foo, '{}', 0, '(int64 null)')",
...                  numpy.arange(3),
...                  Schema.fromstring('<x:int64>[i]'))

>>> db.remove(db.arrays.foo)


Use SciDB Operators
-------------------

>>> dir(db)
... # doctest: +NORMALIZE_WHITESPACE +ELLIPSIS
[...'aggregate',
 ...'apply',
 ...
 ...'xgrid']

>>> db.apply
... # doctest: +NORMALIZE_WHITESPACE
SciDB(db=DB('http://localhost:8080', None, None, None, None, None),
      operator='apply', args=[])

>>> print(db.apply)
apply()

>>> db.missing
Traceback (most recent call last):
    ...
AttributeError: 'DB' object has no attribute 'missing'

In IPython, you can use <TAB> for auto-completion of operator names:

# In []: db.<TAB>
# In []: db.apply

>>> db.create_array('foo', '<x:int64>[i]')
>>> dir(db.arrays)
... # doctest: +ELLIPSIS
[...'foo']

>>> db.remove(db.arrays.foo)
>>> dir(db.arrays)
[]

>>> db.build('<x:int8 not null>[i=0:2]', 'i + 10')[:]
... # doctest: +NORMALIZE_WHITESPACE
array([(0, 10), (1, 11), (2, 12)],
      dtype=[('i', '<i8'), ('x', 'i1')])

>>> db.build('<x:int8 not null>[i=0:2]', 'i + 10').fetch(as_dataframe=True)
   i   x
0  0  10
1  1  11
2  2  12

>>> db.build('<x:int8 not null>[i=0:2]', 'i + 10').apply('y', 'x - 5')[:]
... # doctest: +NORMALIZE_WHITESPACE
array([(0, 10, 5), (1, 11, 6), (2, 12, 7)],
      dtype=[('i', '<i8'), ('x', 'i1'), ('y', '<i8')])


>>> db.build('<x:int8 not null>[i=0:2]', 'i + 10').store('foo')

>>> db.scan(db.arrays.foo)[:]
... # doctest: +NORMALIZE_WHITESPACE
array([(0, 10), (1, 11), (2, 12)],
      dtype=[('i', '<i8'), ('x', 'i1')])

>>> db.apply(db.arrays.foo, 'y', db.arrays.foo.x + 1)[:]
... # doctest: +NORMALIZE_WHITESPACE
array([(0, 10, 11), (1, 11, 12), (2, 12, 13)],
      dtype=[('i', '<i8'), ('x', 'i1'), ('y', '<i8')])

>>> db.remove(db.arrays.foo)

"""

import copy
import enum
import itertools
import logging
import numpy
import pandas
import re
import requests

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
            scidb_url='http://localhost:8080',
            scidb_auth=None,
            http_auth=None,
            role=None,
            namespace=None,
            verify=None):
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

        self.operators = self.iquery_readlines(
            "project(list('operators'), name)")
        self._dir = (self.operators +
                     ['arrays', 'iquery', 'iquery_readlines'])
        self._dir.sort()

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
            return SciDB(self, name)
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
               schema=None):
        """Execute query in SciDB

        :param bool fetch: If `True`, download SciDB array (default
        `False`)

        :param bool atts_only: If `True`, download only SciDB array
        attributes without dimensions (default `False`)

        :param bool as_dataframe: If `True`, return a Pandas
        DataFrame. If `False`, return a NumPy array (default `False`)

        :param bool dataframe_promo: If `True`, nullable types are
        promoted as per Pandas promotion scheme
        http://pandas.pydata.org/pandas-docs/stable/gotchas.html
        #na-type-promotions If `False`, object records are used for
        nullable types (default `True`)

        :param schema: Schema of the SciDB array to use when
        downloading the array. Schema is not verified. If schema is a
        Schema instance, it is copied. Otherwise, a :py:class:`Schema`
        object is built using :py:func:`Schema.fromstring` (default
        `None`).

        >>> DB().iquery('build(<x:int64>[i=0:1; j=0:1], i + j)', fetch=True)
        ... # doctest: +NORMALIZE_WHITESPACE
        array([(0, 0, (255, 0)),
               (0, 1, (255, 1)),
               (1, 0, (255, 1)),
               (1, 1, (255, 2))],
              dtype=[('i', '<i8'), ('j', '<i8'),
                     ('x', [('null', 'u1'), ('val', '<i8')])])

        """
        id = self._shim(Shim.new_session).text

        if fetch:
            # Use provided schema or get schema from SciDB
            if schema:
                # Deep-copy schema since we might be mutating it
                if isinstance(schema, Schema):
                    sch = copy.deepcopy(schema)
                else:
                    sch = Schema.fromstring(schema)
            else:
                # Execute 'show(...)' and Download text
                self._shim(
                    Shim.execute_query,
                    id=id,
                    query=DB._show_query.format(query.replace("'", "\\'")),
                    save='tsv')
                sch = Schema.fromstring(
                    self._shim(Shim.read_bytes, id=id, n=0).text)
                logging.debug(sch)

            # Unpack
            if not atts_only:
                if sch.make_dims_unique():
                    # Dimensions renamed due to collisions. Need to
                    # cast.
                    query = 'cast({}, {:h})'.format(query, sch)

                query = 'project(apply({}, {}), {})'.format(
                    query,
                    ', '.join('{0}, {0}'.format(d.name) for d in sch.dims),
                    ', '.join(i.name for i in itertools.chain(
                        sch.dims, sch.atts)))

                sch.make_dims_atts()
                logging.debug(query)
                logging.debug(sch)

            # Execute Query and Download content
            self._shim(Shim.execute_query,
                       id=id,
                       query=query,
                       save=sch.atts_fmt_scidb)
            buf = self._shim(Shim.read_bytes, id=id, n=0).content

            self._shim(Shim.release_session, id=id)

            # Scan content and build (offset, size) metadata
            off = 0
            buf_meta = []
            while off < len(buf):
                meta = []
                for att in sch.atts:
                    sz = att.itemsize(buf, off)
                    meta.append((off, sz))
                    off += sz
                buf_meta.append(meta)

            # Create NumPy record array
            if as_dataframe and dataframe_promo:
                ar = numpy.empty((len(buf_meta),),
                                 dtype=sch.get_promo_atts_dtype())
            else:
                ar = numpy.empty((len(buf_meta),), dtype=sch.atts_dtype)

            # Extract values using (offset, size) metadata
            # Populate NumPy record array
            pos = 0
            for meta in buf_meta:
                ar.put((pos,),
                       tuple(att.frombytes(
                           buf,
                           off,
                           sz,
                           promo=as_dataframe and dataframe_promo)
                             for (att, (off, sz)) in zip(sch.atts, meta)))
                pos += 1

            # Return NumPy array or Pandas dataframe
            if as_dataframe:
                return pandas.DataFrame.from_records(ar)
            else:
                return ar

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
        ret = [line.split('\t') if '\t' in line else line
               for line in self._shim(
                       Shim.read_bytes, id=id, n=0).text.splitlines()]
        self._shim(Shim.release_session, id=id)
        return ret

    def iquery_upload(self, query, values, schema=None):
        """Upload data and execute query with file name argument in SciDB
        """
        id = self._shim(Shim.new_session).text

        if isinstance(values, numpy.ndarray):
            if schema is None:
                raise Exception('Schema is needed for NumPy arrays')

            no_v = len(values.dtype)
            no_a = len(schema.atts_dtype)
            if not(no_v == 0 and no_a == 1 or
                   no_v == no_a):
                raise Exception(
                    ('Number of values ({}) is different than ' +
                     'number of attributes ({})').format(no_v, no_a))

            data_lst = []
            for cell in values:
                for (atr, idx) in zip(schema.atts, range(len(schema.atts))):
                    data_lst.append(
                        atr.tobytes(cell if no_v == 0 else cell[idx]))

            data = b''.join(data_lst)
        else:
            data = values

        fn = self._shim(Shim.upload, id=id, data=data).text
        self._shim(
            Shim.execute_query, id=id, query=query.format(fn), release=1)

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
    def __init__(self, db, name):
        self.db = db
        self.name = name

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


class SciDB(object):
    """Unevaluated SciDB expression"""
    def __init__(self, db, operator, *args):
        self.db = db
        self.operator = operator

        self.args = list(args)
        self.is_lazy = self.operator.lower() not in (
            'create_array',
            'remove',
            'store',
        )

        self._dir = self.db.operators + ['fetch']
        self._dir.sort()

    def __repr__(self):
        return '{}(db={!r}, operator={!r}, args=[{}])'.format(
            type(self).__name__,
            self.db,
            self.operator,
            ', '.join('{!r}'.format(i) for i in self.args))

    def __str__(self):
        args_fmt_scidb = ('{}'.format(i) for i in self.args)
        return '{}({})'.format(self.operator, ', '.join(args_fmt_scidb))

    def __call__(self, *args):
        """Returns self for lazy expressions. Executes immediate expressions.
        """
        self.args.extend(args)

        if self.operator.lower().startswith('create_array') \
           and len(self.args) < 3:
            # Set temporary = False for create array
            self.args.append(False)

        if self.is_lazy:
            return self
        else:
            return self.db.iquery(str(self))

    def __getitem__(self, key):
        return self.fetch()[key]

    def __getattr__(self, name):
        if name in self.db.operators:
            return SciDB(self.db, name, self)
        else:
            raise AttributeError(
                '{.__name__!r} object has no attribute {!r}'.format(
                    type(self), name))

    def __dir__(self):
        return self._dir

    def fetch(self, as_dataframe=False):
        if self.is_lazy:
            return self.db.iquery(
                str(self), fetch=True, as_dataframe=as_dataframe)
        else:
            None

connect = DB
iquery = DB.iquery


if __name__ == "__main__":
    # logging.basicConfig(level=logging.DEBUG)
    import doctest
    doctest.testmod(optionflags=doctest.REPORT_ONLY_FIRST_FAILURE)
