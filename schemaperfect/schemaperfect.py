import collections
import contextlib
import json

import jsonschema

# If ENABLE_VALIDATION_AT_INSTANTIATION is True, then schema objects are converted to dict and
# validated at creation time. This slows things down, particularly for
# larger specs, but leads to much more useful tracebacks for the user.
# Individual schema classes can override this by setting the
# class-level _class_is_valid_at_instantiation attribute to False
import typing

ENABLE_VALIDATION_AT_INSTANTIATION = True


def set_valid_at_instantiation(value:bool):
    global ENABLE_VALIDATION_AT_INSTANTIATION
    ENABLE_VALIDATION_AT_INSTANTIATION = value

def enable_debug_mode():
    """
    @deprecated use set_valid_at_instantiation instead.
    :return:
    """

    set_valid_at_instantiation(True)


def disable_debug_mode():
    """
    @deprecated use set_valid_at_instantiation instead.
    :return:
    """
    set_valid_at_instantiation(False)


@contextlib.contextmanager
def debug_mode(arg):
    global ENABLE_VALIDATION_AT_INSTANTIATION
    original = ENABLE_VALIDATION_AT_INSTANTIATION
    ENABLE_VALIDATION_AT_INSTANTIATION = arg
    try:
        yield
    finally:
        ENABLE_VALIDATION_AT_INSTANTIATION = original


METASCHEMA_VERSION = 'draft7'


def set_metaschema_version(version):
    """Sets the jsonschema schema version to be used when validating json. See [list of supported metaschema versions](https://github.com/Julian/jsonschema/tree/master/jsonschema/schemas)."""
    import pkgutil
    global METASCHEMA_VERSION
    if not pkgutil.get_data('jsonschema', 'schemas/{0}.json'.format(version)):
        raise ValueError('Unknown metaschema version! The default is "draft7"')
    METASCHEMA_VERSION = version


def get_metaschema_version():
    """Gets the jsonschema schema version to be used when validating json."""
    return METASCHEMA_VERSION


class SchemaValidationError(jsonschema.ValidationError):
    """A wrapper for jsonschema.ValidationError with friendlier traceback"""

    def __init__(self, obj, err):
        super(SchemaValidationError, self).__init__(**self._get_contents(err))
        self._err = err
        self.obj = obj
        self.message = str(self)

    @staticmethod
    def _get_contents(err):
        """Get a dictionary with the contents of a ValidationError"""
        return err._contents()

    def __str__(self):
        cls = self.obj.__class__
        schema_path = ['{}.{}'.format(cls.__module__, cls.__name__)]
        schema_path.extend(self.schema_path)
        schema_path = '->'.join(str(val) for val in schema_path[:-1]
                                if val not in ('properties',
                                               'additionalProperties',
                                               'patternProperties'))
        return """Invalid specification

        {}, validating {!r}

        {}
        """.format(schema_path, self.validator, self.message)


class UndefinedType(object):
    """A singleton object for marking undefined attributes"""
    __instance = None

    def __new__(cls, *args, **kwargs):
        if not isinstance(cls.__instance, cls):
            cls.__instance = object.__new__(cls, *args, **kwargs)
        return cls.__instance

    def __repr__(self):
        return 'Undefined'


Undefined = UndefinedType()


