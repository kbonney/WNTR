# -*- coding: utf-8 -*-

"""The base classes for the the WNTR quality extensions module.
Other than the enum classes, the classes in this module are all abstract 
and/or mixin classes, and should not be instantiated directly.
"""

from abc import ABC, abstractclassmethod, abstractmethod, abstractproperty
import logging
from enum import Enum, IntEnum
import os
from typing import Any, Dict, Iterator, List, Union
from wntr.utils.disjoint_mapping import DisjointMapping

from wntr.utils.enumtools import add_get

has_sympy = False
try:
    from sympy import (
        Float,
        Symbol,
        init_printing,
        symbols,
        Function,
        Mul,
        Add,
        Pow,
        Integer,
    )
    from sympy.functions import (
        cos,
        sin,
        tan,
        cot,
        Abs,
        sign,
        sqrt,
        log,
        exp,
        asin,
        acos,
        atan,
        acot,
        sinh,
        cosh,
        tanh,
        coth,
        Heaviside,
    )
    from sympy.parsing import parse_expr
    from sympy.parsing.sympy_parser import (
        convert_xor,
        standard_transformations,
        auto_number,
        auto_symbol,
    )

    class _log10(Function):
        @classmethod
        def eval(cls, x):
            return log(x, 10)

    has_sympy = True
except ImportError:
    sympy = None
    has_sympy = False
    logging.critical("This python installation does not have SymPy installed. Certain functionality will be disabled.")
    standard_transformations = (None,)
    convert_xor = None
    if not has_sympy:
        from numpy import (
            cos,
            sin,
            tan,
            abs,
            sign,
            sqrt,
            log,
            exp,
            arcsin,
            arccos,
            arctan,
            sinh,
            cosh,
            tanh,
            heaviside,
            log10,
        )

        def _cot(x):
            return 1 / tan(x)

        cot = _cot
        Abs = abs
        asin = arcsin
        acos = arccos
        atan = arctan

        def _acot(x):
            return 1 / arctan(1 / x)

        acot = _acot

        def _coth(x):
            return 1 / tanh(x)

        coth = _coth
        Heaviside = heaviside
        _log10 = log10

logger = logging.getLogger(__name__)

__all__ = [
    "HYDRAULIC_VARIABLES",
    "EXPR_FUNCTIONS",
    "RESERVED_NAMES",
    "EXPR_TRANSFORMS",
    "VariableType",
    "SpeciesType",
    "ReactionType",
    "ExpressionType",
    "AbstractVariable",
    "AbstractReaction",
    "ReactionSystem",
    "VariableValues",
    "AbstractModel",
]

HYDRAULIC_VARIABLES = [
    {"name": "D", "note": "pipe diameter (feet or meters) "},
    {
        "name": "Kc",
        "note": "pipe roughness coefficient (unitless for Hazen-Williams or Chezy-Manning head loss formulas, millifeet or millimeters for Darcy-Weisbach head loss formula)",
    },
    {"name": "Q", "note": "pipe flow rate (flow units) "},
    {"name": "U", "note": "pipe flow velocity (ft/sec or m/sec) "},
    {"name": "Re", "note": "flow Reynolds number "},
    {"name": "Us", "note": "pipe shear velocity (ft/sec or m/sec) "},
    {"name": "Ff", "note": "Darcy-Weisbach friction factor "},
    {"name": "Av", "note": "Surface area per unit volume (area units/L) "},
    {"name": "Len", "note": "Pipe length (feet or meters)"},
]
"""The hydraulic variables defined in EPANET-MSX.
For reference, the valid values are provided in :numref:`table-msx-hyd-vars`.

.. _table-msx-hyd-vars:
.. table:: Valid hydraulic variables in multispecies quality model expressions.

    ============== ================================================
    **Name**       **Description**
    -------------- ------------------------------------------------
    ``D``          pipe diameter
    ``Kc``         pipe roughness coefficient
    ``Q``          pipe flow rate
    ``Re``         flow Reynolds number
    ``Us``         pipe shear velocity
    ``Ff``         Darcy-Weisbach friction factor
    ``Av``         pipe surface area per unit volume
    ``Len``        pipe length
    ============== ================================================

:meta hide-value:
"""

