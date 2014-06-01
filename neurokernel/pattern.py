#!/usr/bin/env python

"""
Represent connectivity pattern using pandas DataFrame.
"""

from collections import OrderedDict
import itertools
import networkx as nx
import numpy as np
import pandas as pd

from plsel import PathLikeSelector

class Interface(object):
    """
    Container for set of interface comprising ports.

    This class contains information about a set of interfaces comprising 
    path-like identifiers [1]_ and the attributes associated with them. By
    default, each port must have at least the following attributes; other 
    attributes may be added:
    
    * interface - indicates which interface a port is associated with.
    * io - indicates whether the port receives input ('in') or emits output ('out').
    * type - indicates whether the port emits/receives spikes or graded potentials.

    Examples
    --------
    >>> i = Interface('/foo[0:4],/bar[0:3]')
    >>> i['/foo[0:2]', 'interface', 'io', 'type'] = [0, 'in', 'spike']
    >>> i['/foo[2:4]', 'interface', 'io', 'type'] = [1, 'out', 'spike']

    Attributes
    ----------
    data : pandas.DataFrame
        Port attribute data.
    index : pandas.MultiIndex
        Index of port identifiers.
    interface_ids : int
        Interface identifiers.

    Parameters
    ----------
    selector : str, unicode, or sequence
            Selector string (e.g., '/foo[0:2]') or sequence of token sequences
            (e.g., [['foo', (0, 2)]]) describing the port identifiers comprised 
            by the interface.
    columns : list, default = ['interface', 'io', 'type']
        Data column names.

    Methods
    -------
    as_selectors(ids)
        Convert list of port identifiers to path-like selectors. 
    data_select(f, inplace=False)
        Restrict Interface data with a selection function.
    from_df(df)
        Create an Interface from a properly formatted DataFrame.
    from_dict(d)
        Create an Interface from a dictionary of selectors and data values.
    in_interfaces(s)
        Check whether a selector is supported by any stored interface.
    in_ports(i)
        List of input port identifiers as tuples comprised by an interface.
    get_interface(i)
        Return specified interface as an Interface instance.
    is_compatible(a, i, b)
        Check whether two interfaces can be connected.
    out_ports(i)
        List of output port identifiers as tuples comprised by an interface.
    port_select(f, inplace=False)
        Restrict Interface ports with a selection function.
    ports(i)
        List of port identifiers as tuples comprised by an interface.
    which_int(s)
        Return identifier(s) of interface(s) containing specified selector.

    See Also
    --------
    .. [1] PathLikeSelector
    """

    def __init__(self, selector='', columns=['interface', 'io', 'type']):
        
        # All ports in an interface must contain at least the following
        # attributes:
        assert set(columns).issuperset(['interface', 'io', 'type'])
        self.sel = PathLikeSelector()
        assert not(self.sel.is_ambiguous(selector))
        self.num_levels = self.sel.max_levels(selector)
        names = [str(i) for i in xrange(self.num_levels)]
        idx = self.sel.make_index(selector, names)
        self.__validate_index__(idx)
        self.data = pd.DataFrame(index=idx, columns=columns)

    def __validate_index__(self, idx):
        """
        Raise an exception if the specified index will result in an invalid interface.
        """
        
        if (hasattr(idx, 'has_duplicates') and idx.has_duplicates) or \
           len(idx.unique()) < len(idx):
            raise ValueError('Duplicate interface index entries detected.')

    def __getitem__(self, key):
        if type(key) == tuple and len(key) > 1:
            return self.sel.select(self.data[list(key[1:])], key[0])
        else:
            return self.sel.select(self.data, key)
        
    def __setitem__(self, key, value):
        if type(key) == tuple:
            selector = key[0]
        else:
            selector = key

        # Try using the selector to select data from the internal DataFrame:
        try:
            idx = self.sel.get_index(self.data, selector,
                                     names=self.data.index.names)

        # If the select fails, try to create new rows with the index specified
        # by the selector and load them with the specified data:
        except:
            try:
                idx = self.sel.make_index(selector, self.data.index.names)
            except:
                raise ValueError('cannot create new rows for ambiguous selector %s' % selector)
            else:
                found = False
        else:
            found = True

        # If the data specified is not a dict, convert it to a dict:
        if type(key) == tuple and len(key) > 1:
            if np.isscalar(value):
                data = {k:value for k in key[1:]}
            elif type(value) == dict:
                data = value
            elif np.iterable(value) and len(value) <= len(key[1:]):
                data={k:v for k, v in zip(key[1:], value)}
            else:
                raise ValueError('cannot assign specified value')
        else:
            if np.isscalar(value):
                data = {self.data.columns[0]: value}
            elif type(value) == dict:
                data = value
            elif np.iterable(value) and len(value) <= len(self.data.columns):
                data={k:v for k, v in zip(self.data.columns, value)}
            else:
                raise ValueError('cannot assign specified value')

        if found:
            for k, v in data.iteritems():
                self.data[k].ix[idx] = v
        else:
            self.data = self.data.append(pd.DataFrame(data=data, index=idx))
            self.data.sort(inplace=True)

    @property
    def index(self):
        """
        Interface index.
        """

        return self.data.index
    @index.setter
    def index(self, i):
        self.data.index = i

    @property
    def interface_ids(self):
        """
        Interface identifiers.
        """
        
        return set(self.data['interface'])

    @classmethod
    def as_selectors(cls, ids):
        """
        Convert list of port identifiers to path-like selectors.

        Parameters
        ----------
        ids : list of tuple
            Port identifiers.

        Returns
        -------
        selectors : list of str
            List of selector strings corresponding to each port identifier.
        """

        result = []
        for t in ids:
            selector = ''
            for s in t:
                if type(s) == str:
                    selector += '/'+s
                else:
                    selector += '[%s]' % s
            result.append(selector)
        return result

    def data_select(self, f, inplace=False):
        """
        Restrict Interface data with a selection function.

        Returns an Interface instance containing only those rows
        whose data is passed by the specified selection function.

        Parameters
        ----------
        f : function
            Selection function with a single dict argument whose keys
            are the Interface's data column names.
        inplace : bool, default=False
            If True, update and return the given Interface instance.
            Otherwise, return a new instance.

        Returns
        -------
        i : Interface
            Interface instance containing data selected by `f`.
        """

        assert callable(f)
        result = self.data[f(self.data)]
        if inplace:
            self.data = result
            return self
        else:
            return Interface.from_df(result)

    @classmethod
    def from_dict(cls, d):
        """
        Create an Interface from a dictionary of selectors and data values.

        Examples
        --------
        >>> d = {'/foo[0]': [0, 'in'], '/foo[1]': [1, 'out']}
        >>> i = Interface.from_dict(d)
        
        Parameters
        ----------
        d : dict
            Dictionary that maps selectors to the data that should be associated
            with the corresponding ports. If a scalar, the data is assigned to
            the first attribute; if an iterable, the data is assigned to the
            attributes in order.;
        
        Returns
        -------
        i : Interface
            Generated interface instance.
        """

        # XX verify that this works
        i = cls(','.join(d.keys()))
        for k, v in d.iteritems():
            i[k] = v
        i.data.sort_index(inplace=True)
        return i

    @classmethod
    def from_df(cls, df):
        """
        Create an Interface from a properly formatted DataFrame.
        
        Examples
        --------
        >>> import plsel
        >>> import pandas
        >>> idx = plsel.make_index('/foo[0:2]')
        >>> data = [[0, 'in', 'spike'], [1, 'out', 'gpot']]
        >>> columns = ['interface', 'io', 'type']
        >>> df = pandas.DataFrame(data, index=idx, columns=columns)

        Parameters
        ----------
        df : pandas.DataFrame
            DataFrame with a MultiIndex and data columns 'interface', 
            'io', and 'type' (additional columns may also be present).

        Returns
        -------
        i : Interface
            Generated Interface instance.

        Notes
        -----
        The contents of the specified DataFrame instance are copied into the
        new Interface instance.
        """
        
        assert isinstance(df.index, pd.MultiIndex)
        assert set(df.columns).issuperset(['interface', 'io', 'type'])
        cls.__validate_index__(df.index)

        i = cls(df.index.tolist(), df.columns)
        i.data = df.copy()
        return i

    def in_interfaces(self, s):
        """
        Check whether ports comprised by a selector are in the stored interfaces.
        
        Parameters
        ----------
        s : str or unicode
            Port selector.

        Returns
        -------
        result : bool
            True if the comprised ports are in any of the stored interfaces.
        """

        return self.sel.is_in(s, self.index.tolist())

    def is_compatible(self, a, i, b):
        """
        Check whether two interfaces can be connected.

        Compares an interface in the current Interface instance with one in
        another instance to determine whether their ports can be connected.

        Parameters
        ----------
        a : int
            Identifier of interface in the current instance.
        i : Interface
            Interface instance containing the other interface.
        b : int
            Identifier of interface in instance `i`.

        Returns
        -------
        result : bool
            True if both interfaces comprise the same identifiers
            and each identifier with an 'io' attribute set to 'out' in one
            interface has its 'io' attribute set to 'in' in the other interface.

        Notes
        -----
        All ports in both interfaces must have set 'io' attributes.
        """

        assert isinstance(i, Interface)
        if not set(self.data['io'].values).issubset(['in', 'out']) or \
           not set(i.data['io'].values).issubset(['in', 'out']):
            raise ValueError("All ports must have their 'io' attribute set.")

        # Find inverse of this instance's 'io' attributes for interface 'a':
        inv = self.data[self.data['interface'] == a].applymap(lambda x: 'out' \
                        if x == 'in' else ('in' if x == 'out' else x))

        # Compare indices:
        idx_a = self.data[self.data['interface'] == a].index
        idx_b = i.data[i.data['interface'] == b].index
        if idx_a.equals(idx_b) and \
           all(inv['io'] == i.data[i.data['interface'] == b]['io']):
            return True
        else:
            return False

    def in_ports(self, i=0):
        """
        List of input port identifiers as tuples comprised by an interface.

        Parameters
        ----------
        i : int
            Interface identifier.

        Returns
        -------
        p : list
            List of port identifiers as tuples of tokens.
        """

        try:
            return self.data[(self.data['io'] == 'in') & \
                             (self.data['interface'] == i)].index.tolist()
        except:
            return []

    def get_interface(self, i=0):
        """
        Return specified interface as an Interface instance.

        Parameters
        ----------
        i : int
            Interface identifier.

        Returns
        -------
        interface : Interface
            Interface instance containing all ports and attributes in the
            specified interface.
        """

        return self.from_df(self.data[self.data['interface'] == i])

    def out_ports(self, i=0):
        """
        List of output port identifiers as tuples comprised by an interface.

        Parameters
        ----------
        i : int
            Interface identifier.

        Returns
        -------
        p : list
            List of port identifiers as tuples of tokens.
        """

        try:
            return self.data[(self.data['io'] == 'out') & \
                             (self.data['interface'] == i)].index.tolist()
        except:
            return []

    def port_select(self, f, inplace=False):
        """
        Restrict Interface ports with a selection function.

        Returns an Interface instance containing only those rows
        whose ports are passed by the specified selection function.

        Parameters
        ----------
        f : function
            Selection function with a single tuple argument containing
            the various columns of the Interface instance's MultiIndex.
        inplace : bool, default=False
            If True, update and return the given Interface instance.
            Otherwise, return a new instance.

        Returns
        -------
        i : Interface
            Interface instance containing ports selected by `f`.
        """

        assert callable(f)
        if inplace:
            self.data = self.data.select(f)
            return self
        else:
            return Interface.from_df(self.data.select(f))

    def ports(self, i=0):
        """
        List of port identifiers as tuples comprised by an interface.

        Parameters
        ----------
        i : int
            Interface identifier.

        Returns
        -------
        p : list
            List of port identifiers as tuples of tokens.
        """

        try:
            return self.data[self.data['interface'] == i].index.tolist()
        except:
            return []
    
    def which_int(self, s):
        """
        Return the interface containing the identifiers comprised by a selector.

        Parameters
        ----------
        selector : str or unicode
            Port selector.

        Returns
        -------
        i : set
            Set of identifiers for interfaces that contain ports comprised by
            the selector.
        """
        
        try:
            s = set(self[s, 'interface'].values.flatten())

            # Ignore unset entries:
            s.discard(np.nan)
            return s
        except KeyError:
            return set()

    def __len__(self):
        return self.data.__len__()

    def __repr__(self):
        return 'Interface\n---------\n'+self.data.__repr__()