class SchemaBase(object):
    """Base class for schema wrappers.

    Each derived class should set the _schema class attribute (and optionally
    the _rootschema class attribute) which is used for validation.
    """
    _schema = None
    _rootschema = None
    _property_names = None
    _class_is_valid_at_instantiation = True

    def __init__(self, *args, **kwds):
        # Two valid options for initialization, which should be handled by
        # derived classes:
        # - a single arg with no kwds, for, e.g. {'type': 'string'}
        # - zero args with zero or more kwds for {'type': 'object'}
        if self._schema is None:
            raise ValueError("Cannot instantiate object of type {}: "
                             "_schema class attribute is not defined."
                             "".format(self.__class__))
        if self._property_names is None and kwds:
           self._property_names =  tuple(kwds.keys())
        if kwds:
            assert len(args) == 0
        else:
            assert len(args) in [0, 1]

        # use object.__setattr__ because we override setattr below.
        self._args = args
        self._kwds = kwds
        self._validation_error = None

        if ENABLE_VALIDATION_AT_INSTANTIATION and self._class_is_valid_at_instantiation:
            self.to_dict(validate=True)



    def copy(self, deep=True, exclude: typing.Optional[typing.Union[typing.AbstractSet, typing.Sequence]] = None):
        """Return a copy of the object

        Parameters
        ----------
        deep : boolean, optional
            if True (default) then return a deep copy of all dict, list, and
            SchemaBase objects within the object structure
        exclude : list, optional
            A list of keys for which the contents should not be copied, but
            only stored by reference.
        """

        def _deep_copy(obj, exclude=()):
            if isinstance(obj, SchemaBase):
                args = tuple(_deep_copy(arg) for arg in obj._args)
                kwds = {k: (_deep_copy(v, exclude=exclude)
                            if k not in exclude else v)
                        for k, v in obj._kwds.items()}
                with debug_mode(False):
                    return obj.__class__(*args, **kwds)
            elif isinstance(obj, typing.Sequence) and not isinstance(obj, str):
                return [_deep_copy(v, exclude=exclude) for v in obj]
            elif isinstance(obj, typing.Mapping):
                return {k: (_deep_copy(v, exclude=exclude)
                            if k not in exclude else v)
                        for k, v in obj.items()}
            else:
                return obj

        if exclude is None:
            exclude = ()
        exclude = frozenset(exclude)

        if deep:
            return _deep_copy(self, exclude=exclude)
        else:
            with debug_mode(False):
                return self.__class__(*self._args, **self._kwds)

    def __getattr__(self, attr):
        # reminder: getattr is called after the __get_attribute__ lookups
        if self._property_names is not None and attr in self._property_names and attr in self._kwds:
            return self._kwds[attr]
        else:
            try:
                _getattr = super().__getattr__
            except AttributeError:
                _getattr = super().__getattribute__
            return _getattr(attr)

    def __setattr__(self, item, val):
        if self._property_names is not None and item in self._property_names:
            self._kwds[item] = val
        else:
            super().__setattr__(item, val)

    def __getitem__(self, item):
        return self._kwds[item]

    def __setitem__(self, item, val):
        self._kwds[item] = val

    def __repr__(self):
        if self._kwds:
            args = ("{}: {!r}".format(key, val)
                    for key, val in sorted(self._kwds.items())
                    if val is not Undefined)
            args = '\n' + ',\n'.join(args)
            return "{0}({{{1}\n}})".format(self.__class__.__name__,
                                           args.replace('\n', '\n  '))
        else:
            return "{}({!r})".format(self.__class__.__name__, self._args[0])

    def __eq__(self, other):
        return (type(self) is type(other)
                and self._args == other._args
                and self._kwds == other._kwds)

    @property
    def is_valid(self) -> bool:
        """Checks if the instance is currently valid and returns bool. Validation error can be obtained via 'instance.validation_error'"""
        try:
            self.to_dict(validate=True)
            return True
        except SchemaValidationError:
            return False

    @property
    def validation_error(self):
        """The latest validation error for this instance."""
        return object.__getattr__(self, '_validation_error')

    def to_dict(self,
                validate=True,
                include: typing.Optional[typing.Union[typing.AbstractSet, typing.Sequence]] = None,
                exclude: typing.Optional[typing.Union[typing.AbstractSet, typing.Sequence]] = None,
                context: typing.Optional[typing.Mapping] = None):
        """Return a dictionary representation of the object

        Parameters
        ----------
        validate : boolean or string
            If True (default), then validate the output dictionary
            against the schema. If "deep" then recursively validate
            all objects in the spec. This takes much more time, but
            it results in friendlier tracebacks for large objects.
        include : list
            A list of property names / keys to include. Defaults to self._property_names. Not passed to recursive calls.
        exclude : list
            A list of property names / keys to exclude.  Not passed to recursive calls.
        context : dict (optional)
            A context dictionary that will be passed to all child to_dict
            function calls

        Returns
        -------
        dct : dictionary
            The dictionary representation of this object

        Raises
        ------
        jsonschema.ValidationError :
            if validate=True and the dict does not conform to the schema
        """
        if include is None:
            include = self._property_names
        if include is not None:
            include = frozenset(include)
        if exclude is not None:
            exclude = frozenset(exclude)
        if context is None:
            context = {}

        sub_validate = 'deep' if validate == 'deep' else False

        def _todict(val):
            if isinstance(val, SchemaBase):
                return val.to_dict(validate=sub_validate, context=context)
            elif isinstance(val, typing.Sequence):
                if not isinstance(val, str):
                    return [_todict(v) for v in val]
                else:
                    return str(val)
            elif isinstance(val, (set, frozenset)):
                return list(sorted(map(_todict, val)))
            elif isinstance(val, typing.Mapping):
                return {k: _todict(v) for k, v in val.items()
                        if v is not Undefined}
            elif str(getattr(type(val), '__name__')).startswith('numpy'):  # convert most numpy types to python native.
                return val.item()
            else:
                return val

        if self._args and not self._kwds:
            result = _todict(self._args[0])
        elif not self._args:
            _keys = tuple(self._kwds.keys())
            if include is not None:
                _keys = tuple(k for k in _keys if k in include)
            if exclude is not None:
                _keys = tuple(k for k in _keys if k not in exclude)
            result = _todict({k: self._kwds[k] for k in _keys if self._kwds[k] is not Undefined})
        else:
            raise ValueError("{} instance has both a value and properties : "
                             "cannot serialize to dict".format(self.__class__))
        if validate:
            try:
                self.validate(result)
            except jsonschema.ValidationError as err:
                object.__setattr__(self, '_validation_error', SchemaValidationError(self, err))
                raise self._validation_error
        return result

    def to_json(self, validate=True, exclude: typing.Optional[typing.Union[typing.AbstractSet, typing.Sequence]] = None, context: typing.Optional[typing.Mapping] = None,
                indent=2, sort_keys=True, **kwargs):
        """Emit the JSON representation for this object as a string.

        Parameters
        ----------
        validate : boolean or string
            If True (default), then validate the output dictionary
            against the schema. If "deep" then recursively validate
            all objects in the spec. This takes much more time, but
            it results in friendlier tracebacks for large objects.
        exclude : list
            A list of keys to exclude. This will *not* passed to child to_dict
            function calls.
        context : dict (optional)
            A context dictionary that will be passed to all child to_dict
            function calls
        indent : integer, default 2
            the number of spaces of indentation to use
        sort_keys : boolean, default True
            if True, sort keys in the output
        **kwargs
            Additional keyword arguments are passed to ``json.dumps()``

        Returns
        -------
        spec : string
            The JSON specification of the chart object.
        """
        if exclude is None:
            exclude = ()
        if context is None:
            context = {}

        dct = self.to_dict(validate=validate, exclude=exclude, context=context)
        return json.dumps(dct, indent=indent, sort_keys=sort_keys, **kwargs)

    @classmethod
    def _default_wrapper_classes(cls):
        """Return the set of classes used within cls.from_dict()"""
        return SchemaBase.__subclasses__()

    @classmethod
    def from_dict(cls, dct, validate=True, _wrapper_classes=None):
        """Construct class from a dictionary representation

        Parameters
        ----------
        dct : dictionary
            The dict from which to construct the class
        validate : boolean
            If True (default), then validate the input against the schema.
        _wrapper_classes : list (optional)
            The set of SchemaBase classes to use when constructing wrappers
            of the dict inputs. If not specified, the result of
            cls._default_wrapper_classes will be used.

        Returns
        -------
        obj : Schema object
            The wrapped schema

        Raises
        ------
        jsonschema.ValidationError :
            if validate=True and dct does not conform to the schema
        """
        if validate:
            cls.validate(dct)
        if _wrapper_classes is None:
            _wrapper_classes = cls._default_wrapper_classes()
        converter = _FromDict(_wrapper_classes)
        return converter.from_dict(constructor=cls, root=cls,
                                   schema=cls._schema, dct=dct)

    @classmethod
    def from_json(cls, json_string, validate=True, **kwargs):
        """Instantiate the object from a valid JSON string

        Parameters
        ----------
        json_string : string
            The string containing a valid JSON chart specification.
        validate : boolean
            If True (default), then validate the input against the schema.
        **kwargs :
            Additional keyword arguments are passed to json.loads

        Returns
        -------
        chart : Chart object
            The altair Chart object built from the specification.
        """
        dct = json.loads(json_string, **kwargs)
        return cls.from_dict(dct, validate=validate)

    @classmethod
    def validate(cls, instance, schema=None):
        """
        Validate the instance against the class schema in the context of the
        rootschema.
        """
        if schema is None:
            schema = cls._schema
        resolver = jsonschema.RefResolver.from_schema(cls._rootschema or cls._schema)
        return jsonschema.validate(instance, schema, resolver=resolver)

    @classmethod
    def resolve_references(cls, schema):
        """Resolve references of the schema the context of this object's schema"""
        resolver = jsonschema.RefResolver.from_schema(cls._rootschema
                                                      or cls._schema
                                                      or schema)
        while '$ref' in schema:
            with resolver.resolving(schema['$ref']) as resolved:
                schema = resolved
        return schema

    def __dir__(self):
        return list(self._kwds.keys())


