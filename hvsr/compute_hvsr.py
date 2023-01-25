"""
 
 USAGE:

 getStationChannelBaseline.py net=netName sta=staName loc=locCode {chan=chanCode} start=2007-03-19
 end=2008-10-28 {plot=[0, 1] verbose=[0, 1] percentlow=[10] percenthigh=[90] x_type=[period,frequency]}

 getStationChannelBaseline.py net=IU sta=ANMO loc=00 chan=BHZ start=2002-11-20 end=2008-11-20 plot=1
 verbose=1 percentlow=10 percenthigh=90

 the default values for the parameters between {} may be provided in the parameter file


 REFERENCES:
   Albarello, Dario & Lunedei, Enrico. (2013). Combining horizontal ambient vibration components for H/V spectral ratio
              estimates. Geophysical Journal International. 194. 936-951. 10.1093/gji/ggt130.

   Francisco J Sanchez-Sesma, Francisco & Rodriguez, Miguel & Iturraran-Viveros, Ursula & Luzn, Francisco & Campillo,
              Michel & Margerin, Ludovic & Garcia-Jerez, Antonio & Suarez, Martha & Santoyo, Miguel &
              Rodriguez-Castellanos, A. (2011). A theory for microtremor H/V spectral ratio: Application for a
              layered medium. Geophysical Journal International. 186. 221-225. 10.1111/j.1365-246X.2011.05064.x.

   Guidelines for the Implementation of the H/V Spectral Ratio Technique on Ambient Vibrations, December 2004
              SESAME European research project WP12 - Deliverable D23.12, European Commission - Research General
              Directorate Project No. EVG1-CT-2000-00026 SESAME.
              ftp://ftp.geo.uib.no/pub/seismo/SOFTWARE/SESAME/USER-GUIDELINES/SESAME-HV-User-Guidelines.pdf

"""

version = 'V.2020.155'

import os
import sys
import numpy as np

from scipy.signal import argrelextrema

import matplotlib

import math

import time
import urllib
import xml.etree.ElementTree as ET

import matplotlib.pyplot as plt
from matplotlib.offsetbox import AnchoredText

# Import the HVSR parameters and libraries.
hvsrDirectory = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

paramPath = os.path.join(hvsrDirectory, 'param')
libPath = os.path.join(hvsrDirectory, 'lib')

sys.path.append(paramPath)
sys.path.append(libPath)

import fileLib as fileLib
import msgLib as msgLib
import computeHVSR_modified as param

script = os.path.basename(__file__)

greek_chars = {'sigma': u'\u03C3', 'epsilon': u'\u03B5', 'teta': u'\u03B8'}
channel_order = {'Z': 0, '1': 1, 'N': 1, '2': 2, 'E': 2}
separator_character = '='

t0 = time.time()
display = True
max_rank = 0
plotRows = 4


def usage():
    """The usage message.
    """
    print('\n\n{} ({}):'.format(script, version))
    print('\nThis script uses IRIS DMC\'s MUSTANG noise-pdf web service (http://service.iris.edu/mustang/) to\n'
          'compute  horizontal-to-vertical spectral ratio (HVSR) and obtain the predominant frequency at the station\n'
          'site. The amplitude of the HVSR curves represent the ratio of the smoothed amplitude spectra for the \n'
          'horizontal and vertical components as obtained from PSDs. Script provides the following options:\n'
          '  - Remove PSDs that fall outside the station noise baseline, as computed by \n'
          '    computeStationChannelBaseline.py script (parameter removeoutliers=0|1)\n'
          '  - Compute HVSR using one of the methods below (parameter: method=1|2|3|4|5|6)\n'
          '    For a review o0f methods 2-6 see Albarello and Lunedei (2013). \n'
          '\t\t(1) DFA, Diffuse Field Assumption method (Sanchez-Sesma et al., 2011)\n'
          '\n\t\tNOTE: The MUSTANG noise-psd web service Power Spectral Density estimate for seismic channels are\n'
          '\t\t      computed using the algorithm outlined at:\n'
          '\t\t      http://service.iris.edu/mustang/noise-psd/docs/1/help/\n'
          '\t\t      This algorithm involves averaging and normalization that may result in smoothing of some of \n'
          '\t\t      the peaks that may otherwise be observed by direct computation of FFT and DFA. The peaks\n'
          '\t\t      are used  by this script for the predominant frequency determination only.\n\n'
          '\t\t(2) arithmetic mean, (HN + HE)/2\n'
          '\t\t(3) geometric mean, sqrt(HN x HE)\n'
          '\t\t(4) vector summation, sqrt(HN^2 + HE^2)\n'
          '\t\t(5) quadratic mean, sqrt(HN^2 + HE^2)/2\n'
          '\t\t(6) maximum horizontal value, max {HN, HE}\n'
          '  - Output a peak rank report with ranking based on SESAME 2004 (modified and not available for DFA method'
          ')\n\n')
    print('\n\nUsage:\n{} net=netName sta=staName loc=locCode chan=chanCodes start=2013-01-01 end=2013-01-01\n'
          'plot=[0, 1] plotbad=[0|1] plotpsd=[0|1] plotpdf=[0|1] plotnnm=[0|1] verbose=[0|1] ymax=[maximum Y value]\n'
          'xtype=[frequency|period] n=[number of segments] removeoutliers=[0|1] method=[1-6] showplot=[0|1]'
          .format(script))
    print('\nnet\t\tstation network name'
          '\nsta\t\tstation name'
          '\nloc\t\tstation location code'
          '\nchan\t\tstation channel code (separate multiple channel codes by comma); \n\t\tdefault: {}'
          '\nxtype\t\tX-axis  type; default: {}'
          '\nstart\t\tstart date of the interval for which HVSR to be computed (format YYYY-MM-DD).'
          '\n\t\tThe start day begins at 00:00:00 UTC'
          '\nend\t\tend date of the interval for which station baseline is computed (format YYYY-MM-DD).'
          '\n\t\tThe end day ends at 23:59:59 UTC'
          '\n\n\t\tNOTE: PSD segments will be limited to those starting between start (inclusive) and '
          '\n\t\tend (exclusive) except when start and end are the same (in that case, the range will '
          '\n\t\tcover start day only).'
          '\n\nverbose\t\tRun in verbose mode to provide informative messages [0=no, 1=yes];'
          '\n\t\tdefault:{}'
          '\nplotbad\t\tplot rejected PSDs (float) if "plotpsd" option is selected; default {}'
          '\nplotnnm\t\tplot the New Noise Models [0|1], active if plot=1; default {}'
          '\nplotpsd\t\tplot PSDs; default {}'
          '\nplotpdf\t\tplot PSD\\DFs; default {}'
          '\nymax\t\tmaximum Y values; default {}'
          '\nn\t\tbreak start-end interval into \'n\' segments; default {}'
          '\nremoveoutliers\tremove PSDs that fall outside the station noise baseline; default {}'
          '\nymax\t\tmcompute HVSR using method (see above); default {}'
          '\nshowplot\tturn plot display on/off default is {} (plot file is generated for both options)'
          .format(param.chan, param.xtype, param.verbose, param.plotbad, param.plotnnm, param.plotpsd, param.plotpdf,
                  param.yLim[1],
                  param.n, param.removeoutliers, param.method, param.showplot))
    print('\n\nExamples:'
          '\n{} net=TA sta=TCOL loc=-- chan=BHZ,BHN,BHE start=2013-01-01 end=2013-01-01 plot=1 plotbad=0 '
          'plotpsd=0 plotpdf=1 verbose=1 ymax=5 xtype=frequency n=1 removeoutliers=0 method=4'.format(script))
    print('\n{} net=TA sta=TCOL loc=-- chan=BHZ,BHN,BHE start=2013-01-01 end=2013-02-01 plot=1 plotbad=0 '
          'plotpsd=0 plotpdf=1 verbose=1 ymax=5 xtype=frequency n=1 removeoutliers=1 method=4'.format(script))
    print('\n{} net=TA sta=M22K loc= chan=BHZ,BHN,BHE start=2017-01-01 end=2017-02-01 plot=1 plotbad=0 '
          'plotpsd=0 plotpdf=1 verbose=1 ymax=6 xtype=frequency n=1 removeoutliers=0 method=4'.format(script))
    print('\n{} net=TA sta=E25K loc= chan=BHZ,BHN,BHE start=2017-01-01 end=2017-02-01 plot=1 plotbad=0 '
          'plotpsd=0 plotpdf=1 verbose=1 ymax=5 xtype=frequency n=1 removeoutliers=0 method=4'.format(script))
    print('\n{} net=TA sta=E25K loc= chan=BHZ,BHN,BHE start=2017-07-01 end=2017-08-01 plot=1 plotbad=0 '
          'plotpsd=0 plotpdf=1 verbose=1 ymax=5 xtype=frequency n=1 removeoutliers=0 method=4'.format(script))
    print ('\n\nReferences:'
           '\nAlbarello, Dario & Lunedei, Enrico. (2013). Combining horizontal ambient vibration components for H/V \n'
           '\tspectral ratio estimates. Geophysical Journal International. 194. 936-951. 10.1093/gji/ggt130.\n'
           '\nFrancisco J Sanchez-Sesma, Francisco & Rodriguez, Miguel & Iturraran-Viveros, Ursula & Luzon, Francisco\n'
           '\t& Campillo, Michel & Margerin, Ludovic & Garcia-Jerez, Antonio & Suarez, Martha & Santoyo, Miguel &\n'
           '\nPeterson, J. (1993). Observations and modeling of seismic background noise, U.S. Geological Survey\n'
           '\topen-file report (Vol. 93-322, p. 94). Albuquerque: U.S. Geological Survey.\n'
           '\nRodriguez-Castellanos, A. (2011). A theory for microtremor H/V spectral ratio: Application for a\n'
           '\tlayered medium. Geophysical Journal International. 186. 221-225. 10.1111/j.1365-246X.2011.05064.x.\n'
           '\nGuidelines for the Implementation of the H/V Spectral Ratio Technique on Ambient Vibrations, December\n'
           '\t2004  Project No. EVG1-CT-2000-00026 SESAME.\n'
           '\t\tftp://ftp.geo.uib.no/pub/seismo/SOFTWARE/SESAME/USER-GUIDELINES/SESAME-HV-User-Guidelines.pdf')

    print ('\n\n\n')


