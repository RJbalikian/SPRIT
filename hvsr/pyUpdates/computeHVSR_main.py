import utilities
import powspecdens
import readhvsr
import msgLib
import fileLib
import setParams
import hvsrCalcs
import ioput

import datetime
import sys
import os

import matplotlib
import numpy as np
import math

import time
import urllib
import xml.etree.ElementTree as ET

import matplotlib.pyplot as plt
from matplotlib.offsetbox import AnchoredText

import obspy

#Main variables
greek_chars = {'sigma': u'\u03C3', 'epsilon': u'\u03B5', 'teta': u'\u03B8'}
channel_order = {'Z': 0, '1': 1, 'N': 1, '2': 2, 'E': 2}
separator_character = '='

t0 = time.time()
display = True
max_rank = 0
plotRows = 4

# Set run parameters.
args = utilities.get_args(sys.argv)
if len(args) <= 1:
    sys.exit()

verbose = int(utilities.get_param(args, 'verbose', msgLib, -1, be_verbose=setParams.verbose))
if verbose >= 0:
    print('\n[INFO]', sys.argv[0])#, version)

report_information = int(utilities.get_param(args, 'report_information', msgLib, 1, be_verbose=verbose))

# Get channels and sort them in the reverse ] order to make sure that we always have ?HZ first.
# Order of the horizontals is not important.
channels = utilities.get_param(args, 'chan', msgLib, setParams.chan)
channelList = sorted(channels.split(','), reverse=True)
if len(channelList) < 3:
    msgLib.error('need 3 channels!', 1)
    sys.exit()

sorted_channel_list = channelList.copy()
for channel in channelList:
    sorted_channel_list[channel_order[channel[2]]] = channel

# See if we want to reject suspect PSDs.
remove_outliers = bool(int(utilities.get_param(args, 'removeoutliers', msgLib, False)))
msgLib.info('remove_outliers: {}'.format(remove_outliers))

# Minimum SESAME 2004 rank to be accepted.
min_rank = float(utilities.get_param(args, 'minrank', msgLib, setParams.minrank))

# network, station, and location to process.
network = utilities.get_param(args, 'net', msgLib, None)
if network is None:
    msgLib.error('network not defined!', 1)
    sys.exit()
station = utilities.get_param(args, 'sta', msgLib, None)
if station is None:
    msgLib.error('station not defined!', 1)
    sys.exit()
location = utilities.get_param(args, 'loc', msgLib, '*')
if location is None:
    msgLib.error('location not defined!', 1)
    sys.exit()

# Start of the window.
start = utilities.get_param(args, 'start', msgLib, None)
start_hour = 'T00:00:00'
start_time = time.strptime(start, '%Y-%m-%d')
end = utilities.get_param(args, 'end', msgLib, None)

# If start and end are the same day, process that day.
if start.strip() == end.strip():
    end_hour = 'T23:59:59'
else:
    end_hour = 'T00:00:00'
end_time = datetime.datetime.time.strptime(end, '%Y-%m-%d')

# Break the start-end interval to n segments.
n = int(utilities.get_param(args, 'n', msgLib, 1))
date_list = utilities.date_range(start, end, n)
msgLib.info('DATE LIST: {}'.format(date_list))

# How to combine h1 & h2.
method = int(utilities.get_param(args, 'method', msgLib, setParams.method))
if method <= 0 or method > 6:
    msgLib.error('method {} for combining H1 & H2 is invalid!'.format(method), 1)
    sys.exit()
elif method == 1:
    dfa = 1
else:
    dfa = 0

msgLib.info('Combining H1 and H2 Using {} method'.format(setParams.methodList[method]))

do_plot = int(utilities.get_param(args, 'plot', msgLib, setParams.plot))
show_plot = int(utilities.get_param(args, 'showplot', msgLib, setParams.plot))
plot_psd = int(utilities.get_param(args, 'plotpsd', msgLib, setParams.plotpsd))
plot_pdf = int(utilities.get_param(args, 'plotpdf', msgLib, setParams.plotpdf))
plot_bad = int(utilities.get_param(args, 'plotbad', msgLib, setParams.plotbad))
plot_nnm = int(utilities.get_param(args, 'plotnnm', msgLib, setParams.plotnnm))

day_values_passed = [[], [], []]
water_level = float(utilities.get_param(args, 'waterlevel', msgLib, setParams.waterlevel))
hvsr_ylim = setParams.hvsrylim
hvsr_ylim[1] = float(utilities.get_param(args, 'ymax', msgLib, setParams.hvsrylim[1]))
xtype = utilities.get_param(args, 'xtype', msgLib, setParams.xtype)
hvsr_band = utilities.get_param(args, 'hvsrband', msgLib, setParams.hvsrband)