EXPR_FUNCTIONS = dict(
    abs=abs,
    sgn=sign,
    sqrt=sqrt,
    step=Heaviside,
    log=log,
    exp=exp,
    sin=sin,
    cos=cos,
    tan=tan,
    cot=cot,
    asin=asin,
    acos=acos,
    atan=atan,
    acot=acot,
    sinh=sinh,
    cosh=cosh,
    tanh=tanh,
    coth=coth,
    log10=_log10,
)
"""Mathematical functions available for use in expressions. See 
:numref:`table-msx-funcs` for a list and description of the 
different functions recognized. These names, case insensitive, are 
considered invalid when naming variables.

Additionally, the following SymPy names - ``Mul``, ``Add``, ``Pow``, 
``Integer``, ``Float`` - are used to convert numbers and symbolic 
functions; therefore, these five words, case sensitive, are also invalid
for use as variable names.

.. _table-msx-funcs:
.. table:: Functions defined for use in EPANET-MSX expressions.

    ============== ================================================================
    **Name**       **Description**
    -------------- ----------------------------------------------------------------
    ``abs``        absolute value (:func:`~sympy.functions.Abs`)
    ``sgn``        sign (:func:`~sympy.functions.sign`)
    ``sqrt``       square-root
    ``step``       step function (:func:`~sympy.functions.Heaviside`)
    ``exp``        natural number, `e`, raised to a power
    ``log``        natural logarithm
    ``log10``      base-10 logarithm (defined as internal function)
    ``sin``        sine
    ``cos``        cosine
    ``tan``        tangent
    ``cot``        cotangent
    ``asin``       arcsine
    ``acos``       arccosine
    ``atan``       arctangent
    ``acot``       arccotangent
    ``sinh``       hyperbolic sine
    ``cosh``       hyperbolic cosine
    ``tanh``       hyperbolic tangent
    ``coth``       hyperbolic cotangent
    ``*``          multiplication (:func:`~sympy.Mul`)
    ``/``          division (:func:`~sympy.Mul`)
    ``+``          addition (:func:`~sympy.Add`)
    ``-``          negation and subtraction (:func:`~sympy.Add`)
    ``^``          power/exponents (:func:`~sympy.Pow`)
    ``(``, ``)``   groupings and function parameters
    `numbers`      literal values (:func:`~sympy.Float` and :func:`~sympy.Integer`)
    ============== ================================================================

:meta hide-value:
"""

RESERVED_NAMES = (
    tuple([v["name"] for v in HYDRAULIC_VARIABLES])
    + tuple([k.lower() for k in EXPR_FUNCTIONS.keys()])
    + tuple([k.upper() for k in EXPR_FUNCTIONS.keys()])
    + tuple([k.capitalize() for k in EXPR_FUNCTIONS.keys()])
    + ("Mul", "Add", "Pow", "Integer", "Float")
)
"""The WNTR reserved names. This includes the MSX hydraulic variables
(see :numref:`table-msx-hyd-vars`) and the MSX defined functions 
(see :numref:`table-msx-funcs`).

:meta hide-value:
"""

_global_dict = dict()
for k, v in EXPR_FUNCTIONS.items():
    _global_dict[k.lower()] = v
    _global_dict[k.capitalize()] = v
    _global_dict[k.upper()] = v
for v in HYDRAULIC_VARIABLES:
    _global_dict[v["name"]] = symbols(v["name"])
_global_dict["Mul"] = Mul
_global_dict["Add"] = Add
_global_dict["Pow"] = Pow
_global_dict["Integer"] = Integer
_global_dict["Float"] = Float

EXPR_TRANSFORMS = (
    auto_symbol,
    auto_number,
    convert_xor,
)
"""The sympy transforms to use in expression parsing. See 
:numref:`table-sympy-transformations` for the list of transformations.

.. _table-sympy-transformations:
.. table:: Transformations used by WNTR when parsing expressions using SymPy.

    ========================================== ==================
    **Transformation**                         **Is used?**
    ------------------------------------------ ------------------
    ``lambda_notation``                        No
    ``auto_symbol``                            Yes
    ``repeated_decimals``                      No
    ``auto_number``                            Yes
    ``factorial_notation``                     No
    ``implicit_multiplication_application``    No
    ``convert_xor``                            Yes
    ``implicit_application``                   No
    ``implicit_multiplication``                No
    ``convert_equals_signs``                   No
    ``function_exponentiation``                No
    ``rationalize``                            No
    ========================================== ==================

:meta hide-value:
"""


class AnnotatedFloat(float):
    def __new__(self, value, note=None):
        return float.__new__(self, value)

    def __init__(self, value, note=None):
        float.__init__(value)
        self.note = note