def check_mark():
    """The default Windows terminal is not able to display the check mark character correctly.
       This function returns another displayable character if platform is Windows"""
    check = get_char(u'\u2714')
    if sys.platform == 'win32':
        check = get_char(u'\u039E')
    return check


def get_char(in_char):
    """Output character with proper encoding/decoding"""
    if in_char in greek_chars.keys():
        out_char = greek_chars[in_char].encode(encoding='utf-8')
    else:
        out_char = in_char.encode(encoding='utf-8')
    return out_char.decode('utf-8')


def time_it(_t):
    """Compute elapsed time since the last call."""
    t1 = time.time()
    dt = t1 - _t
    t = _t
    if dt > 0.05:
        print(f'[TIME] {dt:0.1f} s', flush=True)
        t = t1
    return t


def date_range(_start, _end, _interval):
    """Break an interval to date ranges
       this is used to avoid large requests that get rejected.
    """
    if _interval <= 1:
        _date_list = [_start, _end]
    else:
        _date_list = list()
        from datetime import datetime
        start_t = datetime.strptime(_start, '%Y-%m-%d')
        end_t = datetime.strptime(_end, '%Y-%m-%d')
        diff = (end_t - start_t) / _interval
        if diff.days <= 1:
            _date_list = [_start, _end]
        else:
            for _index in range(_interval):
                _date_list.append((start_t + diff * _index).strftime('%Y-%m-%d'))
            _date_list.append(end_t.strftime('%Y-%m-%d'))
    return _date_list


def print_peak_report(_station_header, _report_header, _peak, _reportinfo, _min_rank):
    """print a report of peak parameters"""
    _index = list()
    _rank = list()

    if report_information:
        print("--------------------------------------------")
        print(param.reportDirectory)
        print(get_param(args, 'start', msgLib, None))
        print(fileLib.baselineFileName(network, station, location, channel))
        print("--------------------------------------------")

        report_file_name = os.path.join(param.reportDirectory, get_param(args, 'start', msgLib, None) +"." + fileLib.baselineFileName(
            network, station, location, channel))

        print(report_file_name)
        

        # In mac(python 3) the following statement works perfectly with just open without encoding, but
        # in windows(w10, python3) this is is not an option and we have to include the encoding='utf-8' param.
        report_file = open(report_file_name, 'w', encoding='utf-8')

        # Write the report to the report file.
        report_file.write('\n\nPeaks:\n'
                          'Parameters and ranking (A0: peak amplitude, f0: peak frequency, {}: satisfied):\n\n'
                          '\t- amplitude clarity conditions:\n'
                          '\t\t. there exist one frequency f-, lying between f0/4 and f0, such that A0 / A(f-) > 2\n'
                          '\t\t. there exist one frequency f+, lying between f0 and 4*f0, such that A0 / A(f+) > 2\n'
                          '\t\t. A0 > 2\n\n'
                          '\t- amplitude stability conditions:\n'
                          '\t\t. peak appear within +/-5% on HVSR curves of mean +/- one standard deviation (f0+/f0-)\n'
                          '\t\t. {}f lower than a frequency dependent threshold {}(f)\n'
                          '\t\t. {}A lower than a frequency dependent threshold log {}(f)\n'.
                          format(check_mark(), get_char('sigma'), get_char('epsilon'), get_char('sigma'), 
                                 get_char('teta')))

        # Also output the report to the terminal.
        print('\n\nPeaks:\n'
              'Parameters and ranking (A0: peak amplitude, f0: peak frequency, {}: satisfied)):\n\n'
              '\t- amplitude clarity conditions:\n'
              '\t\t. there exist one frequency f-, lying between f0/4 and f0, such that A0 / A(f-) > 2\n'
              '\t\t. there exist one frequency f+, lying between f0 and 4*f0, such that A0 / A(f+) > 2\n'
              '\t\t. A0 > 2\n\n'
              '\t- amplitude stability conditions:\n'
              '\t\t. peak appear within +/-5% on HVSR curves of mean +/- one standard deviation (f0+/f0-)\n'
              '\t\t. {}f lower than a frequency dependent threshold {}(f)\n'
              '\t\t. {}A lower than a frequency dependent threshold log {}(f)\n'.
              format(check_mark(), get_char('sigma'), get_char('epsilon'), get_char('sigma'), get_char('teta')), 
              flush=True)

    for _i, _peak_value in enumerate(_peak):
        _index.append(_i)
        _rank.append(_peak_value['Score'])
    _list = list(zip(_rank, _index))
    _list.sort(reverse=True)

    if report_information:
        report_file.write('\n%47s %10s %22s %12s %12s %32s %32s %27s %22s %17s'
                          % ('Net.Sta.Loc.Chan', '    f0    ', '        A0 > 2        ', '     f-      ', '    f+     ',
                             '     f0- within ±5% of f0 &     ', '     f0+ within ±5% of f0       ',
                             get_char('sigma') +
                             'f < ' + get_char('epsilon') + ' * f0      ', get_char('sigma') + 'log HVSR < log' +
                             get_char('teta') + '    ', '   Score/Max.    \n'))
        report_file.write('%47s %10s %22s %12s %12s %32s %32s %27s %22s %17s\n'
                          % (47 * separator_character, 10 * separator_character, 22 * separator_character,
                             12 * separator_character, 12 * separator_character, 32 * separator_character,
                             32 * separator_character, 27 * separator_character, 22 * separator_character,
                             7 * separator_character))

        print('\n%47s %10s %22s %12s %12s %32s %32s %27s %22s %17s'
                          % ('Net.Sta.Loc.Chan', '    f0    ', '        A0 > 2        ', '     f-      ', '    f+     ',
                             '     f0- within ±5% of f0 &     ', '     f0+ within ±5% of f0       ',
                             get_char('sigma') +
                             'f < ' + get_char('epsilon') + ' * f0      ', get_char('sigma') + 'log HVSR < log' +
                             get_char('teta') + '    ', '   Score/Max.    \n'), flush=True)

        print('%47s %10s %22s %12s %12s %32s %32s %27s %22s %17s\n'
              % (47 * separator_character, 10 * separator_character, 22 * separator_character,
                 12 * separator_character, 12 * separator_character, 32 * separator_character,
                 32 * separator_character, 27 * separator_character, 22 * separator_character,
                 7 * separator_character), flush=True)

    _peak_visible = list()
    for _i, _list_value in enumerate(_list):
        _index = _list_value[1]
        _peak_found = _peak[_index]
        if float(_peak_found['Score']) < _min_rank:
            continue
        else:
            _peak_visible.append(True)

        report_file.write('%47s %10.3f %22s %12s %12s %32s %32s %27s %22s %12d/%0d\n' %
              (_station_header, _peak_found['f0'], _peak_found['Report']['A0'], _peak_found['f-'], _peak_found['f+'],
               _peak_found['Report']['P-'], _peak_found['Report']['P+'], _peak_found['Report']['Sf'],
               _peak_found['Report']['Sa'], _peak_found['Score'], max_rank))

        print('%47s %10.3f %22s %12s %12s %32s %32s %27s %22s %12d/%0d\n' %
              (_station_header, _peak_found['f0'], _peak_found['Report']['A0'], _peak_found['f-'], _peak_found['f+'],
               _peak_found['Report']['P-'], _peak_found['Report']['P+'], _peak_found['Report']['Sf'],
               _peak_found['Report']['Sa'], _peak_found['Score'], max_rank), flush=True)

    if len(_list) <= 0 or len(_peak_visible) <= 0:
        report_file.write('%47s\n' % _station_header)
        report_file.close()

        print('%47s\n' % _station_header, flush=True)