class Pattern(object):
    """
    Connectivity pattern linking sets of interface ports.

    This class represents connection mappings between interfaces comprising sets
    of ports. Ports are represented using path-like identifiers [1]_; the
    presence of a row linking the two identifiers in the class' internal index
    indicates the presence of a connection. A single data attribute ('conn')
    associated with defined connections is created by default. Specific
    attributes may be accessed by specifying their names after the port
    identifiers; if a nonexistent attribute is specified when a sequential value
    is assigned, a new column for that attribute is automatically created: ::

        p['/x[0:3]', '/y[0:2]', 'conn', 'x'] = [1, 'foo']

    The direction of connections between ports in a class instance determines 
    whether they are input or output ports.

    Examples
    --------
    >>> p = Pattern('/x[0:3]','/y[0:2]')
    >>> p['/x[0:2]', '/y[0]'] = 1
    >>> p['/y[0:2]', '/x[1]'] = 1

    Attributes
    ----------
    data : pandas.DataFrame
        Connection attribute data.
    index : pandas.MultiIndex
        Index of connections.
    interface : Interface
        Interfaces containing port identifiers and attributes.
    interface_ids : set
        Set of interface identifiers.

    Parameters
    ----------
    sel0, sel1, ...: str
        Selectors defining the sets of ports potentially connected by the 
        pattern. These selectors must be disjoint, i.e., no identifier 
        comprised by one selector may be in any other selector.
    columns : sequence of str
        Data column names.

    Methods
    -------
    clear()
        Clear all connections in class instance.
    dest_idx(src_int, dest_int, src_ports=None)
        Retrieve destination ports connected to the specified source ports.
    from_concat(*selectors, **kwargs)
        Create pattern from the concatenation of identifers comprised by two selectors.
    from_csv(file_name, **kwargs)
        Read connectivity data from CSV file.
    from_product(*selectors, **kwargs)
        Create pattern from the product of identifiers comprised by two selectors.
    get_interface(i)
        Return specified interface as an Interface instance.
    in_interfaces(selector)
        Check whether a selector is supported by any of the pattern's interfaces.
    is_connected(from_int, to_int)
        Check whether the specified interfaces are connected.
    src_idx(src_int, dest_int, dest_ports=None)
        Retrieve source ports connected to the specified destination ports.
    which_int(s)
        Return identifier(s) of interface(s) containing specified selector.

    See Also
    --------
    .. [1] PathLikeSelector

    """

    def __init__(self, *selectors, **kwargs):
        columns = kwargs['columns'] if kwargs.has_key('columns') else ['conn']
        self.sel = PathLikeSelector()

        # Force sets of identifiers to be disjoint so that no identifier can
        # denote a port in more than one set:
        assert self.sel.are_disjoint(selectors)

        # Collect all of the selectors:
        selector = []
        for s in selectors:
            selector.extend(self.sel.parse(s))

        # Create Interface instance containing the ports comprised by all of the
        # specified selectors:
        self.interface = Interface(selector)

        # Set the interface identifiers associated with each of the selectors
        # consecutively:
        for i, s in enumerate(selectors):
            self.interface[s, 'interface'] = i

        # Create a MultiIndex that can store mappings between identifiers in the
        # two interfaces:
        self.num_levels = {'from': self.interface.num_levels,
                           'to': self.interface.num_levels}
        names = ['from_%s' % i for i in xrange(self.num_levels['from'])]+ \
                ['to_%s' %i for i in xrange(self.num_levels['to'])]
        levels = [[] for i in xrange(len(names))]
        labels = [[] for i in xrange(len(names))]
        idx = pd.MultiIndex(levels=levels, labels=labels, names=names)
                            
        self.data = pd.DataFrame(index=idx, columns=columns)

    @property
    def from_slice(self):
        """
        Slice of pattern index row corresponding to source port(s).
        """

        return slice(0, self.num_levels['from'])

    @property
    def to_slice(self):
        """
        Slice of pattern index row corresponding to destination port(s).
        """

        return slice(self.num_levels['from'],        
                     self.num_levels['from']+self.num_levels['to'])

    @property
    def index(self):
        """
        Pattern index.
        """

        return self.data.index
    @index.setter
    def index(self, i):
        self.data.index = i

    @property
    def interface_ids(self):
        """
        Interface identifiers.
        """

        return self.interface.interface_ids

    @classmethod
    def _create_from(cls, *selectors, **kwargs):
        """
        Create a Pattern instance from the specified selectors.

        Parameters
        ----------
        sel0, sel1, ...: str
            Selectors defining the sets of ports potentially connected by the 
            pattern. These selectors must be disjoint, i.e., no identifier comprised
            by one selector may be in any other selector.   
        from_sel, to_sel : str
            Selectors that describe the pattern's initial index. If specified, 
            both selectors must be set. If no selectors are set, the index is
            initially empty.
        data : numpy.ndarray, dict, or pandas.DataFrame
            Data to load store in class instance.
        columns : sequence of str
            Data column names.
        comp_op : str
            Operator to use to combine selectors into single selector that
            comprises both the source and destination ports in a pattern.
        
        Returns
        -------
        result : Pattern
            Pattern instance.
        """

        from_sel = kwargs['from_sel'] if kwargs.has_key('from_sel') else None
        to_sel = kwargs['to_sel'] if kwargs.has_key('to_sel') else None
        data = kwargs['data'] if kwargs.has_key('data') else None
        columns = kwargs['columns'] if kwargs.has_key('columns') else ['conn']
        comb_op = kwargs['comb_op'] if kwargs.has_key('comb_op') else '+'

        # Create empty pattern:
        p = cls(*selectors, columns=columns)

        # Construct index from concatenated selectors if specified:
        names = p.data.index.names
        if (from_sel is None and to_sel is None):
            levels = [[] for i in xrange(len(names))]
            labels = [[] for i in xrange(len(names))]
            idx = pd.MultiIndex(levels=levels, labels=labels, names=names)
        else:
            idx = p.sel.make_index('(%s)%s(%s)' % (from_sel, comb_op, to_sel), names)
                                   
        # Replace the pattern's DataFrame:
        p.data = pd.DataFrame(data=data, index=idx, columns=columns)

        # Update the `io` attributes of the pattern's interfaces:
        p.interface[from_sel, 'io'] = 'in'
        p.interface[to_sel, 'io'] = 'out'

        return p

    @classmethod
    def from_product(cls, *selectors, **kwargs):
        """
        Create pattern from the product of identifiers comprised by two selectors.

        For example: ::

            p = Pattern.from_product('/foo[0:2]', '/bar[0:2]',
                                    from_sel='/foo[0:2]', to_sel='/bar[0:2]',
                                    data=1)

        results in a pattern with the following connections: ::

            '/foo[0]' -> '/bar[0]'
            '/foo[0]' -> '/bar[1]'
            '/foo[1]' -> '/bar[0]'
            '/foo[1]' -> '/bar[1]'

        Parameters
        ----------
        sel0, sel1, ...: str
            Selectors defining the sets of ports potentially connected by the 
            pattern. These selectors must be disjoint, i.e., no identifier comprised
            by one selector may be in any other selector.   
        from_sel, to_sel : str
            Selectors that describe the pattern's initial index.
        data : numpy.ndarray, dict, or pandas.DataFrame
            Data to load store in class instance.
        columns : sequence of str
            Data column names.

        Returns
        -------
        result : Pattern
            Pattern instance.
        """

        from_sel = kwargs['from_sel'] if kwargs.has_key('from_sel') else None
        to_sel = kwargs['to_sel'] if kwargs.has_key('to_sel') else None
        data = kwargs['data'] if kwargs.has_key('data') else None
        columns = kwargs['columns'] if kwargs.has_key('columns') else ['conn']
        return cls._create_from(*selectors, from_sel=from_sel, to_sel=to_sel, 
                                data=data, columns=columns, comb_op='+')

    def get_interface(self, i=0):
        return self.interface.get_interface(i)
    get_interface.__doc__ = Interface.get_interface.__doc__

    @classmethod
    def from_concat(cls, *selectors, **kwargs):
        """
        Create pattern from the concatenation of identifers comprised by two selectors.

        For example: ::

            p = Pattern.from_concat('/foo[0:2]', '/bar[0:2]',
                                    from_sel='/foo[0:2]', to_sel='/bar[0:2]',
                                    data=1)

        results in a pattern with the following connections: ::

            '/foo[0]' -> '/bar[0]'
            '/foo[1]' -> '/bar[1]'

        Parameters
        ----------
        data : numpy.ndarray, dict, or pandas.DataFrame
            Data to load store in class instance.
        from_sel, to_sel : str
            Selectors that describe the pattern's initial index. If specified,
            both selectors must be set. If no selectors are set, the index is
            initially empty.
        columns : sequence of str
            Data column names.

        Returns
        -------
        result : Pattern
            Pattern instance.
        """

        from_sel = kwargs['from_sel'] if kwargs.has_key('from_sel') else None
        to_sel = kwargs['to_sel'] if kwargs.has_key('to_sel') else None
        data = kwargs['data'] if kwargs.has_key('data') else None
        columns = kwargs['columns'] if kwargs.has_key('columns') else ['conn']
        return cls._create_from(*selectors, from_sel=from_sel, to_sel=to_sel, 
                                data=data, columns=columns, comb_op='.+')

    def __validate_index__(self, idx):
        """
        Raise an exception if the specified index will result in an invalid pattern.
        """

        # Prohibit duplicate connections:
        if (hasattr(idx, 'has_duplicates') and idx.has_duplicates) or \
           len(idx.unique()) < len(idx):
            raise ValueError('Duplicate pattern entries detected.')
            
        # Prohibit fan-in connections (i.e., patterns whose index has duplicate
        # 'from' port identifiers):
        from_idx, to_idx = self.split_multiindex(idx, 
                                                 self.from_slice, self.to_slice)
        if (hasattr(to_idx, 'has_duplicates') and to_idx.has_duplicates) or \
           len(to_idx.unique()) < len(to_idx):
            raise ValueError('Fan-in pattern entries detected.')

    def which_int(self, s):
        return self.interface.which_int(s)
    which_int.__doc__ = Interface.which_int.__doc__

    def in_interfaces(self, selector):
        """
        Check whether a selector is supported by any stored interface.
        """

        if len(self.interface[selector]) > 0:
            return True
        else:
            return False

    def get_conns(self, as_str=False):
        """
        Return connections as pairs of port identifiers.
        
        Parameters
        ----------
        as_str : bool
            If True, return connections as a list of identifier
            string pairs. Otherwise, return them as pairs of token tuples.
        """

        if as_str:
            return [(self.sel.to_identifier(row[self.from_slice]),
                     self.sel.to_identifier(row[self.to_slice])) \
                    for row in self.data.index]
        else:
            return [(row[self.from_slice], row[self.to_slice]) \
                    for row in self.data.index]

    def __setitem__(self, key, value):
        # XXX attempting to create an index row that appears both in the 'from'
        # and 'to' sections of the pattern's index should raise an exception
        # because ports cannot both receive input and send output.
        
        # XXX attempting to create an index row that causes multiple source
        # ports to map to a single destination port should raise an exception
        # because Neurokernel's patterns should only permit fan-out but not
        # fan-in.

        # Must pass more than one argument to the [] operators:
        assert type(key) == tuple

        # Ensure that specified selectors refer to ports in the
        # pattern's interfaces:
        assert self.in_interfaces(key[0])
        assert self.in_interfaces(key[1])
        
        # Ensure that the ports are in different interfaces:
        assert self.which_int(key[0]) != self.which_int(key[1])

        # Try using the selector to select data from the internal DataFrame:
        selector = '+'.join(key[0:2])
        try:
            idx = self.sel.get_index(self.data, selector,
                                     names=self.data.index.names)
        
        # If the select fails, try to create new rows with the index specified
        # by the selector and load them with the specified data:
        except:
            try:
                idx = self.sel.make_index(selector, self.data.index.names)
            except:
                raise ValueError('cannot create new rows for ambiguous selector %s' % selector)
            else:
                found = False
        else:
            found = True

        # Update the `io` attributes of the pattern's interfaces:
        self.interface[key[0], 'io'] = 'in'
        self.interface[key[1], 'io'] = 'out'

        # Ensure that data to set is in dict form:
        if len(key) > 2:
            if np.isscalar(value):
                data = {k:value for k in key[2:]}
            elif type(value) == dict:
                data = value
            elif np.iterable(value) and len(value) <= len(key[2:]):
                data={k:v for k, v in zip(key[2:], value)}
            else:
                raise ValueError('cannot assign specified value')
        else:
            if np.isscalar(value):
                data = {self.data.columns[0]: value}
            elif type(value) == dict:
                data = value
            elif np.iterable(value) and len(value) <= len(self.data.columns):
                data={k:v for k, v in zip(self.data.columns, value)}
            else:
                raise ValueError('cannot assign specified value')

        # If the specified selectors correspond to existing entries, 
        # set their attributes:
        if found:
            for k, v in data.iteritems():
                self.data[k].ix[idx] = v

        # Otherwise, populate a new DataFrame with the specified attributes:
        else:
            self.data = self.data.append(pd.DataFrame(data=data, index=idx))
            self.data.sort(inplace=True)

    def __getitem__(self, key):
        if len(key) > 2:
            return self.sel.select(self.data[list(key[2:])],
                                             selector = '+'.join(key[0:2]))
        else:
            return self.sel.select(self.data, selector = '+'.join(key))

    def src_idx(self, src_int, dest_int, 
                src_type=None, dest_type=None, dest_ports=None):                
        """
        Retrieve source ports connected to the specified destination ports.

        Examples
        --------
        >>> p = Pattern('/foo[0:3]', '/bar[0:3]')
        >>> p['/foo[0:3]', '/bar[0:3]'] = 1
        >>> p['/bar[0:3]', '/foo[0:3]'] = 1
        >>> all(p.src_idx(0, 1, dest_ports='/bar[0]') == [('foo', 0), ('foo', 1), ('foo', 2)])

        Parameters
        ----------
        src_int, dest_int : int
            Source and destination interface identifiers.
        dest_ports : str
            Path-like selector corresponding to ports in destination 
            interface. If not specified, all ports in the destination 
            interface are considered.
        src_type, dest_type : str
            Types of source and destination ports as listed in their respective 
            interfaces.

        Returns
        -------
        idx : list of tuple
            Source ports connected to the specified destination ports.
        """

        assert src_int != dest_int
        assert src_int in self.interface.interface_ids and \
            dest_int in self.interface.interface_ids

        # Filter destination ports by specified type:
        if dest_type is None:
            to_int = self.interface.get_interface(dest_int)
        else:
            to_f = lambda x: x['type'] == dest_type
            to_int = self.interface.get_interface(dest_int).data_select(to_f)

        # Filter destination ports by specified ports:
        if dest_ports is None:
            to_idx = to_int.index
        else:
            to_idx = to_int[dest_ports].index

        # Filter source ports by specified type:
        if src_type is None:
            from_int = self.interface.get_interface(src_int)
        else:
            from_f = lambda x: x['type'] == src_type
            from_int = self.interface.get_interface(src_int).data_select(from_f)

        from_idx = from_int.index

        # Construct index from those rows in the pattern whose ports have been
        # selected by the above code:
        idx = self.data.select(lambda x: x[self.from_slice] in from_idx \
                               and x[self.to_slice] in to_idx).index
                
        # Remove duplicate tuples from output without perturbing the order
        # of the remaining tuples:
        return OrderedDict.fromkeys([x[self.from_slice] for x in idx]).keys()

    def dest_idx(self, src_int, dest_int, 
                 src_type=None, dest_type=None, src_ports=None):
        """
        Retrieve destination ports connected to the specified source ports.

        Examples
        --------
        >>> p = Pattern('/foo[0:3]', '/bar[0:3]')
        >>> p['/foo[0:3]', '/bar[0:3]'] = 1
        >>> p['/bar[0:3]', '/foo[0:3]'] = 1
        >>> all(p.dest_idx(0, 1, src_ports='/foo[0]') == [('bar', 0), ('bar', 1), ('bar', 2)])

        Parameters
        ----------
        src_int, dest_int : int
            Source and destination interface identifiers.
        src_ports : str
            Path-like selector corresponding to ports in source
            interface. If not specified, all ports in the source
            interface are considered.
        src_type, dest_type : str
            Types of source and destination ports as listed in their respective 
            interfaces.

        Returns
        -------
        idx : list of tuple
            Destination ports connected to the specified source ports.
        """

        assert src_int != dest_int
        assert src_int in self.interface.interface_ids and \
            dest_int in self.interface.interface_ids

        # Filter source ports by specified type:
        if src_type is None:
            from_int = self.interface.get_interface(src_int)
        else:
            from_f = lambda x: x['type'] == src_type
            from_int = self.interface.get_interface(src_int).data_select(from_f)

        # Filter source ports by specified ports:
        if src_ports is None:
            from_idx = from_int.index    
        else:
            from_idx = from_int[src_ports].index

        # Filter destination ports by specified type:
        if dest_type is None:
            to_int = self.interface.get_interface(dest_int)
        else:
            to_f = lambda x: x['type'] == dest_type
            to_int = self.interface.get_interface(dest_int).data_select(to_f)

        to_idx = to_int.index

        # Construct index from those rows in the pattern whose ports have been
        # selected by the above code:
        idx = self.data.select(lambda x: x[self.from_slice] in from_idx \
                               and x[self.to_slice] in to_idx).index

        # Remove duplicate tuples from output without perturbing the order
        # of the remaining tuples:
        return OrderedDict.fromkeys([x[self.to_slice] for x in idx]).keys()

    def __len__(self):
        return self.data.__len__()

    def __repr__(self):
        return 'Pattern\n-------\n'+self.data.__repr__()

    def clear(self):
        """
        Clear all connections in class instance.
        """

        # XXX need to also clear the interface data structure:
        self.data.drop(self.data.index, inplace=True)

    def is_connected(self, from_int, to_int):
        """
        Check whether the specified interfaces are connected.

        Parameters
        ----------
        from_int, to_int : int
            Interface identifiers; must be in `self.interface.keys()`.

        Returns
        -------
        result : bool
            True if at least one connection from `from_int` to `to_int`
            exists.
        """

        assert from_int != to_int
        assert from_int in self.interface.interface_ids
        assert to_int in self.interface.interface_ids

        # Get index of all defined connections:
        idx = self.data[self.data['conn'] != 0].index
        for t in idx.tolist():
            
            # Split tuple into 'from' and 'to' identifiers:
            from_id = t[0:self.num_levels['from']]
            to_id = t[self.num_levels['from']:self.num_levels['from']+self.num_levels['to']]
            if from_id in self.interface.get_interface(from_int).index and \
               to_id in self.interface.get_interface(to_int).index:
                return True
        return False

    def from_csv(self, file_name, **kwargs):
        """
        Read connectivity data from CSV file.

        Given N 'from' levels and M 'to' levels in the internal index, 
        the method assumes that the first N+M columns in the file specify
        the index levels.

        See Also
        --------
        pandas.read_csv
        """

        # XXX this should refuse to load identifiers that are not in any of the
        # sets of ports comprised by the pattern:
        data_names = self.data.columns
        index_names = self.data.index.names
        kwargs['names'] = data_names
        kwargs['index_col'] = range(len(index_names))
        data = pd.read_csv(file_name, **kwargs)
        self.data = data

        # Restore MultiIndex level names:
        self.data.index.names = index_names

    @classmethod
    def from_graph(self, g):
        """
        Convert a networkx directed graph into a Pattern instance.

        Parameters
        ----------
        g : networkx.DiGraph
            Graph to convert.

        Returns
        -------
        Must contain node labels that at least contain 'interface'
        and 'io' attributes.
        """

        assert type(g) == nx.DiGraph

        nodes = []
        for n in g.nodes(data=True):
            assert PathLikeSelector.is_identifier(n[0])

        # unfinished

    @classmethod
    def split_multiindex(cls, idx, a, b):
        """
        Split a single MultiIndex into two instances.

        Parameters
        ----------
        idx : pandas.MultiIndex
            MultiIndex to split.
        a, b : slice
            Ranges of index columns to include in the two resulting instances.

        Returns
        -------
        idx_a, idx_b : pandas.MultiIndex
            Resulting MultiIndex instances.
        """

        t_list = idx.tolist()
        idx_a = pd.MultiIndex.from_tuples([t[a] for t in t_list])
        idx_b = pd.MultiIndex.from_tuples([t[b] for t in t_list])
        return idx_a, idx_b

    def to_graph(self):
        """
        Convert the pattern to a networkx directed graph.
        
        Returns
        -------
        g : networkx.DiGraph
            Graph whose nodes are the pattern's ports 
            and whose edges are the pattern's connections.

        Notes
        -----
        The 'conn' attribute of the connections is not transferred to the graph
        edges.

        This method relies upon the assumption that the sets of 
        port identifiers comprised by the pattern's interfaces are disjoint.
        """

        g = nx.DiGraph()

        # Add all of the ports as nodes:
        for t in self.interface.data.index:    
            id = self.sel.to_identifier(t)

            # Replace NaNs with empty strings:
            d = {k: (v if str(v) != 'nan' else '') \
                 for k, v in self.interface.data.ix[t].to_dict().iteritems()}

            # Each node's name corresponds to the port identifier string:
            g.add_node(id, d)

        # Add all of the connections as edges:
        for t in self.data.index:
            t_from = t[self.from_slice]
            t_to = t[self.to_slice]
            id_from = self.sel.to_identifier(t_from)
            id_to = self.sel.to_identifier(t_to)
            d = self.data.ix[t].to_dict()

            # Discard the 'conn' attribute because the existence of the edge
            # indicates that the connection exists:
            if d.has_key('conn'):
                d.pop('conn')

            g.add_edge(id_from, id_to, d)

        return g

