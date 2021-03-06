"""
Multinest stopping criteria
===========================

Check whether a MultiNest scan is close to stopping by reading output
files.
"""

from __future__ import print_function
from os.path import isfile
from warnings import warn
from pprint import pformat
from numpy import log, exp, loadtxt, mean

PREAMBLE = r"""Four stopping criteria are applied per mode:

    mode_stop = 1. OR 2. OR 3. OR 4.

    1a. delta_max < tol
    1b. n_rejected - n_live > 50
    1. 1a. AND 1b.
    2. n_live_mode < n_dims + 1
    3. ln like_max - ln min_like <= 1E-4
    4. n_rejected >= max_iter

where we define delta_max = like_max * volume / evidence in a mode.

Once all modes have stopped, MultiNest stops.

Most modes eventually stop via criteria 1. 1b. is usually satisfied long
before 1a.

Monitor progression of scan by tracking progress of ln_delta_max towards ln_tol
per mode.

The *z_trapezoidal* evidence is that found by summing \int L dX at each iteration
of the MN algorithm with the trapezoidal rule.

The *z_trapezoidal_plus_active* evidence is the trapezoidal evidence *plus* evidence
remaining in the active live points, estimated as expected(like) * vol.
"""

################################################################################

def safe_loadtxt(name, fill=0.):
    """
    :param name: Name of file
    :type name: str

    :returns: result of np.loadtxt
    :rtype: list
    """

    def safe_float(str_float):
        """
        :returns: Float of string
        :rtype: float
        """
        try:
            return float(str_float)
        except ValueError:
            return fill

    with open(name) as file_:
        n_cols = len(file_.readline().split())

    safe_float_dict = dict.fromkeys(range(n_cols), safe_float)
    return loadtxt(name, unpack=True, converters=safe_float_dict)

def _error_ln_evidence(mode_):
    """
    :param mode: Information about a single mode
    :type mode: dict

    :returns: Error on log evidence
    :rtype: float
    """
    info = mode_["ln_z_trapezium_info"]
    n_live = mode_["n_live"]
    return (abs(info) / n_live)**0.5



_BOOL_STRING = lambda string: string == "T"
MAX_LEN = 70
TRIM = lambda string: string[:MAX_LEN]



################################################################################


def print_snapshot(root, tol=float("inf"), maxiter=float("inf")):
    """
    Make and print snapshot of MultiNest scan.

    :param root: Prefix of MultiNest output filenames (root)
    :type root: string
    :param tol: MultiNest evidence tolerance factor (tol)
    :type tol: float
    :param maxiter: MultiNest maximum number of iterations (maxiter)
    :type maxiter: int
    """

    # Make snapshot

    information = snapshot(root, tol=tol, maxiter=maxiter)

    # Print information

    tformat = lambda title: (" " + title + " ").center(80, '=')

    print(tformat("Check MultiNest stopping criteria"), end="\n\n")
    print(PREAMBLE, end="\n\n")

    print(tformat("Global information"), end="\n\n")
    print(pformat(information["global"]), end="\n\n")

    # Print per mode information

    for mode_number, mode in sorted(information["modes"].items()):
        mode_info = "Mode: %s" % mode_number
        print(tformat(mode_info), end="\n\n")
        print(pformat(mode), end="\n\n")