def get_args(_arg_list):
    """get the run arguments"""
    _args = {}
    for _i in range(1, len(_arg_list)):
        try:
            _key, _value = _arg_list[_i].split('=')
            _args[_key] = _value
        except Exception as _e:
            msgLib.error('Bad parameter: {}, will use the default\n{}'.format(_arg_list[_i], _e), 1)
            continue
    return _args


def get_param(_args, _key, _msg_lib, _value, be_verbose=-1):
    """get a run argument for the given _key"""
    if _key in _args.keys():
        if be_verbose >= 0:
            print (_key, _args[_key])
        return _args[_key]
    elif _value is not None:
        return _value
    else:
        _msg_lib.error('missing parameter {}'.format(_key), 1)
        usage()
        sys.exit()


def check_y_range(_y, _low, _high):
    """check the PSD values to see if they are within the range"""
    _ok = list()
    _not_ok = list()

    # use subtract operator to see if y and _low/_high are crossing
    for _i, _value in enumerate(_y):
        _l = [_a - _b for _a, _b in zip(_value, _low)]
        if min(_l) < 0:
            _not_ok.append(_i)
            continue

        _h = [_a - _b for _a, _b in zip(_value, _high)]
        if max(_h) > 0:
            _not_ok.append(_i)
            continue

        _ok.append(_i)

    return _ok, _not_ok


def remove_db(_db_value):
    """convert dB power to power"""
    _values = list()
    for _d in _db_value:
        _values.append(10 ** (float(_d) / 10.0))
    return _values


def get_power(_db, _x):
    """calculate HVSR
      We will undo setp 6 of MUSTANG processing as outlined below:
          1. Dividing the window into 13 segments having 75% overlap
          2. For each segment:
             2.1 Removing the trend and mean
             2.2 Apply a 10% sine taper
             2.3 FFT
          3. Calculate the normalized PSD
          4. Average the 13 PSDs & scale to compensate for tapering
          5. Frequency-smooth the averaged PSD over 1-octave intervals at 1/8-octave increments
          6. Convert power to decibels

    NOTE: PSD is equal to the power divided by the width of the bin
          PSD = P / W
          log(PSD) = Log(P) - log(W)
          log(P) = log(PSD) + log(W)  here W is width in frequency
          log(P) = log(PSD) - log(Wt) here Wt is width in period

    for each bin perform rectangular integration to compute power
    power is assigned to the point at the begining of the interval
         _   _
        | |_| |
        |_|_|_|

     Here we are computing power for individual ponts, so, no integration is necessary, just
     compute area
    """
    _dx = np.diff(_x)[0]
    _p = np.multiply(np.mean(remove_db(_db)), _dx)
    return _p


def get_hvsr(_dbz, _db1, _db2, _x, use_method=4):
    """
    H is computed based on the selected use_method see: https://academic.oup.com/gji/article/194/2/936/597415
        use_method:
           (1) DFA
           (2) arithmetic mean, that is, H ≡ (HN + HE)/2
           (3) geometric mean, that is, H ≡ √HN · HE, recommended by the SESAME project (2004)
           (4) vector summation, that is, H ≡ √H2 N + H2 E
           (5) quadratic mean, that is, H ≡ √(H2 N + H2 E )/2
           (6) maximum horizontal value, that is, H ≡ max {HN, HE}
    """
    _pz = get_power(_dbz, _x)
    _p1 = get_power(_db1, _x)
    _p2 = get_power(_db2, _x)

    _hz = math.sqrt(_pz)
    _h1 = math.sqrt(_p1)
    _h2 = math.sqrt(_p2)

    _h = {2: (_h1 + _h2) / 2.0, 3: math.sqrt(_h1 * _h2), 4: math.sqrt(_p1 + _p2), 5: math.sqrt((_p1 + _p2) / 2.0),
          6: max(_h1, _h2)}

    _hvsr = _h[use_method] / _hz
    return _hvsr


def find_peaks(_y):
    """find peaks"""
    _index_list = argrelextrema(np.array(_y), np.greater)

    return _index_list[0]


def init_peaks(_x, _y, _index_list, _hvsr_band, _peak_water_level):
    """initialize peaks"""
    _peak = list()
    for _i in indexList:
        if _y[_i] > _peak_water_level[_i] and (_hvsr_band[0] <= _x[_i] <= _hvsr_band[1]):
            _peak.append({'f0': float(_x[_i]), 'A0': float(_y[_i]), 'f-': None, 'f+': None, 'Sf': None, 'Sa': None,
                          'Score': 0, 'Report': {'A0': '', 'Sf': '', 'Sa': '', 'P+': '', 'P-': ''}})
    return _peak


def check_clarity(_x, _y, _peak, do_rank=False):
    """
       test peaks for satisfying amplitude clarity conditions as outlined by SESAME 2004:
           - there exist one frequency f-, lying between f0/4 and f0, such that A0 / A(f-) > 2
           - there exist one frequency f+, lying between f0 and 4*f0, such that A0 / A(f+) > 2
           - A0 > 2
    """
    global max_rank

    # Peaks with A0 > 2.
    if do_rank:
        max_rank += 1
    _a0 = 2.0
    for _i in range(len(_peak)):

        if float(_peak[_i]['A0']) > _a0:
            _peak[_i]['Report']['A0'] = '%10.2f > %0.1f %1s' % (_peak[_i]['A0'], _a0, check_mark())
            _peak[_i]['Score'] += 1
        else:
            _peak[_i]['Report']['A0'] = '%10.2f > %0.1f  ' % (_peak[_i]['A0'], _a0)

    # Test each _peak for clarity.
    if do_rank:
        max_rank += 1
    for _i in range(len(_peak)):
        _peak[_i]['f-'] = '-'
        for _j in range(len(_x) - 1, -1, -1):

            # There exist one frequency f-, lying between f0/4 and f0, such that A0 / A(f-) > 2.
            if (float(_peak[_i]['f0']) / 4.0 <= _x[_j] < float(_peak[_i]['f0'])) and \
                    float(_peak[_i]['A0']) / _y[_j] > 2.0:
                _peak[_i]['f-'] = '%10.3f %1s' % (_x[_j], check_mark())
                _peak[_i]['Score'] += 1
                break

    if do_rank:
        max_rank += 1
    for _i in range(len(_peak)):
        _peak[_i]['f+'] = '-'
        for _j in range(len(_x) - 1):

            # There exist one frequency f+, lying between f0 and 4*f0, such that A0 / A(f+) > 2.
            if float(_peak[_i]['f0']) * 4.0 >= _x[_j] > float(_peak[_i]['f0']) and \
                    float(_peak[_i]['A0']) / _y[_j] > 2.0:
                _peak[_i]['f+'] = '%10.3f %1s' % (_x[_j], check_mark())
                _peak[_i]['Score'] += 1
                break

    return _peak