if __name__ == '__main__':
    from unittest import main, TestCase
    from pandas.util.testing import assert_frame_equal, assert_index_equal

    class test_interface(TestCase):
        def setUp(self):
            self.interface = Interface('/foo[0:3]')
            self.interface['/foo[0]', 'interface', 'io'] = [0, 'in']
            self.interface['/foo[1:3]', 'interface', 'io'] = [0, 'out']

        def test_create_empty(self):
            i = Interface('')
            assert len(i) == 0

        def test_create_dup_identifiers(self):
            self.assertRaises(Exception, Interface, '/foo[0],/foo[0]')

        def test_as_selectors(self):
            self.assertSequenceEqual(self.interface.as_selectors([('foo', 0),
                                                                  ('foo', 1)]),
                                     ['/foo[0]', '/foo[1]'])

        def test_data_select(self):
            i = self.interface.data_select(lambda x: x['io'] >= 'out')
            assert_index_equal(i.data.index,
                               pd.MultiIndex.from_tuples([('foo', 1),
                                                          ('foo', 2)]))

        def test_from_df(self):
            idx = pd.MultiIndex.from_tuples([('foo', 0),
                                             ('foo', 1),
                                             ('foo', 2)])
            data = data = [(0, 'in', 'spike'),
                           (1, 'in', 'gpot'),
                           (1, 'out', 'gpot')]
            columns = ['interface', 'io', 'type']
            df = pd.DataFrame(data, index=idx, columns=columns)
            i = Interface.from_df(df)
            assert_index_equal(i.data.index, idx)
            # Should also check DataFrame contents.

        def test_from_df_dup(self):
            idx = pd.MultiIndex.from_tuples([('foo', 0),
                                             ('foo', 0),
                                             ('foo', 2)])
            data = data = [(0, 'in', 'spike'),
                           (1, 'in', 'gpot'),
                           (1, 'out', 'gpot')]
            columns = ['interface', 'io', 'type']
            df = pd.DataFrame(data, index=idx, columns=columns)
            self.assertRaises(Exception, Interface.from_df, df)

        def test_from_dict(self):
            i = Interface.from_dict({'/foo[0:3]': np.nan})
            assert_index_equal(i.data.index,
                               pd.MultiIndex.from_tuples([('foo', 0),
                                                          ('foo', 1),
                                                          ('foo', 2)]))

        def test_in_interfaces(self):
            assert self.interface.in_interfaces('/foo[0:3]') == True
            assert self.interface.in_interfaces('/foo[0:4]') == False

        def test_in_ports(self):
            self.assertSequenceEqual(self.interface.in_ports(0),
                                     [('foo', 0)])

        def test_get_interface(self):
            i = Interface('/foo[0:4]')
            i['/foo[0:2]', 'interface'] = 0
            i['/foo[2:4]', 'interface'] = 1
            j = Interface('/foo[2:4]')
            j['/foo[2:4]', 'interface'] = 1
            assert_frame_equal(i.get_interface(1).data, j.data)

        def test_out_ports(self):
            self.assertSequenceEqual(self.interface.out_ports(0),
                                     [('foo', 1), ('foo', 2)])

        def test_port_select(self):
            i = self.interface.port_select(lambda x: x[1] >= 1)
            assert_index_equal(i.data.index,
                               pd.MultiIndex.from_tuples([('foo', 1),
                                                          ('foo', 2)]))

        def test_ports(self):
            self.assertSequenceEqual(self.interface.ports(0),
                                     [('foo', 0),
                                      ('foo', 1),
                                      ('foo', 2)])
                                                              
        def test_index(self):
            assert_index_equal(self.interface.index,
                               pd.MultiIndex(levels=[['foo'], [0, 1, 2]],
                                             labels=[[0, 0, 0], [0, 1, 2]],
                                             names=['0', '1']))

        def test_interface_ids(self):
            i = Interface('/foo[0:4]')
            i['/foo[0:2]', 'interface', 'io'] = [0, 'out']
            i['/foo[2:4]', 'interface', 'io'] = [1, 'in']
            assert i.interface_ids == set([0, 1])

        def test_is_compatible_both_dirs(self):
            i = Interface('/foo[0:4]')
            i['/foo[0:2]', 'interface', 'io'] = [0, 'out']
            i['/foo[2:4]', 'interface', 'io'] = [0, 'in']
            j = Interface('/foo[0:4]')
            j['/foo[0:2]', 'interface', 'io'] = [1, 'in']
            j['/foo[2:4]', 'interface', 'io'] = [1, 'out']
            assert i.is_compatible(0, j, 1)

        def test_is_compatible_one_dir(self):
            i = Interface('/foo[0:2]')
            i['/foo[0:2]', 'interface', 'io'] = [0, 'out']
            j = Interface('/foo[0:2]')
            j['/foo[0:2]', 'interface', 'io'] = [1, 'in']
            assert i.is_compatible(0, j, 1)

        def test_which_int_unset(self):
            i = Interface('/foo[0:4]')
            assert i.which_int('/foo[0:2]') == set()

        def test_which_int_set(self):
            i = Interface('/foo[0:4]')
            i['/foo[0]', 'interface', 'io'] = [0, 'out']
            i['/foo[1]', 'interface', 'io'] = [0, 'in']
            i['/foo[2]', 'interface', 'io'] = [1, 'in']
            i['/foo[3]', 'interface', 'io'] = [1, 'out']
            assert i.which_int('/foo[0:2]') == {0}
            assert i.which_int('/foo[0:4]') == {0, 1}

    class test_pattern(TestCase):
        def setUp(self):
            # XXX not a good example; a pattern shouldn't allow a single port to
            # both send output and receive input:
            self.df = pd.DataFrame(data={'conn': np.ones(6, dtype=object),
                            'from_type': ['spike', 'spike', 'spike',
                                          'gpot', 'gpot', 'spike'],
                            'to_type': ['spike', 'spike', 'spike',
                                        'gpot', 'gpot', 'gpot'],
                            'from_0': ['foo', 'foo', 'foo', 'bar', 'bar', 'bar'],
                            'from_1': [0, 0, 2, 0, 1, 2],
                            'to_0': ['bar', 'bar', 'bar', 'foo', 'foo', 'foo'],
                            'to_1': [0, 1, 2, 0, 0, 1]})
            self.df.set_index('from_0', append=False, inplace=True)
            self.df.set_index('from_1', append=True, inplace=True)
            self.df.set_index('to_0', append=True, inplace=True)
            self.df.set_index('to_1', append=True, inplace=True)
            self.df.sort(inplace=True)

        def test_create(self):
            p = Pattern('/foo[0:3]', '/bar[0:3]',
                        columns=['conn','from_type', 'to_type'])
            p['/foo[0]', '/bar[0]'] = [1, 'spike', 'spike']
            p['/foo[0]', '/bar[1]'] = [1, 'spike', 'spike']
            p['/foo[2]', '/bar[2]'] = [1, 'spike', 'spike']
            p['/bar[0]', '/foo[0]'] = [1, 'gpot', 'gpot']
            p['/bar[1]', '/foo[0]'] = [1, 'gpot', 'gpot']
            p['/bar[2]', '/foo[1]'] = [1, 'spike', 'gpot']
            assert_frame_equal(p.data, self.df)

        def test_create_dup_identifiers(self):
            self.assertRaises(Exception,  Pattern,
                              '/foo[0],/foo[0]', '/bar[0:2]')

        def test_src_idx(self):
            p = Pattern('/[aaa,bbb][0:3]', '/[xxx,yyy][0:3]')
            p['/aaa[0:3]', '/yyy[0:3]'] = 1
            p['/xxx[0:3]', '/bbb[0:3]'] = 1
            self.assertItemsEqual(p.src_idx(0, 1),
                                  [('aaa', 0),
                                   ('aaa', 1),
                                   ('aaa', 2)])
            
        def test_src_idx_dest_ports(self):
            p = Pattern('/[aaa,bbb][0:3]', '/[xxx,yyy][0:3]')
            p['/aaa[0]', '/yyy[0]'] = 1
            p['/aaa[1:3]', '/yyy[1:3]'] = 1
            p['/xxx[0:3]', '/bbb[0:3]'] = 1
            self.assertItemsEqual(p.src_idx(0, 1, dest_ports='/yyy[0]'),
                                  [('aaa', 0)])

        def test_src_idx_src_type(self):
            p = Pattern('/[aaa,bbb][0:3]', '/[xxx,yyy][0:3]')
            p['/aaa[0:3]', '/xxx[0:3]'] = 1
            p['/bbb[0:3]', '/yyy[0:3]'] = 1
            p.interface['/aaa[0:3]'] = [0, 'in', 'spike']
            p.interface['/xxx[0:3]'] = [1, 'out', 'spike']
            self.assertItemsEqual(p.src_idx(0, 1, src_type='spike'), 
                                  [('aaa', 0),
                                   ('aaa', 1),
                                   ('aaa', 2)])
            self.assertItemsEqual(p.src_idx(0, 1, src_type='gpot'), [])

        def test_src_idx_dest_type(self):
            p = Pattern('/[aaa,bbb][0:3]', '/[xxx,yyy][0:3]')
            p['/aaa[0:3]', '/xxx[0:3]'] = 1
            p['/bbb[0:3]', '/yyy[0:3]'] = 1
            p.interface['/aaa[0:3]', 'type'] = 'spike'
            p.interface['/xxx[0:3]', 'type'] = 'spike'
            self.assertItemsEqual(p.src_idx(0, 1, dest_type='spike'), 
                                  [('aaa', 0),
                                   ('aaa', 1),
                                   ('aaa', 2)])
            self.assertItemsEqual(p.src_idx(0, 1, dest_type='gpot'), [])
            
        def test_dest_idx(self):
            p = Pattern('/[aaa,bbb][0:3]', '/[xxx,yyy][0:3]')
            p['/aaa[0:3]', '/yyy[0:3]'] = 1
            p['/xxx[0:3]', '/bbb[0:3]'] = 1
            self.assertItemsEqual(p.dest_idx(0, 1, src_ports='/aaa[0]'),
                                  [('yyy', 0),
                                   ('yyy', 1),
                                   ('yyy', 2)])

        def test_dest_idx_src_ports(self):
            p = Pattern('/[aaa,bbb][0:3]', '/[xxx,yyy][0:3]')
            p['/aaa[0]', '/yyy[0]'] = 1
            p['/aaa[1:3]', '/yyy[1:3]'] = 1
            p['/xxx[0:3]', '/bbb[0:3]'] = 1
            self.assertItemsEqual(p.dest_idx(0, 1, src_ports='/aaa[0]'),
                                  [('yyy', 0)])

        def test_dest_idx_src_type(self):
            p = Pattern('/[aaa,bbb][0:3]', '/[xxx,yyy][0:3]')
            p['/aaa[0:3]', '/xxx[0:3]'] = 1
            p['/bbb[0:3]', '/yyy[0:3]'] = 1
            p.interface['/aaa[0:3]', 'type'] = 'spike'
            p.interface['/xxx[0:3]', 'type'] = 'spike'
            self.assertItemsEqual(p.dest_idx(0, 1, src_type='spike'), 
                                  [('xxx', 0),
                                   ('xxx', 1),
                                   ('xxx', 2)])
            self.assertItemsEqual(p.src_idx(0, 1, src_type='gpot'), [])

        def test_dest_idx_dest_type(self):
            p = Pattern('/[aaa,bbb][0:3]', '/[xxx,yyy][0:3]')
            p['/aaa[0:3]', '/xxx[0:3]'] = 1
            p['/bbb[0:3]', '/yyy[0:3]'] = 1
            p.interface['/aaa[0:3]', 'type'] = 'spike'
            p.interface['/xxx[0:3]', 'type'] = 'spike'
            self.assertItemsEqual(p.dest_idx(0, 1, dest_type='spike'), 
                                  [('xxx', 0),
                                   ('xxx', 1),
                                   ('xxx', 2)])
            self.assertItemsEqual(p.dest_idx(0, 1, dest_type='gpot'), [])

        def test_is_connected(self):
            p = Pattern('/aaa[0:3]', '/bbb[0:3]')
            p['/aaa[0]', '/bbb[2]'] = 1
            assert p.is_connected(0, 1) == True
            assert p.is_connected(1, 0) == False

        def test_get_conns(self):
            p = Pattern('/aaa[0:3]', '/bbb[0:3]')
            p['/aaa[0]', '/bbb[2]'] = 1
            p['/aaa[1]', '/bbb[0]'] = 1
            p['/aaa[2]', '/bbb[1]'] = 1
            self.assertSequenceEqual(p.get_conns(),
                                     [(('aaa', 0), ('bbb', 2)),
                                      (('aaa', 1), ('bbb', 0)),
                                      (('aaa', 2), ('bbb', 1))])
            self.assertSequenceEqual(p.get_conns(True),
                                     [('/aaa[0]', '/bbb[2]'),
                                      ('/aaa[1]', '/bbb[0]'),
                                      ('/aaa[2]', '/bbb[1]')])

        def test_to_graph(self):
            p = Pattern('/foo[0:3]', '/bar[0:3]')
            p['/foo[0:3]', '/bar[0:3]'] = 1
            g = p.to_graph()

            self.assertItemsEqual(g.nodes(data=True), 
                                  [('/bar[0]', {'interface': 1, 'io': 'out', 'type': ''}),
                                   ('/bar[2]', {'interface': 1, 'io': 'out', 'type': ''}),
                                   ('/bar[1]', {'interface': 1, 'io': 'out', 'type': ''}),
                                   ('/foo[1]', {'interface': 0, 'io': 'in', 'type': ''}),                                  
                                   ('/foo[2]', {'interface': 0, 'io': 'in', 'type': ''}),
                                   ('/foo[0]', {'interface': 0, 'io': 'in', 'type': ''})])
            self.assertItemsEqual(g.edges(data=True),
                                  [('/foo[2]', '/bar[2]', {}),
                                   ('/foo[2]', '/bar[0]', {}),
                                   ('/foo[2]', '/bar[1]', {}),
                                   ('/foo[1]', '/bar[2]', {}),
                                   ('/foo[1]', '/bar[0]', {}),
                                   ('/foo[1]', '/bar[1]', {}),
                                   ('/foo[0]', '/bar[2]', {}),
                                   ('/foo[0]', '/bar[0]', {}),
                                   ('/foo[0]', '/bar[1]', {})])

        def test_clear(self):
            p = Pattern('/aaa[0:3]', '/bbb[0:3]')
            p['/aaa[0:3]', '/bbb[0:3]'] = 1
            p.clear()
            assert len(p) == 0

    main()