@add_get(abbrev=True)
class VariableType(IntEnum):
    """The type of reaction variable.

    The following types are defined, and aliases of just the first character
    are also defined.

    .. rubric:: Enum Members
    .. autosummary::

        SPECIES
        CONSTANT
        PARAMETER
        TERM
        RESERVED

    .. rubric:: Class Methods
    .. autosummary::
        :nosignatures:

        get

    """

    SPECIES = 3
    """A chemical or biological water quality species"""
    TERM = 4
    """A functional term - ie named expression - for use in reaction expressions"""
    PARAMETER = 5
    """A reaction expression coefficient that is parameterized by tank or pipe"""
    CONSTANT = 6
    """A constant coefficient for use in reaction expressions"""
    RESERVED = 9
    """A 'variable' that is either a hydraulic variable or other reserved word"""
    S = SPEC = SPECIES
    T = TERM
    P = PARAM = PARAMETER
    C = CONST = CONSTANT
    R = RES = RESERVED


@add_get(abbrev=True)
class SpeciesType(IntEnum):
    """The enumeration for species type.

    .. warning:: These enum values are note the same as the MSX SpeciesType.

    .. rubric:: Enum Members

    .. autosummary::
        BULK
        WALL

    .. rubric:: Class Methods
    .. autosummary::
        :nosignatures:

        get

    """

    BULK = 1
    """bulk species"""
    WALL = 2
    """wall species"""
    B = BULK
    W = WALL


@add_get(abbrev=True)
class ReactionType(Enum):
    """What type of network component does this reaction occur in

    The following types are defined, and aliases of just the first character
    are also defined.

    .. rubric:: Enum Members
    .. autosummary::
        PIPE
        TANK

    .. rubric:: Class Methods
    .. autosummary::
        :nosignatures:

        get
    """

    PIPE = 1
    """The expression describes a reaction in pipes"""
    TANK = 2
    """The expression describes a reaction in tanks"""

    P = PIPE
    T = TANK


@add_get(abbrev=True)
class ExpressionType(Enum):
    """The type of reaction expression.

    The following types are defined, and aliases of just the first character
    are also defined.

    .. rubric:: Enum Members
    .. autosummary::

        EQUIL
        RATE
        FORMULA

    .. rubric:: Class Methods
    .. autosummary::
        :nosignatures:

        get

    """

    EQUIL = 1
    """used for equilibrium expressions where it is assumed that the expression supplied is being equated to zero"""
    RATE = 2
    """used to supply the equation that expresses the rate of change of the given species with respect to time as a function of the other species in the model"""
    FORMULA = 3
    """used when the concentration of the named species is a simple function of the remaining species"""

    E = EQUIL
    R = RATE
    F = FORMULA


class AbstractReaction(ABC):
    def __init__(self, species_name: str, *, note=None) -> None:
        """A water quality reaction definition.

        This abstract class must be subclassed.

        Arguments
        ---------
        species_name : str
            The name of the chemical or biological species being modeled using this reaction.


        Keyword Arguments
        -----------------
        note : str | dict | ENcomment, optional
            Supplementary information regarding this reaction, by default None (see :class:`~wntr.epanet.util.ENcomment` for dict structure).


        Raises
        ------
        TypeError
            if expression_type is invalid
        """
        if species_name is None:
            raise TypeError("The species_name cannot be None")
        self._species_name = species_name
        self.note = note

    @property
    def species_name(self) -> str:
        return self._species_name

    @abstractproperty
    def reaction_type(self) -> Enum:
        """The type of reaction or where this reaction occurs."""
        raise NotImplementedError

    def __str__(self) -> str:
        return "{}->{}".format(self.species_name, self.reaction_type.name)

    def __repr__(self) -> str:
        return (
            "{}(".format(self.__class__.__name__)
            + ", ".join(["{}={}".format(k, repr(getattr(self, k))) for k, v in self.to_dict().items()])
            + ")"
        )

    @abstractmethod
    def to_dict(self) -> dict:
        raise NotImplementedError