def check_freq_stability(_peak, _peakm, _peakp):
    """
       test peaks for satisfying stability conditions as outlined by SESAME 2004:
           - the _peak should appear at the same frequency (within a percentage ± 5%) on the H/V
             curves corresponding to mean + and – one standard deviation.
    """
    global max_rank

    #
    # check σf and σA
    #
    max_rank += 1

    _found_m = list()
    for _i in range(len(_peak)):
        _dx = 1000000.
        _found_m.append(False)
        _peak[_i]['Report']['P-'] = '- &'
        for _j in range(len(_peakm)):
            if abs(_peakm[_j]['f0'] - _peak[_i]['f0']) < _dx:
                _index = _j
                _dx = abs(_peakm[_j]['f0'] - _peak[_i]['f0'])
            if peak[_i]['f0'] * 0.95 <= _peakm[_j]['f0'] <= _peak[_i]['f0'] * 1.05:
                _peak[_i]['Report']['P-'] = '%0.3f within ±5%s of %0.3f %1s' % (_peakm[_j]['f0'], '%',
                                                                                 _peak[_i]['f0'], '&')
                _found_m[_i] = True
                break
        if _peak[_i]['Report']['P-'] == '-':
            _peak[_i]['Report']['P-'] = '%0.3f within ±5%s of %0.3f %1s' % (_peakm[_i]['f0'], '%',
                                                                             _peak[_i]['f0'], '&')

    _found_p = list()
    for _i in range(len(_peak)):
        _dx = 1000000.
        _found_p.append(False)
        _peak[_i]['Report']['P+'] = '-'
        for _j in range(len(_peakp)):
            if abs(_peakp[_j]['f0'] - _peak[_i]['f0']) < _dx:
                _index = _j
                _dx = abs(_peakp[_j]['f0'] - _peak[_i]['f0'])
            if _peak[_i]['f0'] * 0.95 <= _peakp[_j]['f0'] <= _peak[_i]['f0'] * 1.05:
                if _found_m[_i]:
                    _peak[_i]['Report']['P+'] = '%0.3f within ±5%s of %0.3f %1s' % (
                        _peakp[_j]['f0'], '%', _peak[_i]['f0'], check_mark())
                    _peak[_i]['Score'] += 1
                else:
                    _peak[_i]['Report']['P+'] = '%0.3f within ±5%s of %0.3f %1s' % (
                        _peakp[_i]['f0'], '%', _peak[_i]['f0'], ' ')
                break
        if _peak[_i]['Report']['P+'] == '-' and len(_peakp) > 0:
            _peak[_i]['Report']['P+'] = '%0.3f within ±5%s of %0.3f %1s' % (
                _peakp[_i]['f0'], '%', _peak[_i]['f0'], ' ')

    return _peak


def check_stability(_stdf, _peak, _hvsr_log_std, rank):
    """
    test peaks for satisfying stability conditions as outlined by SESAME 2004:
       - σf lower than a frequency dependent threshold ε(f)
       - σA (f0) lower than a frequency dependent threshold θ(f),
    """

    global max_rank

    #
    # check σf and σA
    #
    if rank:
        max_rank += 2
    for _i in range(len(_peak)):
        _peak[_i]['Sf'] = _stdf[_i]
        _peak[_i]['Sa'] = _hvsr_log_std[_i]
        _this_peak = _peak[_i]
        if _this_peak['f0'] < 0.2:
            _e = 0.25
            if _stdf[_i] < _e * _this_peak['f0']:
                _peak[_i]['Report']['Sf'] = '%10.4f < %0.2f * %0.3f %1s' % (_stdf[_i], _e, _this_peak['f0'],
                                                                            check_mark())
                _this_peak['Score'] += 1
            else:
                _peak[_i]['Report']['Sf'] = '%10.4f < %0.2f * %0.3f  ' % (_stdf[_i], _e, _this_peak['f0'])

            _t = 0.48
            if _hvsr_log_std[_i] < _t:
                _peak[_i]['Report']['Sa'] = '%10.4f < %0.2f %1s' % (_hvsr_log_std[_i], _t,
                                                                    check_mark())
                _this_peak['Score'] += 1
            else:
                _peak[_i]['Report']['Sa'] = '%10.4f < %0.2f  ' % (_hvsr_log_std[_i], _t)

        elif 0.2 <= _this_peak['f0'] < 0.5:
            _e = 0.2
            if _stdf[_i] < _e * _this_peak['f0']:
                _peak[_i]['Report']['Sf'] = '%10.4f < %0.2f * %0.3f %1s' % (_stdf[_i], _e, _this_peak['f0'],
                                                                            check_mark())
                _this_peak['Score'] += 1
            else:
                _peak[_i]['Report']['Sf'] = '%10.4f < %0.2f * %0.3f  ' % (_stdf[_i], _e, _this_peak['f0'])

            _t = 0.40
            if _hvsr_log_std[_i] < _t:
                _peak[_i]['Report']['Sa'] = '%10.4f < %0.2f %1s' % (_hvsr_log_std[_i], _t,
                                                                    check_mark())
                _this_peak['Score'] += 1
            else:
                _peak[_i]['Report']['Sa'] = '%10.4f < %0.2f  ' % (_hvsr_log_std[_i], _t)

        elif 0.5 <= _this_peak['f0'] < 1.0:
            _e = 0.15
            if _stdf[_i] < _e * _this_peak['f0']:
                _peak[_i]['Report']['Sf'] = '%10.4f < %0.2f * %0.3f %1s' % (_stdf[_i], _e, _this_peak['f0'],
                                                                            check_mark())
                _this_peak['Score'] += 1
            else:
                _peak[_i]['Report']['Sf'] = '%10.4f < %0.2f * %0.3f  ' % (_stdf[_i], _e, _this_peak['f0'])

            _t = 0.3
            if _hvsr_log_std[_i] < _t:
                _peak[_i]['Report']['Sa'] = '%10.4f < %0.2f %1s' % (_hvsr_log_std[_i], _t, check_mark())
                _this_peak['Score'] += 1
            else:
                _peak[_i]['Report']['Sa'] = '%10.4f < %0.2f  ' % (_hvsr_log_std[_i], _t)

        elif 1.0 <= _this_peak['f0'] <= 2.0:
            _e = 0.1
            if _stdf[_i] < _e * _this_peak['f0']:
                _peak[_i]['Report']['Sf'] = '%10.4f < %0.2f * %0.3f %1s' % (_stdf[_i], _e, _this_peak['f0'],
                                                                            check_mark())
                _this_peak['Score'] += 1
            else:
                _peak[_i]['Report']['Sf'] = '%10.4f < %0.2f * %0.3f  ' % (_stdf[_i], _e, _this_peak['f0'])

            _t = 0.25
            if _hvsr_log_std[_i] < _t:
                _peak[_i]['Report']['Sa'] = '%10.4f < %0.2f %1s' % (_hvsr_log_std[_i], _t, check_mark())
                _this_peak['Score'] += 1
            else:
                _peak[_i]['Report']['Sa'] = '%10.4f < %0.2f  ' % (_hvsr_log_std[_i], _t)

        elif _this_peak['f0'] > 0.2:
            _e = 0.05
            if _stdf[_i] < _e * _this_peak['f0']:
                _peak[_i]['Report']['Sf'] = '%10.4f < %0.2f * %0.3f %1s' % (_stdf[_i], _e, _this_peak['f0'],
                                                                            check_mark())
                _this_peak['Score'] += 1
            else:
                _peak[_i]['Report']['Sf'] = '%10.4f < %0.2f * %0.3f  ' % (_stdf[_i], _e, _this_peak['f0'])

            _t = 0.2
            if _hvsr_log_std[_i] < _t:
                _peak[_i]['Report']['Sa'] = '%10.4f < %0.2f %1s' % (_hvsr_log_std[_i], _t, check_mark())
                _this_peak['Score'] += 1
            else:
                _peak[_i]['Report']['Sa'] = '%10.4f < %0.2f  ' % (_hvsr_log_std[_i], _t)
    return _peak


