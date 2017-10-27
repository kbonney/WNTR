"""
The wntr.network.elements module contains base classes for elements of a water network model.

"""

import enum
import numpy as np
import sys
import copy

if sys.version_info[0] == 2:
    from collections import MutableSequence
else:
    from collections.abc import MutableSequence

class Curve(object):
    """
    Curve class.

    Parameters
    ----------
    name : string
         Name of the curve
    curve_type :
         Type of curve. Options are Volume, Pump, Efficiency, Headloss.
    points :
         List of tuples with X-Y points.
         
         
    """
    def __init__(self, name, curve_type, points):
        self.name = name
        self.curve_type = curve_type
        self.points = copy.deepcopy(points)
        self.points.sort()
        self._headloss_function = None

    def __eq__(self, other):
        if type(self) != type(other):
            return False
        if self.name != other.name:
            return False
        if self.curve_type != other.curve_type:
            return False
        if self.num_points != other.num_points:
            return False
        for point1, point2 in zip(self.points, other.points):
            for value1, value2 in zip(point1, point2):
                if abs(value1 - value2) > 1e-8:
                    return False
        return True

    def __repr__(self):
        return '<Curve: {}, curve_type={}, points={}>'.format(repr(self.name), repr(self.curve_type), repr(self.points))

    def __hash__(self):
        return id(self)
    
    def __getitem__(self, index):
        return self.points.__getitem__(index)

    def __getslice__(self, i, j):
        return self.points.__getslice__(i, j)

    def __len__(self):
        return len(self.points)

    @property
    def num_points(self):
        return len(self.points)

    def _pump_curve(self, flow):
        pass
    
    def _single_point_pump_curve(self, flow):
        pass
    
    def _three_point_pump_curve(self, flow):
        pass
    
    def _multi_point_pump_curve(self, flow):
        pass
    
    def _variable_speed_pump_curve(self, flow):
        pass
    
    def _efficiency_curve(self, flow):
        pass
    
    def _volume_curve(self, level):
        pass
    
    def _headloss_curve(self, flow):
        pass