report_header = '.'.join([network, station, location, '-'.join(sorted_channel_list)])
station_header = report_header
station_header = '{} {} {}'.format(station_header, start, end)
report_header += ' {} from {} to {}\nusing {}'.format(report_header, start, end, setParams.methodList[method])
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
                os.path.join(setParams.baselineDirectory, fileLib.baselineFileName(network, station, location, channel)),
                'r')
        except Exception as e:
            msgLib.error('Failed to read baseline file {}\n'
                         'Use the getStationChannelBaseline.py script to generate the baseline file or '
                         'set the parameter removeoutliers=0.'.
                         format(os.path.join(setParams.baselineDirectory, fileLib.baselineFileName(network,
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
        URL = '{}target={}&starttime={}{}&endtime={}{}&format=xml&correct=true'.format(setParams.mustangPsdUrl, target,
                                                                                       date_list[date_index],
                                                                                       start_hour,
                                                                                       date_list[date_index + 1],
                                                                                       end_hour)
        if verbose >= 0:
            msgLib.info('requesting: {}'.format(URL))
            t0 = utilities.time_it(t0)
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
            t0 = utilities.time_it(t0)

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
            (thisX, thisY, thisP) = hvsrCalcs.get_pdf('{}target={}&starttime={}{}&endtime={}{}&format=text'.format(
                setParams.mustangPdfUrl, target, date_list[date_index], start_hour, date_list[date_index + 1],
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
            t0 = utilities.time_it(t0)

    # PSDs:
    # Initial settings.
    if channel_index == 0:
        if do_plot:
            if verbose >= 0:
                msgLib.info('PLOT PSD')

            fig = plt.figure(figsize=setParams.imageSize, facecolor='white')
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
        (ok, notok) = utilities.check_y_range(psd_values, pct_low, pct_high)
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
        t0 = utilities.time_it(t0)
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
        t0 = utilities.time_it(t0)

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
                t0 = utilities.time_it(t0)

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
                t0 = utilities.time_it(t0)
        if plot_pdf:
            cmap = pqlx

            ok = list()
            im = plt.scatter(pdf_x, pdf_y, c=pdfP, s=46.5, marker='_', linewidth=setParams.lw, edgecolor='face', cmap=cmap,
                             alpha=setParams.alpha)
            ax[channel_index].set_xscale('log')

        if verbose:
            msgLib.info('Tune plots.')
        if verbose >= 0:
            t0 = utilities.time_it(t0)
        if remove_outliers:
            plt.semilogx(np.array(x_values), pct_high, c='yellow', label='{}%'.format(percent_high))
            plt.semilogx(np.array(x_values), pct_mid, c='red', label='{}%'.format(percent_mid))
            plt.semilogx(np.array(x_values), pct_low, c='orange', label='{}%'.format(percent_low))
        plt.semilogx((setParams.hvsrXlim[0], setParams.hvsrXlim[0]), setParams.yLim, c='black')
        plt.semilogx((setParams.hvsrXlim[1], setParams.hvsrXlim[1]), setParams.yLim, c='black')
        p1 = plt.axvspan(setParams.xLim[xtype][0], setParams.hvsrXlim[0], facecolor='#909090', alpha=0.5)
        p2 = plt.axvspan(setParams.hvsrXlim[1], setParams.xLim[xtype][1], facecolor='#909090', alpha=0.5)
        # plt.title(' '.join([target,start,'to',end]))
        plt.ylim(setParams.yLim)
        plt.xlim(setParams.xLim[xtype])
        plt.ylabel(setParams.yLabel)

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
            plt.clim(setParams.pMin, setParams.pMax)


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
                pz = hvsrCalcs.get_power([daily_psd[0][day][i][j], daily_psd[0][day][i][j + 1]], [x_values[j], x_values[j + 1]])
                Pz.append(pz)
                sum_pz += pz
                p1 = hvsrCalcs.get_power([daily_psd[1][day][i][j], daily_psd[1][day][i][j + 1]], [x_values[j], x_values[j + 1]])
                P1.append(p1)
                sum_p1 += p1
                p2 = hvsrCalcs.get_power([daily_psd[2][day][i][j], daily_psd[2][day][i][j + 1]], [x_values[j], x_values[j + 1]])
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
    t0 = utilities.time_it(t0)

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
fileLib.mkdir(setParams.hvsrDirectory, path)
out_file_name = os.path.join(setParams.hvsrDirectory, path, fileLib.hvsrFileName(network, station, location, start, end))

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
                hvsr0 = hvsrCalcs.get_hvsr(psd0, psd1, psd2, [x_values[j], x_values[j + 1]], use_method=method)
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
                hvsr0 = hvsrCalcs.get_hvsr(psd0, psd1, psd2, [x_values[j], x_values[j + 1]], use_method=method)
                hvsr_tmp.append(hvsr0)
            else:
                if verbose > 0:
                    msgLib.warning(sys.argv[0], day + ' missing component, skipped!')
                missing += 1
                continue
    if not np.isnan(np.sum(hvsr_tmp)):
        hvsrPeaks.append(hvsrCalcs.find_peaks(hvsr_tmp))

report_header += '\n'
report_header += ' '.join([str(missing), 'PSDs are missing one or more components\n'])

# Find  the relative extrema of hvsr
if not np.isnan(np.sum(hvsr)):
    indexList = hvsrCalcs.find_peaks(hvsr)
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

peak = hvsrCalcs.init_peaks(x_values, hvsr, indexList, hvsr_band, peak_water_level)
peak = hvsrCalcs.check_clarity(x_values, hvsr, peak, True)

# Find  the relative extrema of hvsrp (hvsr + 1 standard deviation)
if not np.isnan(np.sum(hvsrp)):
    index_p = hvsrCalcs.find_peaks(hvsrp)
else:
    index_p = list()

peakp = hvsrCalcs.init_peaks(x_values, hvsrp, index_p, hvsr_band, peak_water_level_p)
peakp = hvsrCalcs.check_clarity(x_values, hvsrp, peakp)

# Find  the relative extrema of hvsrp (hvsr - 1 standard deviation)
if not np.isnan(np.sum(hvsrm)):
    index_m = hvsrCalcs.find_peaks(hvsrm)
else:
    index_m = list()

peakm = hvsrCalcs.init_peaks(x_values, hvsrm, index_m, hvsr_band, peak_water_level_m)
peakm = hvsrCalcs.check_clarity(x_values, hvsrm, peakm)

peak = hvsrCalcs.check_stability(stdf, peak, hvsr_log_std, True)
peak = hvsrCalcs.check_freq_stability(peak, peakm, peakp)

if do_plot > 0 and len(hvsr) > 0:
    nx = len(x_values) - 1
    plt.suptitle(plot_title)
    if plot_pdf or plot_psd:
        ax.append(plt.subplot(plotRows, 1, 4))
    else:
        ax.append(plt.subplot(1, 1, 1))

    plt.semilogx(np.array(x_values[0:nx]), hvsr, lw=1, c='blue', label='HVSR')
    plt.semilogx(np.array(x_values[0:nx]), hvsrp, c='red', lw=1, ls='--',
                 label='{} {}'.format(utilities.get_char(u'\u00B11'), utilities.get_char(u'\u03C3')))
    plt.semilogx(np.array(x_values[0:nx]), hvsrm, c='red', lw=1, ls='--')
    # plt.semilogx(np.array(x_values),hvsrp2,c='r',lw=1,ls='--')
    # plt.semilogx(np.array(x_values),hvsr_m2,c='r',lw=1,ls='--')
    plt.ylabel(setParams.hvsrYlabel)
    plt.legend(loc='upper left')

    plt.xlim(setParams.hvsrXlim)
    ax[-1].set_ylim(hvsr_ylim)
    plt.xlabel(setParams.xLabel[xtype])

    for i in range(len(peak)):
        plt.semilogx(peak[i]['f0'], peak[i]['A0'], marker='o', c='r')
        plt.semilogx((peak[i]['f0'], peak[i]['f0']), (hvsr_ylim[0], peak[i]['A0']), c='red')
        if stdf[i] < float(peak[i]['f0']):
            dz = stdf[i]
            plt.axvspan(float(peak[i]['f0']) - dz, float(peak[i]['f0']) + dz, facecolor='#909090', alpha=0.5)
            plt.semilogx((peak[i]['f0'], peak[i]['f0']), (hvsr_ylim[0], hvsr_ylim[1]), c='#dcdcdc', lw=0.5)

    plt.savefig(
        os.path.join(setParams.imageDirectory + '/' + fileLib.hvsrFileName(network, station, location, start, end)).replace(
            '.txt', '.png'), dpi=setParams.imageDpi, transparent=True, bbox_inches='tight', pad_inches=0.1)
if not dfa:
    ioput.print_peak_report(station_header, report_header, peak, report_information, min_rank)

if show_plot:
    if verbose >= 0:
        msgLib.info('SHOW PLOT')
    plt.show()