def get_pdf(_url, _verbose):
    """get PDF"""
    _x_values = list()
    _y_values = list()
    _x = list()
    _y = list()
    _p = list()

    if _verbose >= 0:
        msgLib.info('requesting:' + _url)
    try:
        _link = urllib.request.urlopen(_url)
    except Exception as _e:
        msgLib.error('\n\nReceived HTTP Error code: {}\n{}'.format(_e.code, _e.reason), 1)
        if _e.code == 404:
            _url_items = _url.split('&')
            _starttime = [x for x in _url_items if x.startswith('starttime')]
            _endtime = [x for x in _url_items if x.startswith('endtime')]
            msgLib.error('Error 404: PDF not found in the range {} and {} when requested:\n{}'.format(
                _starttime.split('=')[1], _endtime.split('=')[1], _url), 1)
        elif _e.code == 413:
            print('Note: Either use the run argument "n" to split the requested date range to smaller intervals'
                  '\nCurrent "n"" value is: {}. Or request a shorter time interval.'.format(n), flush=True)
            sys.exit(1)
        msgLib.error('failed on target {} {}'.format(target, URL), 1)
        return _x, _y, _p

    if _verbose >= 0:
        msgLib.info('PDF waiting for reply....')

    _data = _link.read().decode()
    _link.close()
    _lines = _data.split('\n')
    _last_frequency = ''
    _line_count = 0
    _non_blank_last_line = 0
    _hits_list = list()
    _power_list = list()
    if len(_lines[-1].strip()) <= 0:
        _non_blank_last_line = 1
    for _line in _lines:
        _line_count += 1
        if len(_line.strip()) <= 0:
            continue
        if _line[0] == '#' or ',' not in _line:
            continue
        (_freq, _power, _hits) = _line.split(',')
        if _last_frequency == '':
            _last_frequency = _freq.strip()
            _power_list = list()
            _power_list.append(float(_power))
            _hits_list = list()
            _hits_list.append(int(_hits))
        elif _last_frequency == _freq.strip():
            _power_list.append(float(_power))
            _hits_list.append(int(_hits))
        if _last_frequency != _freq.strip() or _line_count == len(_lines) - _non_blank_last_line:
            _total_hits = sum(_hits_list)
            _y_values.append(np.array(_hits_list) * 100.0 / _total_hits)
            if xtype == 'period':
                last_x = 1.0 / float(_last_frequency)
                _x_values.append(last_x)
            else:
                last_x = float(_last_frequency)
                _x_values.append(last_x)
            for _i in range(len(_hits_list)):
                _y.append(float(_power_list[_i]))
                _p.append(float(_hits_list[_i]) * 100.0 / float(_total_hits))
                _x.append(last_x)

            _last_frequency = _freq.strip()
            _power_list = list()
            _power_list.append(float(_power))
            _hits_list = list()
            _hits_list.append(int(_hits))
    return _x, _y, _p


# Set run parameters.
args = get_args(sys.argv)
if len(args) <= 1:
    usage()
    sys.exit()

verbose = int(get_param(args, 'verbose', msgLib, -1, be_verbose=param.verbose))
if verbose >= 0:
    print('\n[INFO]', sys.argv[0], version)

report_information = int(get_param(args, 'report_information', msgLib, 1, be_verbose=verbose))

# Get channels and sort them in the reverse ] order to make sure that we always have ?HZ first.
# Order of the horizontals is not important.
channels = get_param(args, 'chan', msgLib, param.chan)
channelList = sorted(channels.split(','), reverse=True)
if len(channelList) < 3:
    msgLib.error('need 3 channels!', 1)
    sys.exit()

sorted_channel_list = channelList.copy()
for channel in channelList:
    sorted_channel_list[channel_order[channel[2]]] = channel

# See if we want to reject suspect PSDs.
remove_outliers = bool(int(get_param(args, 'removeoutliers', msgLib, False)))
msgLib.info('remove_outliers: {}'.format(remove_outliers))

# Minimum SESAME 2004 rank to be accepted.
min_rank = float(get_param(args, 'minrank', msgLib, param.minrank))

# network, station, and location to process.
network = get_param(args, 'net', msgLib, None)
if network is None:
    msgLib.error('network not defined!', 1)
    sys.exit()
station = get_param(args, 'sta', msgLib, None)
if station is None:
    msgLib.error('station not defined!', 1)
    sys.exit()
location = get_param(args, 'loc', msgLib, '*')
if location is None:
    msgLib.error('location not defined!', 1)
    sys.exit()

# Start of the window.
start = get_param(args, 'start', msgLib, None)
start_hour = 'T00:00:00'
start_time = time.strptime(start, '%Y-%m-%d')
end = get_param(args, 'end', msgLib, None)

# If start and end are the same day, process that day.
if start.strip() == end.strip():
    end_hour = 'T23:59:59'
else:
    end_hour = 'T00:00:00'
end_time = time.strptime(end, '%Y-%m-%d')

# Break the start-end interval to n segments.
n = int(get_param(args, 'n', msgLib, 1))
date_list = date_range(start, end, n)
msgLib.info('DATE LIST: {}'.format(date_list))

# How to combine h1 & h2.
method = int(get_param(args, 'method', msgLib, param.method))
if method <= 0 or method > 6:
    msgLib.error('method {} for combining H1 & H2 is invalid!'.format(method), 1)
    sys.exit()
elif method == 1:
    dfa = 1
else:
    dfa = 0

msgLib.info('Combining H1 and H2 Using {} method'.format(param.methodList[method]))

do_plot = int(get_param(args, 'plot', msgLib, param.plot))
show_plot = int(get_param(args, 'showplot', msgLib, param.plot))
plot_psd = int(get_param(args, 'plotpsd', msgLib, param.plotpsd))
plot_pdf = int(get_param(args, 'plotpdf', msgLib, param.plotpdf))
plot_bad = int(get_param(args, 'plotbad', msgLib, param.plotbad))
plot_nnm = int(get_param(args, 'plotnnm', msgLib, param.plotnnm))

day_values_passed = [[], [], []]
water_level = float(get_param(args, 'waterlevel', msgLib, param.waterlevel))
hvsr_ylim = param.hvsrylim
hvsr_ylim[1] = float(get_param(args, 'ymax', msgLib, param.hvsrylim[1]))
xtype = get_param(args, 'xtype', msgLib, param.xtype)
hvsr_band = get_param(args, 'hvsrband', msgLib, param.hvsrband)

report_header = '.'.join([network, station, location, '-'.join(sorted_channel_list)])
station_header = report_header
station_header = '{} {} {}'.format(station_header, start, end)
report_header += ' {} from {} to {}\nusing {}'.format(report_header, start, end, param.methodList[method])
plot_title = report_header
report_header = '{}\n\n'.format(report_header)

# Turn off the display requirement if not needed.
if not show_plot:
    if verbose >= 0:
        msgLib.info('Plot Off')
    matplotlib.use('agg')
else:
    from obspy.imaging.cm import pqlx
    from obspy.signal.spectral_estimation import get_nlnm, get_nhnm

