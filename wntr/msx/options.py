# coding: utf-8
"""Options for multispecies reaction models.
"""

import logging
from typing import Dict, List, Literal, Union

from wntr.network.options import _OptionsBase

logger = logging.getLogger(__name__)


class MsxReportOptions(_OptionsBase):
    """
    Options related to EPANET-MSX report outputs.
    """

    def __init__(
        self,
        pagesize: list = None,
        report_filename: str = None,
        species: Dict[str, bool] = None,
        species_precision: Dict[str, float] = None,
        nodes: Union[Literal["ALL"], List[str]] = None,
        links: Union[Literal["ALL"], List[str]] = None,
    ):
        """
        Options related to EPANET-MSX report outputs.

        Parameters
        ----------
        report_filename : str
            Provides the filename to use for outputting an EPANET report file,
            by default this will be the prefix plus ".rpt".

        species : dict[str, bool]
            Output species concentrations

        species_precision : dict[str, float]
            Output species concentrations with the specified precision

        nodes : None, "ALL", or list
            Output node information in report file. If a list of node names is provided,
            EPANET only provides report information for those nodes.

        links : None, "ALL", or list
            Output link information in report file. If a list of link names is provided,
            EPANET only provides report information for those links.

        pagesize : str
            Page size for EPANET report output

        """
        self.pagesize = pagesize
        """The pagesize for the report"""
        self.report_filename = report_filename
        """The prefix of the report filename (will add .rpt)"""
        self.species = species if species is not None else dict()
        """Turn individual species outputs on and off, by default no species are output"""
        self.species_precision = species_precision if species_precision is not None else dict()
        """Set the output precision for the concentration of a specific species"""
        self.nodes = nodes
        """A list of nodes to print output for, or 'ALL' for all nodes, by default None"""
        self.links = links
        """A list of links to print output for, or 'ALL' for all links, by default None"""

    def __setattr__(self, name, value):
        if name not in ["pagesize", "report_filename", "species", "nodes", "links", "species_precision"]:
            raise AttributeError("%s is not a valid attribute of ReportOptions" % name)
        self.__dict__[name] = value


class MsxSolverOptions(_OptionsBase):
    """
    Multispecies quality model options.
    """

    def __init__(
        self,
        timestep: int = 360,
        area_units: str = "M2",
        rate_units: str = "MIN",
        solver: str = "RK5",
        coupling: str = "NONE",
        atol: float = 1.0e-4,
        rtol: float = 1.0e-4,
        compiler: str = "NONE",
        segments: int = 5000,
        peclet: int = 1000,
        # global_initial_quality: Dict[str, float] = None,
        report: MsxReportOptions = None,
    ):
        """
        Multispecies quality model options.

        Parameters
        ----------
        timestep : int >= 1
            Water quality timestep (seconds), by default 60 (one minute).
        area_units : str, optional
            The units of area to use in surface concentration forms, by default ``M2``. Valid values are ``FT2``, ``M2``, or ``CM2``.
        rate_units : str, optional
            The time units to use in all rate reactions, by default ``MIN``. Valid values are ``SEC``, ``MIN``, ``HR``, or ``DAY``.
        solver : str, optional
            The solver to use, by default ``RK5``. Options are ``RK5`` (5th order Runge-Kutta method), ``ROS2`` (2nd order Rosenbrock method), or ``EUL`` (Euler method).
        coupling : str, optional
            Use coupling method for solution, by default ``NONE``. Valid options are ``FULL`` or ``NONE``.
        atol : float, optional
            Absolute concentration tolerance, by default 0.01 (regardless of species concentration units).
        rtol : float, optional
            Relative concentration tolerance, by default 0.001 (±0.1%).
        compiler : str, optional
            Whether to use a compiler, by default ``NONE``. Valid options are ``VC``, ``GC``, or ``NONE``
        segments : int, optional
            Maximum number of segments per pipe (MSX 2.0 or newer only), by default 5000.
        peclet : int, optional
            Peclet threshold for applying dispersion (MSX 2.0 or newer only), by default 1000.
            report : ReportOptions or dict
            Options on how to report out results.

        """
        self.timestep: int = timestep
        """The timestep, in seconds, by default 360"""
        self.area_units: str = area_units
        """The units used to express pipe wall surface area where, by default FT2. Valid values are FT2, M2, and CM2."""
        self.rate_units: str = rate_units
        """The units in which all reaction rate terms are expressed, by default HR. Valid values are HR, MIN, SEC, and DAY."""
        self.solver: str = solver
        """The solver to use, by default EUL. Valid values are EUL, RK5, and ROS2."""
        self.coupling: str = coupling
        """Whether coupling should occur during solving, by default NONE. Valid values are NONE and FULL."""
        self.rtol: float = rtol
        """The relative tolerance used during solvers ROS2 and RK5, by default 0.001 for all species. Can be overridden on a per-species basis."""
        self.atol: float = atol
        """The absolute tolerance used by the solvers, by default 0.01 for all species regardless of concentration units. Can be overridden on a per-species basis."""
        self.compiler: str = compiler
        """A compier to use if the equations should be compiled by EPANET-MSX, by default NONE. Valid options are VC, GC and NONE."""
        self.segments: int = segments
        """The number of segments per-pipe to use, by default 5000."""
        self.peclet: int = peclet
        """The threshold for applying dispersion, by default 1000."""
        self.report: MsxReportOptions = MsxReportOptions.factory(report)
        """The reporting output options."""

    def __setattr__(self, name, value):
        if name == "report":
            if not isinstance(value, (MsxReportOptions, dict, tuple, list)):
                raise ValueError("report must be a ReportOptions or convertable object")
            value = MsxReportOptions.factory(value)
        elif name in {"timestep"}:
            try:
                value = max(1, int(value))
            except ValueError:
                raise ValueError("%s must be an integer >= 1" % name)
        elif name in ["atol", "rtol"]:
            try:
                value = float(value)
            except ValueError:
                raise ValueError("%s must be a number", name)
        elif name in ["segments", "peclet"]:
            try:
                value = int(value)
            except ValueError:
                raise ValueError("%s must be a number", name)
        elif name not in ["area_units", "rate_units", "solver", "coupling", "compiler"]:
            raise ValueError("%s is not a valid member of MultispeciesOptions")
        self.__dict__[name] = value

    def to_dict(self):
        """Dictionary representation of the options"""
        return dict(self)