class Pattern(object):
    """Defines a multiplier pattern (series of multiplier factors)
    
    Parameters
    ----------
    name : str
        A unique name to describe the pattern (should be the same used when adding the pattern to the model)
    multipliers : list-like
        A list of multipliers that makes up the pattern; internally saved as a numpy array
    step_size : int
        The pattern timestep (in seconds)
    step_start : int
        Which pattern index goes with time=0, if not the first
    wrap : bool
        If true (the default), then the pattern repeats itself forever; if false, after the pattern
        has been exhausted, it will return 0.0
    
    """
    def __init__(self, name, multipliers=[], step_size=1, step_start=0, wrap=True):
        self.name = name
        """The name should be unique"""
        if isinstance(multipliers, (int, float)):
            multipliers = [multipliers]
        self._multipliers = np.array(multipliers)
        """The array of multipliers (list or numpy array)"""
        self.step_size = step_size
        self.step_start = step_start
        self.wrap = wrap
        """If wrap (default true) then repeat pattern forever, otherwise return 0 if exceeds length"""

    @classmethod
    def BinaryPattern(cls, name, step_size, start_time, end_time, duration):
        """Factory method to create a binary pattern (single instance of step up, step down)
        
        This class method is equivalent to using the old (WNTR<0.1.5) `WaterNetworkModel.add_pattern` method with the
        `start_time` and `end_time` attributes. 
        
        Parameters
        ----------
        name : str
            A unique name to describe the pattern (should be the same used when adding the pattern to the model)
        step_size : int
            The pattern timestep (in seconds)
        start_time : int
            The time at which the pattern turns "on" (1.0)
        end_time : int
            The time at which the pattern turns "off" (0.0)
        duration : int
            The length of the simulation out to which the "off" values should go
        
        Returns
        -------
        Pattern
            The new pattern object
        
        """
        patternstep = step_size
        patternlen = int(end_time/patternstep)
        patternstart = int(start_time/patternstep)
        patternend = int(end_time/patternstep)
        patterndur = int(duration/patternstep)
        pattern_list = [0.0]*patterndur
        pattern_list[patternstart:patternend] = [1.0]*(patternend-patternstart)
        return cls(name, multipliers=pattern_list, step_size=patternstep, wrap=False)
    
    @classmethod
    def _SquareWave(cls, name, step_size, length_off, length_on, first_on):
        raise NotImplementedError('Square wave currently unimplemented')
    
    def __eq__(self, other):
        if not type(self) == type(other):
            return False
        if self.name != other.name or \
           len(self) != len(other) or \
           self.step_size != other.step_size or \
           self.step_start != other.step_start or \
           self.wrap != other.wrap:
            return False
        return np.all(np.abs(self._multipliers-other._multipliers)<1.0e-10)

    def __hash__(self):
        return hash(self.name)
        
    def __str__(self):
        return '<Pattern "%s">'%self.name
        
    def __len__(self):
        return len(self._multipliers)
    
    @property
    def multipliers(self):
        """The actual multiplier values in an array"""
        return self._multipliers
    
    @multipliers.setter
    def multipliers(self, values):
        if isinstance(values, (int, float, complex)):
            self._multipliers = np.array([values])
        else:
            self._multipliers = np.array(values)

    def __getitem__(self, step):
        """Get the multiplier appropriate for step
        
        Parameters
        ----------
        step : int
            The index into the pattern to get a value
            
        Returns
        -------
        float
            The value at index `step`
        
        """
        nmult = len(self._multipliers)
        if nmult == 0:                          return 1.0
        elif self.wrap:                         return self._multipliers[int(step%nmult)]
        elif step < 0 or step >= nmult:         return 0.0
        return self._multipliers[step]

    def at(self, time):
        """The pattern value at 'time', given in seconds since start of simulation
        
        Parameters
        ----------
        time : int
            The time in seconds to get a value
            
        Returns
        -------
            The value at index calculated from the time
        
        """
        step = ((time+self.step_start)//self.step_size)
        nmult = len(self._multipliers)
        if nmult == 0:                          return 1.0
        elif self.wrap:                         return self._multipliers[int(step%nmult)]
        elif step < 0 or step >= nmult:         return 0.0
        return self._multipliers[step]
    __call__ = at


class TimeVaryingValue(object):
    """A simple time varying value.
    
    Provides a mechanism to calculate values based on a base value and a multiplier pattern.
    Uses __call__ with a `time` to calculate the appropriate value based on that time.
    
    Parameters
    ----------
    base : number
        A number that represents the baseline value for this variable
    pattern : Pattern, optional
        If None, then the value will be constant. Otherwise, the Pattern will be used.
    name : str
        A category, description, or other name that is useful to the user to describe this value
        
    Raises
    ------
    ValueError
        If `base` or `pattern` are invalid types
    
    """
    def __init__(self, base, pattern=None, name=None):
        if not isinstance(base, (int, float, complex)):
            raise ValueError('TimeVaryingValue->base must be a number')
        if isinstance(pattern, Pattern):
            self._pattern = pattern
        elif pattern is None:
            self._pattern = None
        else:
            raise ValueError('TimeVaryingValue->pattern must be a Pattern object or None')
        if base is None: base = 0.0
        self._base = base
        self._name = name
        
    def __nonzero__(self):
        return self._base
    __bool__ = __nonzero__

    def __str__(self):
        return repr(self)

    def __repr__(self):
        fmt = "<TimeVaryingValue: {}, {}, category={}>"
        return fmt.format(self._base, self._pattern, repr(self._name))
    
    @property
    def base_value(self):
        """The baseline value for this variable"""
        return self._base
    
    @property
    def pattern_name(self):
        """The name of the pattern used"""
        if self._pattern:
            return self._pattern.name
        return None
        
    @property
    def pattern(self):
        """The pattern object"""
        return self._pattern
    
    @property
    def name(self):
        """The name of this value"""
        return self._name
    
    def set_base_value(self, value):
        self._base = value
    
    def set_pattern(self, pattern):
        self._pattern = pattern
        
    def set_name(self, name):
        self._name = name
    
    def __getitem__(self, step):
        """Calculate the value at a specific step
        
        Parameters
        ----------
        step : int
            The index (not time!) to get a value for
            
        Returns
        -------
        float
            The value
        """
        
        if not self._pattern:
            return self._base
        return self._base * self._pattern[step]
    
    def at(self, time):
        """Calculate the value at a specific time
        
        Parameters
        ----------
        time : int
            The time (in seconds) to get a value for
            
        Returns
        -------
        float
            The value
        """
        if not self._pattern:
            return self._base
        return self._base * self._pattern.at(time)
    __call__ = at


class Pricing(TimeVaryingValue):
    """A value class for pump pricing based on an optional time pattern"""
    def __init__(self, base_price=None, pattern=None, category=None):
        super(Pricing, self).__init__(base=base_price, pattern=pattern, name=category)

    def __repr__(self):
        fmt = "<Pricing: {}, {}, category={}>"
        return fmt.format(self._base, self.pattern_name, repr(self._name))

    @property
    def category(self):
        return self._name

    @property
    def base_price(self):
        return self._base
    
    def __eq__(self, other):
        if type(self) == type(other) and \
           self.pattern == other.pattern and \
           self.category == other.category and \
           abs(self._base - other._base)<1e-10 :
            return True
        return False

class Speed(TimeVaryingValue):
    """A value class for pump speed based on a pattern"""
    def __init__(self, base_speed=None, pattern=None, pump_name=None):
        super(Speed, self).__init__(base=base_speed, pattern=pattern, name=pump_name)    

    def __repr__(self):
        fmt = "<Speed: {}, {}, pump_name={}>"
        return fmt.format(self._base, self.pattern_name, repr(self._name))

    @property
    def base_speed(self):
        return self._base
        
    @property
    def pump_name(self):
        return self._name

    def __eq__(self, other):
        if type(self) == type(other) and \
           self.pattern == other.pattern and \
           self.pump_name == other.pump_name and \
           abs(self._base - other._base)<1e-10 :
            return True
        return False


class Demand(TimeVaryingValue):
    """A value class for demand at a junction based on a pattern"""
    def __init__(self, base_demand=None, pattern=None, category=None):
        super(Demand, self).__init__(base=base_demand, pattern=pattern, name=category)
    
    def __repr__(self):
        fmt = "<Demand: base_demand={}, pattern={}, category={}>"
        return fmt.format(self._base, repr(self.pattern_name), repr(self._name))

    @property
    def category(self):
        return self._name

    @property
    def base_demand(self):
        return self._base
    
    @base_demand.setter
    def base_demand(self, value):
        self._base = value

    def demand_values(self, start_time, end_time, time_step):
        """Create a numpy array populated with the demand for a range of times, including end"""
        demand_times = range(start_time, end_time + time_step, time_step)
        demand_values = np.zeros((len(demand_times,)))
        for ct, t in enumerate(demand_times):
            demand_values[ct] = self.at(t)
        return demand_values

    def __eq__(self, other):
        if type(self) == type(other) and \
           self.pattern == other.pattern and \
           self.category == other.category and \
           abs(self._base - other._base)<1e-10 :
            return True
        return False


class ReservoirHead(TimeVaryingValue):
    """A value class for varying head based on a pattern"""
    def __init__(self, total_head=None, pattern=None, name=None):
        super(ReservoirHead, self).__init__(base=total_head, pattern=pattern, name=name)
    
    def __repr__(self):
        fmt = "<ReservoirHead: {}, {}>"
        return fmt.format(self._base, self.pattern_name)

    @property
    def total_head(self):
        return self._base

    def __eq__(self, other):
        if type(self) == type(other) and \
           self.pattern == other.pattern and \
           self.name == other.name and \
           abs(self._base - other._base)<1e-10 :
            return True
        return False

class Source(TimeVaryingValue):
    """A water quality source

    Parameters
    ----------
    name : string
         Name of the source

    node_name: string
        Injection node

    source_type: string
        Source type, options = CONCEN, MASS, FLOWPACED, or SETPOINT

    quality: float
        Source strength in Mass/Time for MASS and Mass/Volume for CONCEN, FLOWPACED, or SETPOINT

    pattern_name: string
        Pattern name

    """

    def __init__(self, name, node_name, source_type, quality, pattern):
        super(Source, self).__init__(base=quality, pattern=pattern, name=name)
        self.node_name = node_name
        self.source_type = source_type

    def __eq__(self, other):
        if not type(self) == type(other):
            return False
        if self.node_name == other.node_name and \
           self.source_type == other.source_type and \
           abs(self._base - other._base)<1e-10 and \
           self._pattern == other._pattern:
            return True
        return False

    def __repr__(self):
        fmt = "<Source: '{}', '{}', '{}', {}, {}>"
        return fmt.format(self.name, self.node_name, self.source_type, self._base, self._pattern_name)

    @property
    def quality(self):
        return self._base
    

class DemandList(MutableSequence):
    """List with specialized demand-specific calls and type checking.
    
    A demand list is a list of demands and can be used with all normal list-like commands.
    For example,
    
    >>> from wntr.network.elements import DemandList
    >>> dl = DemandList()
    >>> len(dl)
    0
    >>> dl.append( (0.5, None, None) )
    >>> len(dl)
    1
    >>> dl[0]
    <Demand: base_demand=0.5, pattern=None, category=None>
    
    The demand list does not have any attributes, but can be created by passing in demand objects
    or demand tuples as ``(base_demand, pattern, category_name)``
    
    
    """
    
    def __init__(self, *args):
        self._list = []
        for object in args:
            self.append(object)

    def __getitem__(self, index):
        """Get the demand at index <==> y = S[index]"""
        return self._list.__getitem__(index)
    
    def __setitem__(self, index, object):
        """Set demand and index <==> S[index] = object"""
        if isinstance(object, (list, tuple)) and len(object) in [2,3]:
            object = Demand(*object)
        elif not isinstance(object, Demand):
            raise ValueError('object must be a Demand or demand tuple')
        return self._list.__setitem__(index, object)
    
    def __delitem__(self, index):
        """Remove demand at index <==> del S[index]"""
        return self._list.__delitem__(index)

    def __len__(self):
        """Number of demands in list <==> len(S)"""
        return len(self._list)
    
    def __nonzero__(self):
        """True if demands exist in list NOT if demand is non-zero"""
        return len(self._list) > 0
    __bool__ = __nonzero__
    
    def __repr__(self):
        return '<DemandList: {}>'.format(repr(self._list))
    
    def insert(self, index, object):
        """S.insert(index, object) - insert object before index"""
        if isinstance(object, (list, tuple)) and len(object) in [2,3]:
            object = Demand(*object)
        elif not isinstance(object, Demand):
            raise ValueError('object must be a Demand or demand tuple')
        self._list.insert(index, object)
    
    def append(self, object):
        """S.append(object) - append object to the end"""
        if isinstance(object, (list, tuple)) and len(object) in [2,3]:
            object = Demand(*object)
        elif not isinstance(object, Demand):
            raise ValueError('object must be a Demand or demand tuple')
        self._list.append(object)
    
    def extend(self, iterable):
        """S.extend(iterable) - extend list by appending elements from the iterable"""
        for object in iterable:
            if isinstance(object, (list, tuple)) and len(object) in [2,3]:
                object = Demand(*object)
            elif not isinstance(object, Demand):
                raise ValueError('object must be a Demand or demand tuple')
            self._list.append(object)

    def clear(self):
        """S.clear() - remove all entries"""
        self._list = []

    def at(self, time, category=None):
        """Get the total demand at a given time - Demand objects must have been initialized with a step size"""
        demand = 0.0
        if category:
            for dem in self._list:
                if dem.category == category:  
                    demand += dem.at(time)
        else:
            for dem in self._list:
                demand += dem.at(time)
        return demand
    __call__ = at
    
    def base_demand_list(self, category=None):
        """A list of the base demands, optionally of a single category"""
        res = []
        for dem in self._list:
            if category is None or dem.category == category:
                res.append(dem.base_demand)
        return res

    def pattern_list(self, category=None):
        """A list of the patterns, optionally of a single category"""
        res = []
        for dem in self._list:
            if category is None or dem.category == category:
                res.append(dem.pattern)
        return res
    
    def category_list(self):
        """A list of all the pattern categories"""
        res = []
        for dem in self._list:
                res.append(dem.category)
        return res

    def demand_values(self, start_time, end_time, time_step):
        """Create a numpy array populated with the total demand for a range of times"""
        demand_times = range(start_time, end_time + time_step, time_step)
        demand_values = np.zeros((len(demand_times,)))
        for dem in self._list:
            for ct, t in enumerate(demand_times):
                demand_values[ct] += dem(t)
        return demand_values



class NodeType(enum.IntEnum):
    """
    An enum class for types of nodes.

    .. rubric:: Enum Members

    ==================  ==================================================================
    :attr:`~Junction`   Node is a :class:`~wntr.network.model.Junction`
    :attr:`~Reservoir`  Node is a :class:`~wntr.network.model.Reservoir`
    :attr:`~Tank`       Node is a :class:`~wntr.network.model.Tank`
    ==================  ==================================================================

    """
    Junction = 0
    Reservoir = 1
    Tank = 2

    def __init__(self, val):
        if self.name != self.name.upper():
            self._member_map_[self.name.upper()] = self
        if self.name != self.name.lower():
            self._member_map_[self.name.lower()] = self

    def __str__(self):
        return self.name

    def __eq__(self, other):
        return int(self) == int(other) and (isinstance(other, int) or \
               self.__class__.__name__ == other.__class__.__name__)


class LinkType(enum.IntEnum):
    """
    An enum class for types of links.

    .. rubric:: Enum Members

    ===============  ==================================================================
    :attr:`~CV`      Pipe with check valve
    :attr:`~Pipe`    Regular pipe
    :attr:`~Pump`    Pump
    :attr:`~Valve`   Any valve type (see following)
    :attr:`~PRV`     Pressure reducing valve
    :attr:`~PSV`     Pressure sustaining valve
    :attr:`~PBV`     Pressure breaker valve
    :attr:`~FCV`     Flow control valve
    :attr:`~TCV`     Throttle control valve
    :attr:`~GPV`     General purpose valve
    ===============  ==================================================================

    """
    CV = 0
    Pipe = 1
    Pump = 2
    PRV = 3
    PSV = 4
    PBV = 5
    FCV = 6
    TCV = 7
    GPV = 8
    Valve = 9

    def __init__(self, val):
        if self.name != self.name.upper():
            self._member_map_[self.name.upper()] = self
        if self.name != self.name.lower():
            self._member_map_[self.name.lower()] = self

    def __str__(self):
        return self.name

    def __eq__(self, other):
        return int(self) == int(other) and (isinstance(other, int) or \
               self.__class__.__name__ == other.__class__.__name__)


class LinkStatus(enum.IntEnum):
    """
    An enum class for link statuses.
    
    .. warning:: 
        This is NOT the class for determining output status from an EPANET binary file.
        The class for output status is wntr.epanet.util.LinkTankStatus.

    .. rubric:: Enum Members

    ===============  ==================================================================
    :attr:`~Closed`  Pipe/valve/pump is closed.
    :attr:`~Opened`  Pipe/valve/pump is open.
    :attr:`~Open`    Alias to "Opened"
    :attr:`~Active`  Valve is partially open.
    ===============  ==================================================================

    """
    Closed = 0
    Open = 1
    Opened = 1
    Active = 2
    CV = 3

    def __init__(self, val):
        if self.name != self.name.upper():
            self._member_map_[self.name.upper()] = self
        if self.name != self.name.lower():
            self._member_map_[self.name.lower()] = self

    def __str__(self):
        return self.name

    def __eq__(self, other):
        return int(self) == int(other) and (isinstance(other, int) or \
               self.__class__.__name__ == other.__class__.__name__)