ax2 = None
# Do one channel at a time.
channel_index = -1
for channel in sorted_channel_list:
    channel_index += 1
    x_values = list()
    psd_values = list()
    day_values = list()
    day_time_values = list()
    pct_low = list()
    pct_high = list()
    pct_mid = list()

    target = '.'.join([network, station, location, channel, '*'])
    label = '.'.join([network, station, location, 'PSDs'])
    label_hvsr = '.'.join([network, station, location, 'HVSR'])
    if verbose >= 0:
        msgLib.info('requesting {} from {} to {}'.format(target, start, end))

    # Baseline files are required if we will remove the outliers. We assume the baseline file has all the periods,
    # so we use it as a reference.
    if remove_outliers:
        try:
            baselineFile = open(
                os.path.join(param.baselineDirectory, fileLib.baselineFileName(network, station, location, channel)),
                'r')
        except Exception as e:
            msgLib.error('Failed to read baseline file {}\n'
                         'Use the getStationChannelBaseline.py script to generate the baseline file or '
                         'set the parameter removeoutliers=0.'.
                         format(os.path.join(param.baselineDirectory, fileLib.baselineFileName(network,
                                                                                               station,
                                                                                               location,
                                                                                               channel))), 1)
            sys.exit()

        lines = baselineFile.read()
        baseline = lines.split('\n')
        for index_value in range(0, len(baseline)):
            if len(baseline[index_value].strip()) == 0:
                continue
            if baseline[index_value].strip().startswith('#'):
                values = baseline[index_value].strip().split()
                percent_low = values[1]
                percent_mid = values[3]
                percent_high = values[5]
                continue

            values = baseline[index_value].split()

            x_values.append(float(values[0]))
            pct_low.append(float(values[1]))
            pct_mid.append(float(values[2]))
            pct_high.append(float(values[3]))
        baselineFile.close()

    # Get daily PSDs from MUSTANG.
    # Limit PSD segments starting between starttime (inclusive) and endtime (exclusive)
    pdf_x = list()
    pdf_y = list()
    pdfP = list()
    for date_index in range(len(date_list) - 1):
        msgLib.info('Doing {}{} to {}{}'.format(date_list[date_index], start_hour, date_list[date_index + 1], end_hour))
        URL = '{}target={}&starttime={}{}&endtime={}{}&format=xml&correct=true'.format(param.mustangPsdUrl, target,
                                                                                       date_list[date_index],
                                                                                       start_hour,
                                                                                       date_list[date_index + 1],
                                                                                       end_hour)
        if verbose >= 0:
            msgLib.info('requesting: {}'.format(URL))
            t0 = time_it(t0)
        try:
            link = urllib.request.urlopen(URL)
        except Exception as _e:
            msgLib.error('\n\nReceived HTTP Error code: {}\n{}'.format(_e.code, _e.reason), 1)
            if _e.code == 404:
                msgLib.error('Error 404: No PSDs found in the range {}{} to {}{} when requested:\n\n{}'.format(
                    date_list[date_index], start_hour, date_list[date_index + 1], end_hour, URL), 1)
                continue
            elif _e.code == 413:
                print('Note: Either use the run argument "n" to split the requested date range to smaller intervals'
                      '\nCurrent "n"" value is: {}. Or request a shorter time interval.'.format(n), flush=True)
                sys.exit(1)
            msgLib.error('failed on target {} {}'.format(target, URL), 1)

        if verbose:
            msgLib.info('PSD waiting for reply....')

        tree = ET.parse(link)
        link.close()
        root = tree.getroot()

        if verbose:
            requestStart = root.find('RequestedDateRange').find('Start').text
            requestEnd = root.find('RequestedDateRange').find('End').text

        psds = root.find('Psds')

        all_psds = psds.findall('Psd')
        if verbose:
            msgLib.info('PSD: {}'.format(str(len(all_psds))))
            t0 = time_it(t0)

        for psd in all_psds:
            day = psd.attrib['start'].split('T')[0]
            psdTime = time.strptime(day, '%Y-%m-%d')
            if (start_time != end_time and (psdTime < start_time or psdTime >= end_time)) or \
                    (start_time == end_time and psdTime != start_time):
                if verbose >= 0:
                    msgLib.warning(sys.argv[0], 'Rejected, PSD of {} is outside the  window {} to {}'.
                                   format(psd.attrib['start'],
                                          time.strftime('%Y-%m-%dT%H:%M:%S', start_time),
                                          time.strftime('%Y-%m-%dT%H:%M:%S', end_time)))
                continue
            allValues = psd.findall('value')

            X = list()
            Y = list()
            for value in allValues:
                X.append(float(value.attrib['freq']))
                Y.append(float(value.attrib['power']))

            # We follow a simple logic, the X values must match. We take the first one to be the sequence we want.
            if not x_values:
                x_values = list(X)

            if X != x_values:
                if verbose:
                    msgLib.warning(sys.argv[0], 'Rejected {} {} {} for bad X'.format(target, date_list[date_index],
                                                                                     date_list[date_index + 1]))
            else:
                # Store the PSD values and at the same time keep track of their day and time.
                day_values.append(day)
                day_time_values.append(psd.attrib['start'])
                psd_values.append(Y)

        if plot_pdf:
            (thisX, thisY, thisP) = get_pdf('{}target={}&starttime={}{}&endtime={}{}&format=text'.format(
                param.mustangPdfUrl, target, date_list[date_index], start_hour, date_list[date_index + 1],
                end_hour), verbose)
            pdf_x += thisX
            pdf_y += thisY
            pdfP += thisP
            if verbose:
                msgLib.info('PDF: {}'.format(len(pdf_y)))

    # Must have PSDs.
    if not psd_values:
        msgLib.error('no PSDs found to process between {} and {}'.format(
            date_list[date_index], date_list[date_index + 1]), 1)
        sys.exit()
    else:
        if verbose >= 0:
            msgLib.info('total PSDs:' + str(len(psd_values)))
            t0 = time_it(t0)

    # PSDs:
    # Initial settings.
    if channel_index == 0:
        if do_plot:
            if verbose >= 0:
                msgLib.info('PLOT PSD')

            fig = plt.figure(figsize=param.imageSize, facecolor='white')
            ax = list()
            fig.canvas.set_window_title(label)
            ax.append(plt.subplot(plotRows, 1, channel_index + 1))

        # [chanZ[day],chan1[day],chan2[day]]
        daily_psd = [{}, {}, {}]
        day_time_psd = [{}, {}, {}]
        median_daily_psd = [{}, {}, {}]
        equal_daily_energy = [{}, {}, {}]
    else:
        if do_plot:
            ax.append(plt.subplot(plotRows, 1, channel_index + 1, sharex=ax[0]))

    # Go through all PSDs and reject the 'bad' ones based on the station baseline
    # only done when remove_outliers is True.
    if remove_outliers:
        if verbose:
            msgLib.info('CLEAN UP ' + str(len(psd_values)) + ' PSDs')
        (ok, notok) = check_y_range(psd_values, pct_low, pct_high)
    else:
        # No cleanup needed, mark them all as OK!
        notok = list()
        ok = range(len(psd_values))

    info = ' '.join(
        ['Channel', channel, str(len(psd_values)), 'PSDs,', str(len(ok)), 'accepted and', str(len(notok)), 'rejected',
         '\n'])
    report_header += info
    print ('[INFO]', info)

    if verbose and notok:
        t0 = time_it(t0)
        msgLib.info('Flag BAD PSDs')
    for i, index in enumerate(ok):
        # DAY,DAYTIME: 2018-01-01 2018-01-01T00:00:00.000Z
        day = day_values[index]
        day_time = day_time_values[index]
        psd = psd_values[index]

        # Preserve the individual PSDs (day_time)
        day_time_psd[channel_index][day_time] = psd

        # Group PSDs into daily bins
        if day not in daily_psd[channel_index].keys():
            daily_psd[channel_index][day] = list()
        daily_psd[channel_index][day].append(psd)

        # Keep track of individual days
        if day_values[index] not in day_values_passed[channel_index]:
            day_values_passed[channel_index].append(day)
    if verbose and notok:
        t0 = time_it(t0)

    if do_plot:
        # Plot the 'bad' PSDs in gray.
        if plot_psd and plot_bad:
            msgLib.info('[INFO] Plot {} BAD PSDs'.format(len(notok)))
            for i, index in enumerate(notok):
                if i == 0:
                    plt.semilogx(np.array(x_values), psd_values[index], c='gray', label='Rejected')
                else:
                    plt.semilogx(np.array(x_values), psd_values[index], c='gray')
            if verbose >= 0:
                t0 = time_it(t0)

        if plot_psd:
            # Plot the 'good' PSDs in green.
            if verbose:
                msgLib.info('[INFO] Plot {} GOOD PSDs'.format(len(ok)))
            for i, index in enumerate(ok):
                if i == 0:
                    plt.semilogx(np.array(x_values), psd_values[index], c='green', label='PSD')
                else:
                    plt.semilogx(np.array(x_values), psd_values[index], c='green')
            if verbose >= 0:
                t0 = time_it(t0)
        if plot_pdf:
            cmap = pqlx

            ok = list()
            im = plt.scatter(pdf_x, pdf_y, c=pdfP, s=46.5, marker='_', linewidth=param.lw, edgecolor='face', cmap=cmap,
                             alpha=param.alpha)
            ax[channel_index].set_xscale('log')

        if verbose:
            msgLib.info('Tune plots.')
        if verbose >= 0:
            t0 = time_it(t0)
        if remove_outliers:
            plt.semilogx(np.array(x_values), pct_high, c='yellow', label='{}%'.format(percent_high))
            plt.semilogx(np.array(x_values), pct_mid, c='red', label='{}%'.format(percent_mid))
            plt.semilogx(np.array(x_values), pct_low, c='orange', label='{}%'.format(percent_low))
        plt.semilogx((param.hvsrXlim[0], param.hvsrXlim[0]), param.yLim, c='black')
        plt.semilogx((param.hvsrXlim[1], param.hvsrXlim[1]), param.yLim, c='black')
        p1 = plt.axvspan(param.xLim[xtype][0], param.hvsrXlim[0], facecolor='#909090', alpha=0.5)
        p2 = plt.axvspan(param.hvsrXlim[1], param.xLim[xtype][1], facecolor='#909090', alpha=0.5)
        # plt.title(' '.join([target,start,'to',end]))
        plt.ylim(param.yLim)
        plt.xlim(param.xLim[xtype])
        plt.ylabel(param.yLabel)

        if len(ok) <= 0:
            anchored_text = AnchoredText(
                ' '.join(['.'.join([network, station, location, channel]), '{:,d}'.format(len(psd_values)), 'PSDs']),
                loc=2)
        else:
            anchored_text = AnchoredText(' '.join(
                ['.'.join([network, station, location, channel]), '{:,d}'.format(len(ok)), 'out of',
                 '{:,d}'.format(len(psd_values)), 'PSDs']), loc=2)
        ax[channel_index].add_artist(anchored_text)

        if plot_nnm:
            nlnm_x, nlnm_y = get_nlnm()
            nhnm_x, nhnm_y = get_nhnm()
            if xtype != 'period':
                nlnm_x = 1.0 / nlnm_x
                nhnm_x = 1.0 / nhnm_x
            plt.plot(nlnm_x, nlnm_y, lw=2, ls='--', c='k', label='NLNM, NHNM')
            plt.plot(nhnm_x, nhnm_y, lw=2, ls='--', c='k')

        plt.legend(prop={'size': 6}, loc='lower left')

        # Create a second axes for the colorbar.
        if plot_pdf and ax2 is None:
            ax2 = fig.add_axes([0.92, 0.4, 0.01, 0.4])
            cbar = fig.colorbar(im, ax2, orientation='vertical')
            cbar.set_label('Probability (%)', size=9, rotation=270, labelpad=6)
            plt.clim(param.pMin, param.pMax)


    # Compute and save the median daily PSD for HVSR computation
    # for non-DFA computation.
    # daily_psd[channel_index][day] is a list of individual PSDs for that channel and day. We compute median
    # along axis=0 to get median of individual frequencies.
    if not dfa:
        if verbose:
            msgLib.info('Save Median Daily')
        for day in (day_values_passed[channel_index]):
            if display:
                print('[INFO] calculating median_daily_psd', flush=True)
                display = False
            median_daily_psd[channel_index][day] = np.percentile(daily_psd[channel_index][day], 50, axis=0)