class AbstractVariable(ABC):
    """A multi-species water quality model variable.

    This abstract class must be extended before use. There are several concrete classes
    that inhert from this class, including
    :class:`~wntr.msx.msx.Species`,
    :class:`~wntr.msx.msx.Constant`,
    :class:`~wntr.msx.msx.Parameter`,
    and :class:`~wntr.msx.msx.Term`.
    See also the :class:`~wntr.msx.msx.MultispeciesModel`, which has the functions
    required to create these variables and define reactions.
    """

    def __init__(self, name: str, *, note=None) -> None:
        """Multi-species variable constructor arguments.

        Arguments
        ---------
        name : str
            The name/symbol for the variable. Must be a valid MSX variable name.

        Keyword Arguments
        -----------------
        note : str | dict | ENcomment, optional
            Supplementary information regarding this variable, by default None (see :class:`~wntr.epanet.util.ENcomment` for dict structure).
            As dict it can have two keys, "pre" and "post". See :class:`ENcomment`
            for more details.

        Raises
        ------
        KeyExistsError
            the name is already taken
        ValueError
            the name is a reserved word


        The following should only be used by model building functions, and the
        user should never need to pass these arguments.

        Other Parameters
        ----------------
        _vars : VariablesRegistry, optional
            the variables registry object of the model this variable was added to, by default None
        """
        if name in RESERVED_NAMES:
            raise ValueError("Name cannot be a reserved name")
        self.name: str = name
        """The name/ID of this variable, must be a valid EPANET/MSX ID"""
        self.note = note
        """A note related to this variable"""

    @abstractproperty
    def var_type(self) -> Enum:
        """The type of reaction variable"""
        raise NotImplementedError

    @abstractmethod
    def to_dict(self) -> Dict[str, Any]:
        """Represent the object as a dictionary"""
        raise NotImplementedError

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return (
            "{}(".format(self.__class__.__name__)
            + ", ".join(["{}={}".format(k, repr(getattr(self, k))) for k, v in self.to_dict().items()])
            + ")"
        )


class ReactionSystem(ABC):
    """Abstract class for reaction systems, which contains variables and reaction expressions.

    This class contains the functions necessary to perform as a mapping view onto the
    **variables** defined, by their name.
    """

    def __init__(self) -> None:
        self._vars = DisjointMapping()
        self._rxns = dict()

    @abstractmethod
    def add_variable(self, obj: AbstractVariable) -> None:
        """Add a variable to the system"""
        raise NotImplementedError

    @abstractmethod
    def add_reaction(self, obj: AbstractReaction) -> None:
        """Add a reaction to the system"""
        raise NotImplementedError

    @abstractmethod
    def variables(self):
        """A generator looping through all variables"""
        raise NotImplementedError

    @abstractmethod
    def reactions(self):
        """A generator looping through all reactions"""
        raise NotImplementedError

    @abstractmethod
    def to_dict(self):
        """Represent the reaction system as a dictionary"""
        raise NotImplementedError

    def __contains__(self, __key: object) -> bool:
        return self._vars.__contains__(__key)

    def __eq__(self, __value: object) -> bool:
        return self._vars.__eq__(__value)

    def __ne__(self, __value: object) -> bool:
        return self._vars.__ne__(__value)

    def __getitem__(self, __key: str) -> AbstractVariable:
        return self._vars.__getitem__(__key)

    def __iter__(self) -> Iterator:
        return self._vars.__iter__()

    def __len__(self) -> int:
        return self._vars.__len__()


class VariableValues(ABC):
    """Abstract class for a variable's network-specific values."""

    @abstractproperty
    def var_type(self) -> Enum:
        """Define what type of variable this network-specific data is for"""
        raise NotImplementedError

    @abstractmethod
    def to_dict(self) -> dict:
        """Represent the variable's network-specific values as a dictionary"""
        raise NotImplementedError


class NetworkData(ABC):
    """Abstract class containing network specific data.
    
    This class should be populated with things like initial quality,
    sources, parameterized values, etc.
    """

    @abstractmethod
    def to_dict(self) -> dict:
        """Represent the network specific data as a dictionary"""
        raise NotImplementedError


class AbstractModel(ABC):
    """Abstract water quality model."""

    def __init__(self, filename=None):
        self.name: str = None if filename is None else os.path.splitext(os.path.split(filename)[1])[0]
        """A name for the model, or the MSX model filename (no spaces allowed)"""
        self.title: str = None
        """The title line from the MSX file, must be a single line"""
        self.description: str = None
        """A longer description, note that multi-line descriptions may not be 
        represented well in dictionary form."""
        self._orig_file: str = filename
        self._options = None
        self._rxn_system: ReactionSystem = None
        self._net_data: NetworkData = None
        self._wn = None

    @abstractproperty
    def options(self):
        """The model options structure.

        Concrete classes should implement this with the appropriate typeing and
        also implement a setter method.
        """
        raise NotImplementedError

    @abstractproperty
    def reaction_system(self) -> ReactionSystem:
        """The reaction variables defined for this model.

        Concrete classes should implement this with the appropriate typing.
        """
        raise NotImplementedError

    @abstractproperty
    def network_data(self) -> NetworkData:
        """The network-specific values added to this model.

        Concrete classes should implement this with the appropriate typing.
        """
        raise NotImplementedError

    @abstractmethod
    def to_dict(self) -> dict:
        """Represent the model as a dictionary."""
        raise NotImplementedError

    @abstractclassmethod
    def from_dict(self, data: dict) -> "AbstractModel":
        """Create a new model from a dictionary."""
        raise NotImplementedError