class _FromDict(object):
    """Class used to construct SchemaBase class hierarchies from a dict

    The primary purpose of using this class is to be able to build a hash table
    that maps schemas to their wrapper classes. The candidate classes are
    specified in the ``class_list`` argument to the constructor.
    """
    _hash_exclude_keys = ('definitions', 'title', 'description', '$schema', 'id')

    def __init__(self, class_list):
        # Create a mapping of a schema hash to a list of matching classes
        # This lets us quickly determine the correct class to construct
        self.class_dict = collections.defaultdict(list)
        for cls in class_list:
            if cls._schema is not None:
                self.class_dict[self.hash_schema(cls._schema)].append(cls)

    @classmethod
    def hash_schema(cls, schema, use_json=True):
        """
        Compute a python hash for a nested dictionary which
        properly handles dicts, lists, sets, and tuples.

        At the top level, the function excludes from the hashed schema all keys
        listed in `exclude_keys`.

        This implements two methods: one based on conversion to JSON, and one based
        on recursive conversions of unhashable to hashable types; the former seems
        to be slightly faster in several benchmarks.
        """
        if cls._hash_exclude_keys:
            schema = {key: val for key, val in schema.items()
                      if key not in cls._hash_exclude_keys}
        if use_json:
            s = json.dumps(schema, sort_keys=True)
            return hash(s)
        else:
            def _freeze(val):
                if isinstance(val, typing.Mapping):
                    return frozenset((k, _freeze(v)) for k, v in val.items())
                elif isinstance(val, typing.AbstractSet):
                    return frozenset(map(_freeze, val))
                elif isinstance(val, typing.Sequence) and not isinstance(val, str):
                    return tuple(map(_freeze, val))
                else:
                    return val

            return hash(_freeze(schema))

    @staticmethod
    def _passthrough(*args, **kwds):
        """An object constructor that simply passes arguments through"""
        if kwds and not args:
            return kwds
        elif args and not kwds:
            assert len(args) == 1
            return args[0]
        else:
            raise ValueError("Both args and kwds supplied")

    def from_dict(self, constructor, root, schema, dct):
        """Construct an object from a dict representation"""
        # TODO: introspect lists, objects, etc. when they don't have a wrapper.
        #       could do this by passing the schema rather than cls.
        schema = root.resolve_references(schema)

        def _get_constructor(schema):
            # TODO: do something more than simply selecting the last match?
            hash_ = self.hash_schema(schema)
            matches = self.class_dict[hash_]
            constructor = matches[-1] if matches else self._passthrough
            schema = root.resolve_references(schema)
            return constructor, schema

        if 'anyOf' in schema or 'oneOf' in schema:
            schemas = schema.get('anyOf', []) + schema.get('oneOf', [])
            for this_schema in schemas:
                this_constructor, this_schema = _get_constructor(this_schema)
                try:
                    root.validate(dct, this_schema)
                except jsonschema.ValidationError:
                    continue
                else:
                    return self.from_dict(this_constructor, root, this_schema, dct)

        if isinstance(dct, typing.Mapping):
            # TODO: handle schemas for additionalProperties/patternProperties
            props = schema.get('properties', {})
            kwds = {}
            for key, val in dct.items():
                if key in props:
                    prop_constructor, prop_schema = _get_constructor(props[key])
                    val = self.from_dict(prop_constructor, root, prop_schema, val)
                kwds[key] = val
            return constructor(**kwds)

        elif isinstance(dct, typing.Sequence) and not isinstance(dct, str):
            if 'items' in schema:
                item_schema = schema['items']
                item_constructor, item_schema = _get_constructor(item_schema)
            else:
                item_schema = {}
                item_constructor = self._passthrough
            dct = [self.from_dict(item_constructor, root, item_schema, val)
                   for val in dct]
            return constructor(dct)
        else:
            return constructor(dct)