# Are we doing DFA?
# Use equal energy for daily PSDs to give small 'events' a chance to contribute
# the same as large ones, so that P1+P2+P3=1
if dfa:
    if display:
        print('[INFO] DFA', flush=True)
        display = False
    sum_ns_power = list()
    sum_ew_power = list()
    sum_z_power = list()
    daily_psd = [{}, {}, {}]
    day_values = list()

    # Make sure we have all 3 components for every time sample
    for day_time in day_time_values:
        if day_time not in (day_time_psd[0].keys()) or day_time not in (day_time_psd[1].keys()) or day_time not in (
        day_time_psd[2].keys()):
            continue
        day = day_time.split('T')[0]
        if day not in day_values:
            day_values.append(day)

        # Initialize the daily PSDs.
        if day not in daily_psd[0].keys():
            daily_psd[0][day] = list()
            daily_psd[1][day] = list()
            daily_psd[2][day] = list()

        daily_psd[0][day].append(day_time_psd[0][day_time])
        daily_psd[1][day].append(day_time_psd[1][day_time])
        daily_psd[2][day].append(day_time_psd[2][day_time])

    # For each day equalize energy
    for day in day_values:

        # Each PSD for the day
        for i in range(len(daily_psd[0][day])):
            Pz = list()
            P1 = list()
            P2 = list()
            sum_pz = 0
            sum_p1 = 0
            sum_p2 = 0

            # Each sample of the PSD , convert to power
            for j in range(len(x_values) - 1):
                pz = get_power([daily_psd[0][day][i][j], daily_psd[0][day][i][j + 1]], [x_values[j], x_values[j + 1]])
                Pz.append(pz)
                sum_pz += pz
                p1 = get_power([daily_psd[1][day][i][j], daily_psd[1][day][i][j + 1]], [x_values[j], x_values[j + 1]])
                P1.append(p1)
                sum_p1 += p1
                p2 = get_power([daily_psd[2][day][i][j], daily_psd[2][day][i][j + 1]], [x_values[j], x_values[j + 1]])
                P2.append(p2)
                sum_p2 += p2

            sum_power = sum_pz + sum_p1 + sum_p2  # total power

            # Mormalized power
            for j in range(len(x_values) - 1):
                # Initialize if this is the first sample of the day
                if i == 0:
                    sum_z_power.append(Pz[j] / sum_power)
                    sum_ns_power.append(P1[j] / sum_power)
                    sum_ew_power.append(P2[j] / sum_power)
                else:
                    sum_z_power[j] += (Pz[j] / sum_power)
                    sum_ns_power[j] += (P1[j] / sum_power)
                    sum_ew_power[j] += (P2[j] / sum_power)
        # Average the normalized daily power
        for j in range(len(x_values) - 1):
            sum_z_power[j] /= len(daily_psd[0][day])
            sum_ns_power[j] /= len(daily_psd[0][day])
            sum_ew_power[j] /= len(daily_psd[0][day])

        equal_daily_energy[0][day] = sum_z_power
        equal_daily_energy[1][day] = sum_ns_power
        equal_daily_energy[2][day] = sum_ew_power

# HVSR computation
if verbose:
    msgLib.info('HVSR computation')
if verbose >= 0:
    t0 = time_it(t0)

# Find the unique days between all channels
d = day_values_passed[0]
for i in range(1, len(day_values_passed)):
    d += day_values_passed[i]
day_values_passed = set(d)  # unique days

hvsr = list()
peak_water_level = list()
hvsrp = list()
peak_water_level_p = list()
hvsrp2 = list()
hvsrm = list()
water_level_m = list()
peak_water_level_m = list()
hvsr_m2 = list()
hvsr_std = list()
hvsr_log_std = list()

path = ''.join(['M', str(method)])
fileLib.mkdir(param.hvsrDirectory, path)
out_file_name = os.path.join(param.hvsrDirectory, path, fileLib.hvsrFileName(network, station, location, start, end))

outFile = open(out_file_name, 'w')
msgLib.info(f'Output file: {out_file_name}')
count = -1