def snapshot(root, tol=0.1, maxiter=float("inf")):
    """
    :param root: Prefix of MultiNest output filenames (root)
    :type root: string
    :param tol: MultiNest evidence tolerance factor (tol)
    :type tol: float
    :param maxiter: MultiNest maximum number of iterations (maxiter)
    :type maxiter: int

    :returns: All information about MultiNest scan
    :rtype: dict
    """
    assert tol > 0., "tol <= 0: %s" % tol
    assert maxiter > 0, "maxiter <= 0: %s" % maxiter

    # Dictionary for global information about results
    global_ = dict()

    # Fetch arguments
    global_["tol"] = tol
    global_["ln_tol"] = log(global_["tol"])
    global_["maxiter"] = maxiter
    global_["root"] = root

    # Check *resume.dat, *phys_live.points and *live.points
    resume_name = TRIM(global_["root"] + "resume.dat")
    phys_live_name = TRIM(global_["root"] + "phys_live.points")
    live_name = TRIM(global_["root"] + "live.points")

    assert isfile(resume_name), "Cannot find: %s" % resume_name
    assert isfile(phys_live_name), "Cannot find: %s" % phys_live_name
    assert isfile(live_name), "Cannot find: %s" % live_name

    # Read data from *resume.dat, *phys_live.points and *live.points

    phys_live = safe_loadtxt(phys_live_name)
    live = safe_loadtxt(live_name)
    resume = map(str.split, open(resume_name))
    global_resume = resume[:4]  # General information
    modes_resume = resume[4:]  # Mode-specific information

    # Check first 4 lines of *resume.dat
    mean_shape = [1, 4, 2, 1]
    shape = map(len, global_resume)
    assert mean_shape == shape, "Wrong format: %s" % resume_name

    ############################################################################

    # Read information from *phys_live.points and *live.points

    ln_like = phys_live[-2]
    global_["ln_like_max"] = max(ln_like)
    global_["like_max"] = exp(global_["ln_like_max"])
    global_["like_mean"] = mean(exp(ln_like))
    global_["chi_squared_min"] = -2. * global_["ln_like_max"]
    global_["n_params"] = phys_live.shape[0] - 2
    global_["n_dims"] = live.shape[0] - 1

    ############################################################################

    # Read information about *global* evidence etc from *resume.dat

    # Read whether live-points generated
    global_["gen_live_completed"] = not _BOOL_STRING(global_resume[0][0])

    # Read number of rejected points
    global_["n_rejected"] = int(global_resume[1][0])
    assert global_["n_rejected"] >= 0

    # Read number of likelihood calls
    global_["n_like_calls"] = int(global_resume[1][1])
    assert global_["n_like_calls"] >= 0

    # Read number of modes
    global_["n_modes"] = int(global_resume[1][2])
    assert global_["n_modes"] >= 0

    # Read number of live points
    global_["n_live"] = int(global_resume[1][3])
    assert global_["n_live"] >= 0

    # Read total log evidence
    global_["ln_z_trapezium"] = float(global_resume[2][0])

    # Read error of total log evidence
    global_["ln_z_trapezium_info"] = float(global_resume[2][1])

    # Read whether ellipsoidal sampling
    global_["ellipsoidal"] = _BOOL_STRING(global_resume[3][0])

    ############################################################################

    # Read information about *branches* from *resume.dat

    modes = {m: dict([["mode", m]]) for m in range(global_["n_modes"])}

    for mode in modes.values():

        mode["branch_number"] = list()
        mode["branch_line"] = list()

        branch_line = modes_resume.pop(0)
        assert len(branch_line) == 1

        # Read number of branches in mode
        branch_number = int(branch_line[0])
        assert branch_number >= 0
        mode["branch_number"].append(branch_number)

        # Read unknown information about branches. This corresponds to
        # ic_brnch(i,1:ic_nBrnch(i),1),ic_brnch(i,1:ic_nBrnch(i),2)
        # I don't fully understand expected format of these lines.
        if branch_number:
            branch_line = modes_resume.pop(0)
            # assert len(branch_line) == 2 * branch_number, branch_line
            mode["branch_line"].append(branch_line)

    ############################################################################

    # Read information about *modes* from *resume.dat

    for mode in modes.values():

        mode_line = modes_resume.pop(0)
        assert len(mode_line) == 4

        # Read whether mode stopped
        mode["stop"] = _BOOL_STRING(mode_line[0])

        # Read unknown information about mode
        mode["ic_reme - possibly whether this node has children"] = str(mode_line[1])
        mode["ic_fNode - possibly indicates parent mode"] = str(mode_line[2])

        # Read number of live points in mode
        mode["n_live"] = int(mode_line[3])
        assert mode["n_live"] >= 0

        mode_line = modes_resume.pop(0)
        assert len(mode_line) == 3

        # Read volume in mode
        mode["vol"] = float(mode_line[0])
        assert mode["vol"] >= 0.

        # Read log evidence in mode
        try:
            mode["ln_z_trapezium"] = float(mode_line[1])
        except ValueError:
            mode["ln_z_trapezium"] = -1E100

        # Read error of log evidence in mode
        mode["ln_z_trapezium_info"] = float(mode_line[2])

        # Guess whether in constant efficiency mode by whether next line
        # is length 1
        if "ceff" not in global_:
            global_["ceff"] = bool(modes_resume) and len(modes_resume[0]) == 1

        # Read unknown information about constant efficiency mode
        if global_["ceff"]:

            mode_line = modes_resume.pop(0)
            assert len(mode_line) == 1

            mode["ceff_unknown"] = str(mode_line[0])

    # Should have parsed all lines
    assert not modes_resume, "Data not parsed: %s" % modes_resume

    ############################################################################

    # Extra global calculations

    global_["z_trapezium"] = exp(global_["ln_z_trapezium"])
    global_["ln_z_trapezium_error"] = _error_ln_evidence(global_)
    global_["z_trapezium_error"] = global_["ln_z_trapezium_error"] * global_["z_trapezium"]
    global_["stop_1b"] = global_["n_rejected"] - global_["n_live"] > 50
    global_["stop_4"] = global_["n_rejected"] >= global_["maxiter"]
    global_["stop"] = all([mode["stop"] for mode in modes.values()])
    if global_["stop"] and not global_["stop_1b"]:
        warn("Unusual convergence - very few rejected points")

    ############################################################################

    # Extra calculations per mode

    for n_mode, mode in modes.iteritems():

        mode["z_trapezium"] = exp(mode["ln_z_trapezium"])

        if mode["n_live"] > 0:

            # Column of log likelihood for this mode
            mode_ln_like = phys_live[:, phys_live[-1] == n_mode + 1][-2]

            mode["ln_like_max"] = max(mode_ln_like)
            mode["like_max"] = exp(mode["ln_like_max"])

            mode["ln_like_min"] = min(mode_ln_like)
            mode["like_min"] = exp(mode["ln_like_min"])

            mode["like_mean"] = mean(exp(mode_ln_like))
            mode["ln_like_mean"] = mean(mode_ln_like)

            mode["chi_squared_min"] = -2. * mode["ln_like_max"]
            mode["chi_squared_max"] = -2. * mode["ln_like_min"]
            mode["chi_squared_mean"] = -2. * mode["ln_like_mean"]

            mode["ln_delta_max"] = log(mode["vol"]) + mode["ln_like_max"] - mode["ln_z_trapezium"]
            mode["delta_max"] = exp(mode["ln_delta_max"])
            mode["ln_delta_mean"] = log(mode["vol"]) + log(mode["like_mean"]) - mode["ln_z_trapezium"]
            mode["delta_mean"] = exp(mode["ln_delta_mean"])
            mode["z_active"] = mode["like_mean"] * mode["vol"]

            mode["ln_z_trapezium_error"] = _error_ln_evidence(mode)
            mode["z_trapezium_error"] = mode["ln_z_trapezium_error"] * mode["z_trapezium"]

            mode["z_trapezium_plus_active"] = mode["z_trapezium"] + mode["z_active"]

            mode["stop_1a"] = mode["delta_max"] < global_["tol"]
            mode["stop_1b"] = global_["stop_1b"]
            mode["stop_1"] = mode["stop_1a"] and mode["stop_1b"]
            mode["stop_2"] = mode["n_live"] > global_["n_dims"] + 1
            mode["stop_3"] = mode["ln_like_max"] - mode["ln_like_min"] <= 1E-4
            mode["stop_4"] = global_["stop_4"]

            stop = (mode["stop_1"] or mode["stop_2"] or
                    mode["stop_3"] or mode["stop_4"])

            if not mode["stop"] == stop:
                warn("Inconsistent stopping criteria. "
                     "The assumed tol = {} may be too small".format(tol))


        else:
            mode["z_active"] = 0.
            mode["z_trapezium_plus_active"] = mode["z_trapezium"]

    ############################################################################

    # Sum provisional evidence per mode

    global_["z_trapezium_plus_active"] = sum([mode["z_trapezium_plus_active"] for mode in modes.itervalues()])

    ############################################################################

    # Combine information into a single dictionary
    information = {"modes": modes, "global": global_}

    return information
