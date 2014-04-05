import sys

from . import SciDBArray
from .afldb import operators

mod = sys.modules[__name__]

__all__ = ['register_operator', 'AFLNamespace']


def _format_operand(o):
    """
    Format the input into a string
    approproate for use as an input to an AFLExpression call

    Parameters
    ----------
    o : AFLExpression, SciDBArray, number, or string
        The input to format

    Returns
    -------
    result : str
        The formatted string
    """

    # awkward: commands like list need their strings to be single-quoted
    #          for now, this has to be done manually
    if isinstance(o, basestring):
        return o

    if isinstance(o, AFLExpression):
        if o.cached_result is not None:
            return o.cached_result.name
        return o.query

    if isinstance(o, SciDBArray):
        return o.name

    return str(o)


class AFLExpression(object):
    _signature = []
    _interface = None

    def __init__(self, *args):
        self._check_arguments(args)
        self.args = args
        self._result = None

    def _check_arguments(self, args):
        if len(self._signature) == 0:
            return

        ngiven = len(args)
        exact = self._signature[-1] != 'args'
        nrequired = len(self._signature) - 1 + int(exact)

        if ngiven < nrequired:
            arg = "argument" if nrequired == 1 else "arguments"
            constraint = "exactly" if exact else "at least"
            name = self.name
            raise TypeError("{name}() takes {constraint} {nrequired} {arg} "
                            "({ngiven} given)".format(**locals()))

    @property
    def name(self):
        """
        The SciDB operator name, assumed to be the same as the class name
        """
        return self.__class__.__name__

    @property
    def interface(self):
        if self._interface is not None:
            return self._interface

        # look for an interface in arguments
        for a in self.args:
            try:
                return a.interface
            except AttributeError:
                pass

        raise AttributeError("Could not find an interface")

    @interface.setter
    def interface(self, value):
        self._interface = value

    @property
    def query(self):
        ops = map(_format_operand, self.args)
        q = "{function}({args})".format(function=self.name, args=','.join(ops))
        return q

    @property
    def cached_result(self):
        """
        Return the result if already evaluated, or None.

        Returns
        -------
        A SciDBArray instance, or None
        """
        return self._result

    def eval(self, out=None, store=True, **kwargs):
        """
        Evaluate the expression if necessary, and return the
        result as a SciDBArray.

        Parameters
        ----------
        out : SciDBArray instance (optional)
            The array to store the result in.
            One will be created if necessary

        store : bool
            If True (the default), the query will be
            wrapped in a store call, and wrapped in
            a SciDBAarray (specified by `out`). If
            false, this executes the query, but
            doesn't save the result

        Returns
        --------
        out : SciDBArray instance, or None

        Note
        ----
        The result of eval() is cached, so subsequent calls
        will not trigger additional database computation
        """
        if self._result is not None:
            return self._result

        if not store:
            return self.interface._execute_query(self.query, **kwargs)

        if out is None:
            out = self.interface.new_array()

        self._result = out
        self.interface._execute_query('store(%s, %s)' %
                                      (self.query, out.name))
        return self._result

    def toarray(self):
        return self.eval().toarray()

    def __str__(self):
        return self.query

    def __repr__(self):
        return "SciDB Expression: <%s>" % self


class BinaryInfixAFLOperator(AFLExpression):

    """
    Bindings to AFL scalar functions like +, -, etc.

    These Operators are called using the normal functional notation
    (e.g., ``add(X, 5)``), but their query strings expand to ``X + 5``

    Attributes
    ----------
    op : str
       The SciDB operator token (e.g., ``+``)
    """

    op = None

    @property
    def query(self):
        l, r = map(_format_operand, self.args)
        q = "({l} {op} {r})".format(l=l, op=self.op, r=r)
        return q


def register_operator(entry, interface=None):
    """
    Create a new AFL operator, based on a description dictionary

    Parameters
    ----------
    entry: dict with the following keys:
        - name : string giving the name of the operator
        - doc : docstring
        - signature : list giving the type of each argument

    interface : SciDBinterface instance
        Which SciDBinterface instance to bind the operator class to

    Returns
    --------
    A new AFLExpression subclass, representing the operator
    """
    name = str(entry['name'])
    doc = entry['doc']
    signature = entry['signature']

    attrs = {'__doc__': doc, '_signature': signature,
             '_interface': interface}
    result = type(name, (AFLExpression,), attrs)
    return result


def register_infix(name, op, interface=None):
    """
    Create a new BinaryInfixAFLOperator type

    Parameters
    ----------
    name : str
        Name of the class
    op : str
        SciDB operator name
    interface : SciDBInterface instance (optional)
        Which interface to bind to

    Returns
    -------
    A new subtype of BinaryInfixAFLOperator
    """
    doc = "The operator %s" % op
    signature = ['item', 'item']
    attrs = {'__doc__': doc, '_signature': signature,
             'op': op,
             '_interface': interface}
    return type(name, (BinaryInfixAFLOperator,), attrs)


class AFLNamespace(object):

    """
    A module-like namespace for all registered operators.
    """

    def __init__(self, interface):
        for op in operators:
            setattr(self, op['name'], register_operator(op, interface))

        for name, op in [('as_', 'as'), ('add', '+'),
                         ('sub', '-'), ('mul', '*'), ('div', '/'),
                         ('mod', '%')]:
            setattr(self, name, register_infix(name, op, interface))

    def papply(self, array, attr, expression):
        """
        papply(array, attr, expression)

        Shorthand for project(apply(array, attr, expression), attr)
        """
        return self.project(self.apply(array, attr, expression), attr)

    def quote(self, val):
        """Wrap the argument in single quotes.

        Useful for AFL operators which expected quoted strings
        """
        return "'%s'" % val


# add in some missing operators
# TODO add these to afldb.py
for op in ['gemm', 'gesvd', 'pow', 'abs']:
    operators.append(dict(name=op, signature=[], doc=''))


# build the functions and populate the namespace
for op in operators:
    setattr(mod, op['name'], register_operator(op))
    __all__.append(op['name'])