# compute one x-value (period or frequency) at a time to also compute standard deviation
outFile.write('frequency HVSR HVSR+1STD HVSR-1STD\n')
for j in range(len(x_values) - 1):
    missing = 0
    hvsr_tmp = list()

    for day in sorted(day_values_passed):

        # must have all 3 channels, compute HVSR for that day
        if dfa:
            if day in equal_daily_energy[0].keys() and day in equal_daily_energy[1].keys() and day in \
                    equal_daily_energy[2].keys():
                hvsr0 = math.sqrt(
                    (equal_daily_energy[1][day][j] + equal_daily_energy[2][day][j]) / equal_daily_energy[0][day][j])
                hvsr_tmp.append(hvsr0)
            else:
                if verbose > 0:
                    msgLib.warning(sys.argv[0], day + ' missing component, skipped!')
                missing += 1
                continue
        else:
            if day in median_daily_psd[0].keys() and day in median_daily_psd[1].keys() and day in \
                    median_daily_psd[2].keys():
                psd0 = [median_daily_psd[0][day][j], median_daily_psd[0][day][j + 1]]
                psd1 = [median_daily_psd[1][day][j], median_daily_psd[1][day][j + 1]]
                psd2 = [median_daily_psd[2][day][j], median_daily_psd[2][day][j + 1]]
                hvsr0 = get_hvsr(psd0, psd1, psd2, [x_values[j], x_values[j + 1]], use_method=method)
                hvsr_tmp.append(hvsr0)
            else:
                if verbose > 0:
                    msgLib.warning(sys.argv[0], day + ' missing component, skipped!')
                missing += 1
                continue
    count += 1
    peak_water_level.append(water_level)
    if len(hvsr_tmp) > 0:
        hvsr.append(np.mean(hvsr_tmp))
        hvsr_std.append(np.std(hvsr_tmp))
        hvsr_log_std.append(np.std(np.log10(hvsr_tmp)))
        hvsrp.append(hvsr[-1] + hvsr_std[-1])
        peak_water_level_p.append(water_level + hvsr_std[-1])
        hvsrp2.append(hvsr[-1] * math.exp(hvsr_log_std[count]))
        hvsrm.append(hvsr[-1] - hvsr_std[-1])
        peak_water_level_m.append(water_level - hvsr_std[-1])
        hvsr_m2.append(hvsr[-1] / math.exp(hvsr_log_std[-1]))
        # outFile.write(str(x_values[count])+'  '+str(hvsr[-1])+'  '+str(hvsrp[-1])+'  '+str(hvsrm[-1])+'\n')
        outFile.write(
            '%s %0.3f %0.3f %0.3f\n' % (str(x_values[count]), float(hvsr[-1]), float(hvsrp[-1]), float(str(hvsrm[-1]))))
outFile.close()

# Compute day at a time to also compute frequency standard deviation
missing = 0

# This holds the peaks for individual HVSRs that will contribute to the final HVSR. It will be used to find Sigmaf.
hvsrPeaks = list()

for day in sorted(day_values_passed):
    hvsr_tmp = list()
    for j in range(len(x_values) - 1):
        if dfa > 0:
            if day in equal_daily_energy[0].keys() and day in equal_daily_energy[1].keys() and day in \
                    equal_daily_energy[2].keys():
                hvsr0 = math.sqrt(
                    (equal_daily_energy[1][day][j] + equal_daily_energy[2][day][j]) / equal_daily_energy[0][day][j])
                hvsr_tmp.append(hvsr0)
            else:
                if verbose > 0:
                    msgLib.warning(sys.argv[0], day + ' missing component, skipped!')
                missing += 1
                continue
        else:
            if day in median_daily_psd[0].keys() and day in median_daily_psd[1].keys() and day in \
                    median_daily_psd[2].keys():
                psd0 = [median_daily_psd[0][day][j], median_daily_psd[0][day][j + 1]]
                psd1 = [median_daily_psd[1][day][j], median_daily_psd[1][day][j + 1]]
                psd2 = [median_daily_psd[2][day][j], median_daily_psd[2][day][j + 1]]
                hvsr0 = get_hvsr(psd0, psd1, psd2, [x_values[j], x_values[j + 1]], use_method=method)
                hvsr_tmp.append(hvsr0)
            else:
                if verbose > 0:
                    msgLib.warning(sys.argv[0], day + ' missing component, skipped!')
                missing += 1
                continue
    if not np.isnan(np.sum(hvsr_tmp)):
        hvsrPeaks.append(find_peaks(hvsr_tmp))

report_header += '\n'
report_header += ' '.join([str(missing), 'PSDs are missing one or more components\n'])

# Find  the relative extrema of hvsr
if not np.isnan(np.sum(hvsr)):
    indexList = find_peaks(hvsr)
else:
    indexList = list()

stdf = list()
for index in indexList:
    point = list()
    for j in range(len(hvsrPeaks)):
        p = None
        for k in range(len(hvsrPeaks[j])):
            if p is None:
                p = hvsrPeaks[j][k]
            else:
                if abs(index - hvsrPeaks[j][k]) < abs(index - p):
                    p = hvsrPeaks[j][k]
        if p is not None:
            point.append(p)
    point.append(index)
    v = list()
    for l in range(len(point)):
        v.append(x_values[point[l]])
    stdf.append(np.std(v))

peak = init_peaks(x_values, hvsr, indexList, hvsr_band, peak_water_level)
peak = check_clarity(x_values, hvsr, peak, True)

# Find  the relative extrema of hvsrp (hvsr + 1 standard deviation)
if not np.isnan(np.sum(hvsrp)):
    index_p = find_peaks(hvsrp)
else:
    index_p = list()

peakp = init_peaks(x_values, hvsrp, index_p, hvsr_band, peak_water_level_p)
peakp = check_clarity(x_values, hvsrp, peakp)

# Find  the relative extrema of hvsrp (hvsr - 1 standard deviation)
if not np.isnan(np.sum(hvsrm)):
    index_m = find_peaks(hvsrm)
else:
    index_m = list()

peakm = init_peaks(x_values, hvsrm, index_m, hvsr_band, peak_water_level_m)
peakm = check_clarity(x_values, hvsrm, peakm)

peak = check_stability(stdf, peak, hvsr_log_std, True)
peak = check_freq_stability(peak, peakm, peakp)

if do_plot > 0 and len(hvsr) > 0:
    nx = len(x_values) - 1
    plt.suptitle(plot_title)
    if plot_pdf or plot_psd:
        ax.append(plt.subplot(plotRows, 1, 4))
    else:
        ax.append(plt.subplot(1, 1, 1))

    plt.semilogx(np.array(x_values[0:nx]), hvsr, lw=1, c='blue', label='HVSR')
    plt.semilogx(np.array(x_values[0:nx]), hvsrp, c='red', lw=1, ls='--',
                 label='{} {}'.format(get_char(u'\u00B11'), get_char(u'\u03C3')))
    plt.semilogx(np.array(x_values[0:nx]), hvsrm, c='red', lw=1, ls='--')
    # plt.semilogx(np.array(x_values),hvsrp2,c='r',lw=1,ls='--')
    # plt.semilogx(np.array(x_values),hvsr_m2,c='r',lw=1,ls='--')
    plt.ylabel(param.hvsrYlabel)
    plt.legend(loc='upper left')

    plt.xlim(param.hvsrXlim)
    ax[-1].set_ylim(hvsr_ylim)
    plt.xlabel(param.xLabel[xtype])

    for i in range(len(peak)):
        plt.semilogx(peak[i]['f0'], peak[i]['A0'], marker='o', c='r')
        plt.semilogx((peak[i]['f0'], peak[i]['f0']), (hvsr_ylim[0], peak[i]['A0']), c='red')
        if stdf[i] < float(peak[i]['f0']):
            dz = stdf[i]
            plt.axvspan(float(peak[i]['f0']) - dz, float(peak[i]['f0']) + dz, facecolor='#909090', alpha=0.5)
            plt.semilogx((peak[i]['f0'], peak[i]['f0']), (hvsr_ylim[0], hvsr_ylim[1]), c='#dcdcdc', lw=0.5)

    plt.savefig(
        os.path.join(param.imageDirectory + '/' + fileLib.hvsrFileName(network, station, location, start, end)).replace(
            '.txt', '.png'), dpi=param.imageDpi, transparent=True, bbox_inches='tight', pad_inches=0.1)
if not dfa:
    print_peak_report(station_header, report_header, peak, report_information, min_rank)

if show_plot:
    if verbose >= 0:
        msgLib.info('SHOW PLOT')
    plt.show()
