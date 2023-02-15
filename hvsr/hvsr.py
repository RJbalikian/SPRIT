import datetime
import math
import os
import pathlib
import sys
import tempfile
import warnings
import xml.etree.ElementTree as ET

import matplotlib.pyplot as plt
import obspy
import numpy as np
import scipy

import hvsr.hvsrtools.msgLib as msgLib

"""
This file contains all the updated functions needed
"""
##msgLib functions
#Post message
def message(post_message):
    """print a run message"""
    bar = "*" * 12
    print("%s %s %s" % (bar, post_message, bar))

#Post error
def error(err_message, code):
    """print an error message"""
    print("\n[ERR] %s\n" % err_message, flush=True)
    return code

#Post warning
def warning(sender, warn_message):
    """print a warning message"""
    print("[WARN] from %s: %s" % (sender, warn_message), flush=True)

#Post info message
def info(info_message):
    """print an informative message"""
    print("[INFO] %s" % info_message, flush=True)
    return

#Converts filepaths to pathlib paths, if not already
def checkifpath(filepath):
    # checks if the variable is any instance of pathlib
    if isinstance(filepath, pathlib.PurePath):
        pass
    else:
        try:
            filepath = pathlib.Path(filepath)
            #print('Converted string to pathlib path') #Assume a string was input rather than pathlib object
        except:
            msgLib.error('Input cannot be converted to pathlib path', 0)
    return filepath

#Formats time into desired output
def __formatTime(inputDT, tzone='utc', dst=True):
    """
    Formats input time to datetime objects in utc
    --------------
    Parameters:
        inputDT : str or datetime obj input datetime. Can include date and time, just date (time inferred to be 00:00:00.00) or just time (if so, date is set as today)
        tzone   : str='utc' or int {'utc', 'local'} timezone of data entry. 
                    If string and not utc, assumed to be timezone of computer running the process.
                    If int, assumed to be offset from UTC (e.g., CST in the United States is -6; CDT in the United States is -5)
        dst     : bool=True If any string aside from 'utc' is specified for tzone, this will adjust according to daylight savings time. If tzone is int, no adjustment made

    --------------
    Returns:
        outputTimeObj   : datetime object in UTC

    """
    if type(inputDT) is str:
        #tzone = 'America/Chicago'
        #Format string to datetime obj
        div = '-'
        timeDiv = 'T'
        if "/" in inputDT:
            div = '/'
            hasDate = True
        elif '-' in inputDT:
            div = '-'
            hasDate = True
        else:
            hasDate= False
            year = datetime.datetime.today().year
            month = datetime.datetime.today().month
            day = datetime.datetime.today().day

        if ':' in inputDT:
            hasTime = True
            if 'T' in inputDT:
                timeDiv = 'T'
            else:
                timeDiv = ' '
        else:
            hasTime = False
        
        if hasDate:
            #If first number is 4-dig year (assumes yyyy-dd-mm is not possible)
            if len(inputDT.split(div)[0])>2:
                year = inputDT.split(div)[0]
                month = inputDT.split(div)[1]
                day = inputDT.split(div)[2].split(timeDiv)[0]

            #If last number is 4-dig year            
            elif len(inputDT.split(div)[2].split(timeDiv)[0])>2:
                #..and first number is day
                if int(inputDT.split(div)[0])>12:
                    #dateStr = '%d'+div+'%m'+div+'%Y'   
                    year = inputDT.split(div)[2].split(timeDiv)[0]
                    month = inputDT.split(div)[1]
                    day = inputDT.split(div)[0]
                #...and first number is month (like American style)                             
                else:
                    year = inputDT.split(div)[2].split(timeDiv)[0]
                    month = inputDT.split(div)[0]
                    day = inputDT.split(div)[1]     
            
            #Another way to catch if first number is (2-digit) year
            elif int(inputDT.split(div)[0])>31:
                #dateStr = '%y'+div+'%m'+div+'%d'
                year = inputDT.split(div)[0]
                #Assumes anything less than current year is from this century
                if year < datetime.datetime.today().year:
                    year = '20'+year
                else:#...and anything more than current year is from last century
                    year = '19'+year
                #assumes day will always come last in this instance, as above
                month = inputDT.split(div)[1]
                day = inputDT.split(div)[2].split(timeDiv)[0]
            #If last digit is (2 digit) year           
            elif int(inputDT.split(div)[2].split(timeDiv)[0])>31:
                #...and first digit is day
                if int(inputDT.split(div)[0])>12:
                    #dateStr = '%d'+div+'%m'+div+'%y'       
                    year = inputDT.split(div)[2].split(timeDiv)[0]
                    if year < datetime.datetime.today().year:
                        year = '20'+year
                    else:
                        year = '19'+year
                    month = inputDT.split(div)[1]
                    day = inputDT.split(div)[0]                           
                else: #...and second digit is day
                    #dateStr = '%m'+div+'%d'+div+'%y'
                    year = inputDT.split(div)[2].split(timeDiv)[0]
                    if year < datetime.datetime.today().year:
                        year = '20'+year
                    else:
                        year = '19'+year
                    month = inputDT.split(div)[0]
                    day = inputDT.split(div)[1]                  

        hour=0
        minute=0
        sec=0
        microS=0
        if hasTime:
            if hasDate:
                timeStr = inputDT.split(timeDiv)[1]
            else:
                timeStr = inputDT
            
            if 'T' in timeStr:
                timeStr=timeStr.split('T')[1]
            elif ' ' in timeStr:
                timeStr=timeStr.split(' ')[1]

            timeStrList = timeStr.split(':')
            if len(timeStrList[0])>2:
                timeStrList[0] = timeStrList[0][-2:]
            elif int(timeStrList[0]) > 23:
                timeStrList[0] = timeStrList[0][-1:]
            
            if '.' in timeStrList[2]:
                microS = int(timeStrList[2].split('.')[1])
                timeStrList[2] = timeStrList[2].split('.')[0]

            hour = int(timeStrList[0])
            minute=int(timeStrList[1])
            sec = int(timeStrList[2])


        outputTimeObj = datetime.datetime(year=int(year),month=int(month), day=int(day),
                                hour=int(hour), minute=int(minute), second=int(sec), microsecond=int(microS))

    elif type(inputDT) is datetime.datetime or type(inputDT) is datetime.time:
        outputTimeObj = inputDT

    if type(tzone) is int: #Plus/minus needs to be correct there
        outputTimeObj = outputTimeObj-datetime.timedelta(hours=tzone)
    elif type(tzone) is str:
        if tzone != 'utc':
            utc_time = datetime.datetime.utcnow()
            localTime = datetime.datetime.now()
            utcOffset = utc_time-localTime
            outputTimeObj=outputTimeObj+utcOffset
            utcOffset = utc_time-localTime
            outputTimeObj = outputTimeObj+utcOffset
            if dst:
                outputTimeObj = outputTimeObj+datetime.timedelta(hours=1)

    return outputTimeObj

#Sort Channels later
def __sortchannels(channels=['EHZ', 'EHN', 'EHE']):
    """"
    Sort channels. Z/vertical should be first, horizontal order doesn't matter, but N 2nd and E 3rd is default
        ----------------
        Parameters
            channels    : list = ['EHZ', 'EHN', 'EHE']
    """
    channel_order = {'Z': 0, '1': 1, 'N': 1, '2': 2, 'E': 2}

    sorted_channel_list = channels.copy()
    for channel in channels:
        sorted_channel_list[channel_order[channel[2]]] = channel
    return sorted_channel_list
#Define input parameters
def input_param(network='AM', 
                        station='RAC84', 
                        loc='00', 
                        channels=['EHZ', 'EHN', 'EHE'],
                        date=str(datetime.datetime.now().date()),
                        starttime = '00:00:00.00',
                        endtime = '23:59:99.99',
                        tzone = 'America/Chicago', #or 'UTC'
                        dst = True,
                        lon = -88.2290526,
                        lat =  40.1012122,
                        elevation = 755,
                        depth = 0,
                        dataPath = '',
                        metaPath = r'resources\raspshake_metadata.inv',
                        hvsr_band = [0.4, 40] 
                        ):

    #Reformat time
    if type(date) is datetime.datetime:
        date = str(date.date())
    elif type(date) is datetime.date:
        date=str(date)

    if type(starttime) is str:
        if 'T' in starttime:
            date=starttime.split('T')[0]
            starttime = starttime.split('T')[1]
    elif type(starttime) is datetime.datetime:
        date = str(starttime.date())
        starttime = str(starttime.time())
    elif type(starttime) is datetime.time():
        starttime = str(starttime)
    
    starttime = date+"T"+starttime
    starttime = __formatTime(starttime, tzone=tzone, dst=dst)

    if type(endtime) is str:
        if 'T' in endtime:
            date=endtime.split('T')[0]
            endtime = endtime.split('T')[1]
    elif type(endtime) is datetime.datetime:
        date = str(endtime.date())
        endtime = str(endtime.time())
    elif type(endtime) is datetime.time():
        endtime = str(endtime)

    endtime = date+"T"+endtime
    endtime = __formatTime(endtime, tzone=tzone, dst=dst)

    date = datetime.date(year=int(date.split('-')[0]), month=int(date.split('-')[1]), day=int(date.split('-')[2]))

    if metaPath == r'resources\raspshake_metadata.inv':
        metaPath = str(pathlib.Path(os.getcwd()))+'\\'+metaPath

    inputParamDict = {'net':network,'sta':station, 'loc':loc, 'cha':channels,
                    'date':date,'starttime':starttime,'endtime':endtime, 'timezone':'UTC',
                    'longitude':lon,'latitude':lat,'elevation':elevation,'depth':depth,
                    'dataPath':dataPath, 'metaPath':metaPath, 'hvsr_band':hvsr_band
                    }

    return inputParamDict

#Read in metadata .inv file, specifically for RaspShake
def updateShakeMetadata(filepath, network='AM', station='RAC84', channels=['EHZ', 'EHN', 'EHE'], 
                    startdate=str(datetime.datetime(2022,1,1)), enddate=str(datetime.datetime.today()), 
                    lon = '-88.2290526', lat = '40.1012122', elevation = '755', depth='0', write=True):
    """
    Reads static metadata file provided for Rasp Shake and updates with input parameters
        --------------
        PARAMETERS
            filepath
            network
            station
            channels
            startdate
            enddate
            lon
            lat
            elevation
            depth
        -------------
        Returns
        
        updated tree, output filepath
    """
    filepath = checkifpath(filepath)

    parentPath = filepath.parent
    filename = filepath.stem

    tree = ET.parse(str(filepath))
    root = tree.getroot()

    prefix= "{http://www.fdsn.org/xml/station/1}"

    #metadata  = list(root)#.getchildren()

    for item in root.iter(prefix+'Channel'):
        item.attrib['endDate'] = enddate

    for item in root.iter(prefix+'Station'):
        item.attrib['code'] = station
        item.attrib['endDate'] = enddate

    for item in root.iter(prefix+'Network'):
        item.attrib['code'] = network
        
    for item in root.iter(prefix+'Latitude'):
        item.text = lat

    for item in root.iter(prefix+'Longitude'):
        item.text = lon

    for item in root.iter(prefix+'Created'):
        nowTime = str(datetime.datetime.now())
        item.text = nowTime

    for item in root.iter(prefix+'Elevation'):
        item.text= elevation

    for item in root.iter(prefix+'Depth'):
        item.text=depth

    #Set up (and) export
    filetag = '_'+str(datetime.datetime.today().date())

    outfile = str(parentPath)+'\\'+filename+filetag+'.inv'

    if write:
        tree.write(outfile, xml_declaration=True, method='xml',encoding='UTF-8')

    #Create temporary file for reading into obspy
    tpf = tempfile.NamedTemporaryFile(delete=False)
    stringRoot = ET.tostring(root, encoding='UTF-8', method='xml')
    tpf.write(stringRoot)
    tpf.close()

    inv = obspy.read_inventory(tpf.name, format='STATIONXML', level='response')

    os.remove(tpf.name)

    return inv

#Gets the metadata for Raspberry Shake, specifically for 3D v.7
def getShakeMetadata(inv, station='RAC84', network='AM', channels = ['EHZ', 'EHN', 'EHE']):
    """Get Shake metadata and output as paz parameter needed for PPSD
    Parameters:
        inv     : file, file object or obspy inventory object
        station : str           station name (must be the same as in the inv object or file)
        network : str           network name (must be the same as in the inv object or file)
        channels: list of str   channel names (must be the same as in the inv object or file)
    """
    if isinstance(inv, pathlib.PurePath):
        inv = checkifpath(inv)
        tree = ET.parse(inv)
        root = tree.getroot()
    else:
        #Create temporary file from inventory object
        tpf = tempfile.NamedTemporaryFile(delete=False)
        inv.write(tpf.name, format='STATIONXML')

        #Read data into xmlTree
        tree = ET.parse(tpf.name)
        root = tree.getroot()

        #Close and remove temporary file
        tpf.close()
        os.remove(tpf.name)

    c=channels[0]
    pzList = [str(n) for n in list(range(7))]
    s=pzList[0]

    prefix= "{http://www.fdsn.org/xml/station/1}"

    sensitivityPath = "./"+prefix+"Network[@code='"+network+"']/"+prefix+"Station[@code='"+station+"']/"+prefix+"Channel[@code='"+c+"']/"+prefix+"Response/"+prefix+"InstrumentSensitivity/"+prefix+"Value"
    gainPath = "./"+prefix+"Network[@code='"+network+"']/"+prefix+"Station[@code='"+station+"']/"+prefix+"Channel[@code='"+c+"']/"+prefix+"Response/"+prefix+"Stage[@number='1']/"+prefix+"StageGain/"+prefix+"Value"

    #paz = []
    paz = {}
    for c in channels:
        channelPaz = {}
        #channelPaz['channel'] = c
        for item in root.findall(sensitivityPath):
            channelPaz['sensitivity']=float(item.text)

        for item in root.findall(gainPath):
            channelPaz['gain']=float(item.text)
        
        poleList = []
        zeroList = []
        for s in pzList:
            if int(s) < 4:
                polePathReal = "./"+prefix+"Network[@code='"+network+"']/"+prefix+"Station[@code='"+station+"']/"+prefix+"Channel[@code='"+c+"']/"+prefix+"Response/"+prefix+"Stage[@number='1']/"+prefix+"PolesZeros/"+prefix+"Pole[@number='"+s+"']/"+prefix+"Real"
                polePathImag = "./"+prefix+"Network[@code='"+network+"']/"+prefix+"Station[@code='"+station+"']/"+prefix+"Channel[@code='"+c+"']/"+prefix+"Response/"+prefix+"Stage[@number='1']/"+prefix+"PolesZeros/"+prefix+"Pole[@number='"+s+"']/"+prefix+"Imaginary"
                for poleItem in root.findall(polePathReal):
                    poleReal = poleItem.text
                for poleItem in root.findall(polePathImag):
                    pole = complex(float(poleReal), float(poleItem.text))
                    poleList.append(pole)
                    channelPaz['poles'] = poleList
                    #channelPaz['poles'] = list(set(poleList))
            else:
                zeroPathReal = "./"+prefix+"Network[@code='"+network+"']/"+prefix+"Station[@code='"+station+"']/"+prefix+"Channel[@code='"+c+"']/"+prefix+"Response/"+prefix+"Stage[@number='1']/"+prefix+"PolesZeros/"+prefix+"Zero[@number='"+s+"']/"+prefix+"Real"
                zeroPathImag = "./"+prefix+"Network[@code='"+network+"']/"+prefix+"Station[@code='"+station+"']/"+prefix+"Channel[@code='"+c+"']/"+prefix+"Response/"+prefix+"Stage[@number='1']/"+prefix+"PolesZeros/"+prefix+"Zero[@number='"+s+"']/"+prefix+"Imaginary"
                for zeroItem in root.findall(zeroPathReal):
                    zeroReal = zeroItem.text
                
                for zeroItem in root.findall(zeroPathImag):
                    zero = complex(float(zeroReal), float(zeroItem.text))
                    #zero = zeroReal + "+" + zeroItem.text+'j'
                    zeroList.append(zero)
                    #channelPaz['zeros'] = list(set(zeroList))
                    channelPaz['zeros'] = zeroList

        paz[str(c)] = channelPaz
    return paz

#Reads in traces to obspy stream
def fetchdata(datapath, inv, date=datetime.datetime.today(), inst='raspshake'):

    """Fetch ambient seismic data from a source to read into obspy stream
        Parameters
        ----------
        datapath : str or pathlib path
            Path to directory containing data. For Raspberry Shakes, 
            this is the directory where the channel folders are located.
        inv     : obspy inventory object containing metadata for instrument that collected data to be fetched
        date : str, tuple, or date object
            Date for which to read in the data traces. 
            If string, will attempt to decode to convert to a date format.
            If tuple, assumes first item is day of year (DOY) and second item is year 
            If date object, will read it in directly.
        inst : str {'raspshake}
            The type of instrument from which the data is reading. Currently, only raspberry shake supported
        
        Returns
        ---------
        rawDataIN : obspy data stream with 3 traces: Z (vertical), N (North-south), and E (East-west)
        
        """

    datapath = checkifpath(datapath)

    #Need to put dates and times in right formats first
    if type(date) is datetime.datetime:
        doy = date.timetuple().tm_yday
        year = date.year
    elif type(date) is datetime.date:
        date = datetime.datetime.combine(date, datetime.time(hour=0, minute=0, second=0))
        doy = date.timetuple().tm_yday
        year = date.year
    elif type(date) is tuple:
        if date[0]>366:
            msgLib.error('First item in date tuple must be day of year (0-366)', 0)
        elif date[1] > datetime.datetime.now().year:
            msgLib.error('Second item in date tuple should be year, but given item is in the future', 0)
        else:
            doy = date[0]
            year = date[1]
    elif type(date) is str:
        if '/' in date:
            dateSplit = date.split('/')            
        elif '-' in date:
            dateSplit = date.split('-')
        else:
            dateSplit = date

        if int(dateSplit[0]) > 31:
            date = datetime.datetime(int(dateSplit[0]), int(dateSplit[1]), int(dateSplit[2]))
            doy = date.timetuple().tm_yday
            year = date.year
        elif int(dateSplit[0])<=12 and int(dateSplit[2]) > 31:
            msgLib.info("Preferred date format is 'yyyy-mm-dd' or 'yyyy/mm/dd'. Will attempt to parse date.")
            date = datetime.datetime(int(dateSplit[2]), int(dateSplit[0]), int(dateSplit[1]))
            doy = date.timetuple().tm_yday
            year = date.year
        else:
            msgLib.info("Preferred date format is 'yyyy-mm-dd' or 'yyyy/mm/dd'. Cannot parse date.")
    else: #FOR NOW, need to update
        date = datetime.datetime.now()
        doy = date.timetuple().tm_yday
        year = date.year
        print("Did not recognize date, using year {} and day {}".format(year, doy))

    print('Day of Year:', doy)

    if inst=='raspshake':
        folderList = []
        folderPathList = []
        for child in datapath.iterdir():
            if child.is_dir():
                folderPathList.append(child)
                folderList.append(child.stem.split('.')[0])
        folderList.sort(reverse=True) #Channels in Z, N, E order

        if len(folderList) !=3:
            msgLib.error('3 channels needed!', 1)
        else:
            filepaths = []
            for folder in folderPathList:
                for file in folder.iterdir():
                    if str(doy) in str(file.name) and str(year) in str(file.name):
                        filepaths.append(file)

            if len(filepaths) == 0:
                msgLib.info('No file found for specified day/year. The following days/files exist for specified year in this directory')
                doyList = []
                for j, folder in enumerate(folderPathList):
                    for i, file in enumerate(folder.iterdir()):
                        if j ==0:
                            doyList.append(str(year) + ' ' + str(file.name[-3:]))
                            print(datetime.datetime.strptime(doyList[i], '%Y %j').strftime('%b %d'), '| Day of year:' ,file.name[-3:])

            traceList = []
            for i, f in enumerate(filepaths):
                with warnings.catch_warnings():
                    warnings.filterwarnings(action='ignore', message='^readMSEEDBuffer()')
                    st = obspy.read(str(f))
                    tr = (st[0])
                    #tr= obspy.Trace(tr.data,header=meta)
                    traceList.append(tr)
            rawDataIN = obspy.Stream(traceList)
            rawDataIN.attach_response(inv)
    if 'Z' in str(rawDataIN.traces[0])[12:15]:
        pass
    else:
        rawDataIN = rawDataIN.sort(['channel'], reverse=True) #z, n, e order
    return rawDataIN

#Trim data 
def trimdata(stream, start, end, exportdir=None, sitename=None, export=None):
    """Function to trim data to start and end time
        -------------------
        Parameters:
            stream  : obspy.stream object   Stream to be trimmed
            start   : datetime object       Start time of trim, in UTC
            end     : datetime object       End time of trim, in UTC
            export  : str                   If not specified, does not export. 
                                                Otherwise, exports trimmed stream using obspy write function in format provided as string
                                                https://docs.obspy.org/packages/autogen/obspy.core.stream.Stream.write.html#obspy.core.stream.Stream.write
            exportdir: str or pathlib obj   Output file to export trimmed data to; 
            sitename: str                   Name of site for user reference. It is added as prefix to filename when designated.
                                                If not designated, it is not included.
            outfile : str                   Exact filename to output
                                                If not designated, uses default parameters (from input filename in standard seismic file format)
        ---------------------
        Returns:
            st_trimmed  : obspy.stream object Obpsy Stream trimmed to start and end times
    """
    st_trimmed = stream.copy()

    trimStart = obspy.UTCDateTime(start)
    trimEnd = obspy.UTCDateTime(end)
    st_trimmed.trim(starttime=trimStart, endtime=trimEnd)

    #Format export filepath, if exporting
    if export is not None and sitename is not None and exportdir is not None:
        if sitename is None:
            sitename=''
        else:
            sitename = sitename+'_'
        export = '.'+export
        net = st_trimmed[0].stats.network
        sta = st_trimmed[0].stats.station
        loc = st_trimmed[0].stats.location
        strtD=str(st_trimmed[0].stats.starttime.date)
        strtT=str(st_trimmed[0].stats.starttime.time)[0:2]
        strtT=strtT+str(st_trimmed[0].stats.starttime.time)[3:5]
        endT = str(st_trimmed[0].stats.endtime.time)[0:2]
        endT = endT+str(st_trimmed[0].stats.endtime.time)[3:5]

        exportdir = checkifpath(exportdir)
        exportdir = str(exportdir)
        if type(export) is str:
            filename = sitename+net+'.'+sta+'.'+loc+'.'+strtD+'_'+strtT+'-'+endT+export
        elif type(export) is bool:
            filename = sitename+net+'.'+sta+'.'+loc+'.'+strtD+'_'+strtT+'-'+endT+'.mseed'

        exportFile = exportdir+'\\'+filename

        st_trimmed.write(filename=exportFile)
    else:
        pass

    return st_trimmed

#Generate PPSDs for each channel
def generatePPSDs(stream, paz, ppsd_length=60, **kwargs):
    """Generates PPSDs for each channel
        Channels need to be in Z, N, E order
        Info on PPSD creation here: https://docs.obspy.org/packages/autogen/obspy.signal.spectral_estimation.PPSD.html
        ---------------------
        Parameters:
            stream  :   obspy stream object from which to pull data
            paz     :   dictionary of dictionaries    a dictionary with dictionaries containing poles and zeros (paz) info for each channel, from inv file
            ppsd_length:  length of data passed to psd, in seconds. Per obspy: Longer segments increase the upper limit of analyzed periods but decrease the number of analyzed segments.
            **kwargs:   keyword arguments that can be passed to obspy.signal.PPSD

        ----------------------
        Returns:
            ppsds   :   dictionary containing entries with ppsds for each channel
    """
    from obspy.imaging.cm import viridis_white_r
    from obspy.signal import PPSD
    ppsdE = PPSD(stream.select(channel='EHE').traces[0].stats, paz['EHE'], ppsd_length=ppsd_length, kwargs=kwargs)
    ppsdE.add(stream, verbose=False)

    ppsdN = PPSD(stream.select(channel='EHN').traces[0].stats, paz['EHN'], ppsd_length=ppsd_length, kwargs=kwargs)
    ppsdN.add(stream, verbose=False)

    ppsdZ = PPSD(stream.select(channel='EHZ').traces[0].stats, paz['EHZ'], ppsd_length=ppsd_length, kwargs=kwargs)
    ppsdZ.add(stream, verbose=False)

    ppsds = {'EHZ':ppsdZ, 'EHN':ppsdN, 'EHE':ppsdE}
    return ppsds

def __check_xvalues(ppsds):
    xLengths = []
    for k in ppsds.keys():
        xLengths.append(len(ppsds[k].period_bin_centers))
    if len(set(xLengths)) <= 1:
        pass #This means all channels have same number of period_bin_centers
    else:
        print('X-values (periods or frequencies) do not have the same values. \n This may result in computational errors')
        #Do stuff to fix it?
    return

def process_hvsr(ppsds, method=4, site=''):
    """
    This function will have all the stuff needed to process HVSR, as updated from local data
    Based on the notebook

    -----------------------
    Parameters:
        ppsds   : dict  Dictionary with three key-value pairs containing the PPSD outputs from the three channels from the generatePPSDs function

    -----------------------
    Return:

    """
    __check_xvalues(ppsds)
    methodList = ['DFA', 'Arithmetic Mean', 'Geometric Mean', 'Vector Summation', 'Quadratic Mean', 'Maximum Horizontal Value']
    for k in ppsds:
        
        x_freqs = np.divide(np.ones_like(ppsds[k].period_bin_centers), ppsds[k].period_bin_centers)
        x_periods = np.array(ppsds[k].period_bin_centers)

        y = np.mean(np.array(ppsds[k].psd_values), axis=0)

    x_freqs = {}
    x_periods = {}

    psdVals = {}
    stDev = {}
    stDevValsP = {}
    stDevValsM = {}
    psdRaw={}
    for k in ppsds:
        x_freqs[k] = np.divide(np.ones_like(ppsds[k].period_bin_centers), ppsds[k].period_bin_centers)
        x_periods[k] = np.array(ppsds[k].period_bin_centers)

        psdRaw[k] = np.array(ppsds[k].psd_values)
        psdVals[k] = np.mean(np.array(ppsds[k].psd_values), axis=0)

        stDev[k] = np.std(np.array(ppsds[k].psd_values), axis=0)
        stDevValsM[k] = np.array(psdVals[k] - stDev[k])
        stDevValsP[k] = np.array(psdVals[k] + stDev[k])
    #method=4
    #hvsr_curve = []
    #for j in range(len(x_freqs['EHZ'])-1):
    #    psd0 = [psdVals['EHZ'][j], psdVals['EHZ'][j + 1]]
    #    psd1 = [psdVals['EHE'][j], psdVals['EHE'][j + 1]]
    #    psd2 = [psdVals['EHN'][j], psdVals['EHN'][j + 1]]
    #    f =    [x_freqs['EHZ'][j], x_freqs['EHZ'][j + 1]]

        #hvsr0 = get_hvsr(psd0, psd1, psd2, f, use_method=method)
    #    hvsr = __get_hvsr(psd0, psd1, psd2, f, use_method=4)

    #    hvsr_curve.append(hvsr)

    #This gets the hvsr curve averaged from all time steps     
    hvsr_curve = __get_hvsr_curve(x=x_freqs['EHZ'], psd=psdVals, method=4)
    
    #Add some other variables to our output dictionary
    hvsr_out = {
                'x_freqs':x_freqs,
                'hvsr_curve':np.array(hvsr_curve),
                'x_period':x_periods,
                'psd_values':psdVals,
                'psd_raw':psdRaw,
                'ppsd_std':stDev,
                'ppsd_std_vals_m':stDevValsM,
                'ppsd_std_vals_p':stDevValsP,
                'method':methodList[method],
                'site':site,
                'ppsds':ppsds
                }
    
    #Get hvsr curve from three components at each time step
    hvsr_tSteps = []
    anyK = list(hvsr_out['psd_raw'].keys())[0]
    for tStep in range(hvsr_out['psd_raw'][anyK].shape[0]):
        tStepDict = {}
        for k in hvsr_out['psd_raw']:
            tStepDict[k] = hvsr_out['psd_raw'][k][tStep]
        hvsr_tSteps.append(__get_hvsr_curve(x=hvsr_out['x_freqs'][anyK], psd=tStepDict, method=method))
    hvsr_tSteps = np.array(hvsr_tSteps)
    
    hvsr_out['ind_hvsr_curves'] = hvsr_tSteps
    hvsr_out['ind_hvsr_stdDev'] = np.std(hvsr_tSteps, axis=0)
    #hvsr_out['ind_hvsr_stdDev_median'] = np.median(hvsr_tSteps, axis=0)


    tStepPeaks = []
    for tStepHVSR in hvsr_tSteps:
        tStepPeaks.append(__find_peaks(tStepHVSR))
    #tStepPeaks = np.array(tStepPeaks) #This is a list of lists, and the individual lists are different sizes

    hvsr_out['ind_hvsr_peak_indices'] = tStepPeaks
    hvsr_out['hvsr_peak_indices'] = __find_peaks(hvsr_out['hvsr_curve'])

    #Get other HVSR parameters (i.e., standard deviations, water levels, etc.)
    hvsr_out = __gethvsrparams(hvsr_out)

    return hvsr_out

#Get an HVSR curve, given an array of x values (freqs), and a dict with psds for three components
def __get_hvsr_curve(x, psd, method=4):
    """ Get an HVSR curve from three components over the same time period/frequency intervals
    -------------------
    Parameters:
        x = x value (frequency or period)
        psd = 3-component dictionary
    --------------------
    Returns:
        hvsr_curve  :   list containing H/V ratios at each frequency/period in x
    """
    hvsr_curve = []
    for j in range(len(x)-1):
        psd0 = [psd['EHZ'][j], psd['EHZ'][j + 1]]
        psd1 = [psd['EHE'][j], psd['EHE'][j + 1]]
        psd2 = [psd['EHN'][j], psd['EHN'][j + 1]]
        f =    [x[j], x[j + 1]]

        hvsr = __get_hvsr(psd0, psd1, psd2, f, use_method=4)
        hvsr_curve.append(hvsr)  

    return hvsr_curve

#Get additional HVSR params for later calcualtions
def __gethvsrparams(hvsr_out):
    count=0
    #SOMETHING VERY WRONG IS GOING ON HERE!!!!
    hvsrp2 = {}
    hvsrm2 = {}
    
    peak_water_level = []
    hvsr_std=[]
    #hvsr_log_std=[]
    peak_water_level_p=[]
    hvsrp2=[]
    hvsrm=[]
    peak_water_level_m=[]
    water_level=1.8 #Make this an input parameter eventually!!!****
    
    count += 1
    hvsr_log_std = {}

    peak_water_level.append(water_level)

    hvsr=hvsr_out['hvsr_curve']
    if hvsr_out['ind_hvsr_curves'].shape[0] > 0:
        hvsrp = np.add(hvsr_out['hvsr_curve'], hvsr_out['ind_hvsr_stdDev'])
        hvsrm = np.subtract(hvsr_out['hvsr_curve'], hvsr_out['ind_hvsr_stdDev'])

        #ppsd_std = hvsr_out['ppsd_std']
        hvsr_log_std = np.std(np.log10(hvsr_out['ind_hvsr_curves']), axis=0)
        hvsrp2 = np.multiply(hvsr, np.exp(hvsr_log_std))
        hvsrm2 = np.divide(hvsr, np.exp(hvsr_log_std))

        peak_water_level_p = water_level + hvsr_out['ind_hvsr_stdDev']
        peak_water_level_m = water_level - hvsr_out['ind_hvsr_stdDev']

    newKeys = ['hvsr_log_std', 'peak_water_level', 'peak_water_level_p', 'peak_water_level_m','hvsrp','hvsrm', 'hvsrp2','hvsrm2']
    newVals = [hvsr_log_std,    peak_water_level,   peak_water_level_p,   peak_water_level_m,  hvsrp,  hvsrm,   hvsrp2,  hvsrm2]
    for i, nk in enumerate(newKeys):
        hvsr_out[nk] = np.array(newVals[i])

    return hvsr_out

#Plot HVSR data
def hvplot(hvsr_dict, kind='HVSR', xtype='freq', **kwargs):
    """Function to plot calculate HVSR data
       ---------------------
       Parameters:
            hvsr_dict   : dict                  Dictionary containing output from process_hvsr function
            kind        : str='HVSR' or list    The kind of plot(s) to plot. If list, will plot all plots listed
                                'HVSR'  : Standard HVSR plot, including standard deviation
                                '[HVSR]c' :HVSR plot with each components' spectra
                                '[HVSR]p' :HVSR plot with picked peaks shown
                                '[HVSR]-s: HVSR plots don't show standard deviation
                                'Specgram': Combined spectrogram of all components
            xtype       : str='freq'    String for what to use between frequency or period
                                            For frequency, the following are accepted (case does not matter): 'f', 'Hz', 'freq', 'frequency'
                                            For period, the following are accepted (case does not matter): 'p', 'T', 's', 'sec', 'second', 'per', 'period'
        --------------------
        Returns:
            fig, ax
        
    """
    freqList = ['F', 'HZ', 'FREQ', 'FREQUENCY']
    perList = 'P', 'T', 'S', 'SEC', 'SECOND' 'PER', 'PERIOD'
    
    if xtype.upper() in freqList:
        xtype='x_freqs'
    elif xtype.upper() in perList:
        xtype='x_period'
    else:
        print('xtype not valid')
        return
    
    if type(kind) is list:
        #iterate through and plot in separate (sub)plots
        pass
    else:
        #Just a single plot
        if 'HVSR' in kind.upper():
            fig, ax = __plot_hvsr(hvsr_dict, kind, xtype, kwargs=kwargs)
        if 'specgram' in kind.lower() or 'spectrogram' in kind.lower():

            fig, ax = __plot_specgram(hvsr_dict, kwargs=kwargs)

    return fig, ax
    
#Plot hvsr curve, private supporting function for hvplot
def __plot_hvsr(hvsr_dict, kind, xtype, **kwargs):
    """Private function for plotting hvsr curve (or curves with components)
    """
    fig, ax = plt.subplots()

    if xtype=='x_freqs':
        xlabel = 'Frequency [Hz]'
    else:
        xlabel = 'Period [s]'
        
    x = hvsr_dict[xtype]
    y = hvsr_dict['hvsr_curve']
    
    for i, k in enumerate(x):
        x[k] = x[k][:-1].copy()
        hvsr_dict['hvsr_std'][k]=hvsr_dict['hvsr_std'][k][:-1].copy()
    
    x = x['EHZ']
    plt.plot(x, y, color='k', label='H/V Ratio', zorder=0)
    if '-s' not in kind.lower():
        sdList = []
        for cSD in hvsr_dict['hvsr_std']:
            sdList.append(hvsr_dict['hvsr_std'][cSD])
        sdArr = np.array(sdList)
        sdArr = np.sqrt(np.mean(sdArr, axis=0)) #This is probably not right
        stArrbelow = np.subtract(y, sdArr)
        stArrabove = np.add(y, sdArr)
        
        plt.fill_between(x, stArrbelow, stArrabove, color='k', alpha=0.1)
    plt.xlabel(xlabel)
    plt.ylabel('H/V Ratio'+'\n['+hvsr_dict['method']+']')
    plt.title(hvsr_dict['site'])
    plt.legend(loc='upper right')
    
    if 'c' in kind.lower():
        if '+c' in kind.lower():
            plt.legend()
            plt.semilogx()
            plt.xlim([0.2,50])
            plt.show()
            fig, ax = plt.subplots()
            axis = ax
            linalpha = 1
            stdalpha = 0.1
        else:
            axis = ax.twinx()
            linalpha = 0.1
            stdalpha = 0.02

        #Plot individual components
        stDev = {}
        stDevVals={}
        y={}
        for k in hvsr_dict['psd_values']:
            y[k] = np.array(hvsr_dict['psd_values'][k])
            y[k] = y[k][:-1]

            stDev[k] = np.std(y[k], axis=0)
            stDevVals[k] = np.array(y[k] - stDev[k])
            stDevVals[k] = np.stack([stDevVals[k], (y[k] + stDev[k])])
            if k == 'EHZ':
                pltColor = 'k'
            elif k =='EHE':
                pltColor = 'b'
            elif k == 'EHN':
                pltColor = 'r'
            
            axis.plot(x, y[k], c=pltColor, label=k, alpha=linalpha)
            axis.fill_between(x, stDevVals[k][0], stDevVals[k][1], color=pltColor, alpha=stdalpha)
            #plt.gca(axis)
            #plt.plot(x_freqs[k], stDevVals[k][0], color='k', alpha=0.5)
            #plt.plot(x_freqs[k], stDevVals[k][1], color='k', alpha=0.5)
        plt.legend(loc='upper left')
    plt.semilogx()
    plt.xlim([0.2,50])
    plt.show()
    
    return fig, ax

#Plot specgtrogram, private supporting function for hvplot
def __plot_specgram(hvsr_dict, **kwargs):
    """Private function for plotting average spectrogram of all three channels from ppsds
    """
    kwargs = kwargs['kwargs']
    ppsds = hvsr_dict['ppsds']
    fig, ax = plt.subplots()
    import matplotlib.dates as mdates

    psdList =[]
    for k in hvsr_dict['psd_raw']:
        psdList.append(hvsr_dict['psd_raw'][k])
    psdArr = np.array(psdList)
    psdArr = np.mean(psdArr, axis=0)
    if 'detrend' in kwargs:
        if kwargs['detrend']:
            psdArr = np.subtract(psdArr, np.median(psdArr, axis=0))
        del kwargs['detrend']

    xmin = datetime.datetime.strptime(min(ppsds['EHZ'].current_times_used).isoformat(), '%Y-%m-%dT%H:%M:%S.%f')
    xmax = datetime.datetime.strptime(max(ppsds['EHZ'].current_times_used).isoformat(), '%Y-%m-%dT%H:%M:%S.%f')
    xmin = mdates.date2num(xmin)
    xmax = mdates.date2num(xmax)

    tTicks = []
    tLabels = []
    for i, t in enumerate(ppsds['EHZ'].current_times_used):
        t1 = datetime.datetime.strptime(t.isoformat(), '%Y-%m-%dT%H:%M:%S.%f')
        tTicks.append(mdates.date2num(t1))
        day = str(t.date)
        if i%10==0:
            tLabels.append(str(t.hour)+':'+str(t.minute))
        else:
            tLabels.append('') 
    extList = [xmin,xmax,min(hvsr_dict['x_freqs']['EHZ']),max(hvsr_dict['x_freqs']['EHZ'])]
    if 'cmap' in kwargs.keys():
        cmap=kwargs['cmap']
    else:
        cmap='viridis'
    print(kwargs)
    im = ax.imshow(psdArr.T, origin='lower', extent=extList,aspect=.005, **kwargs)#,cmap=cmap)
  
    ax = plt.gca()
    fig = plt.gcf()

    FreqTicks = np.arange(1,np.round(max(hvsr_dict['x_freqs']['EHZ']),0), 10)
    plt.xticks(ticks=tTicks, labels=tLabels)
    #plt.yticks(np.round(hvsr_calc['x_freqs']['EHZ'],0))
    plt.yticks(FreqTicks)
    plt.xlabel('Time \n'+day)
    plt.ylabel('Frequency [Hz]')
    plt.semilogy()
    plt.colorbar(mappable=im)
    plt.rcParams['figure.dpi'] = 200
    plt.show()
    return fig, ax

#Get HVSR
def __get_hvsr(_dbz, _db1, _db2, _x, use_method=4):
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
    _pz = __get_power(_dbz, _x)
    _p1 = __get_power(_db1, _x)
    _p2 = __get_power(_db2, _x)

    _hz = math.sqrt(_pz)
    _h1 = math.sqrt(_p1)
    _h2 = math.sqrt(_p2)

    _h = {  2: (_h1 + _h2) / 2.0, 
            3: math.sqrt(_h1 * _h2), 
            4: math.sqrt(_p1 + _p2), 
            5: math.sqrt((_p1 + _p2) / 2.0),
            6: max(_h1, _h2)}

    _hvsr = _h[use_method] / _hz
    return _hvsr

#Remove decibel scaling
def __remove_db(_db_value):
    """convert dB power to power"""
    _values = list()
    for _d in _db_value:
        _values.append(10 ** (float(_d) / 10.0))
    return _values

#For converting dB scaled data to power units
def __get_power(_db, _x):
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
    #print(_db)
    _dx = abs(np.diff(_x)[0])
    #print(_dx)
    _p = np.multiply(np.mean(__remove_db(_db)), _dx)
    #print(_p)
    return _p

#Find peaks in the hvsr ccruve
def __find_peaks(_y):
    """find peaks"""
    _index_list = scipy.signal.argrelextrema(np.array(_y), np.greater)

    return _index_list[0]

#Quality checks, stability tests, clarity tests
def check_peaks(hvsr, x, y, index_list, peak, peakm, peakp, stdf, hvsr_log_std, rank, hvsr_band=[0.4, 40], peak_water_level=1.8, do_rank=False):
    """Function to run tests on HVSR peaks to find best one and see if it passes quality checks
    
    Parameters
    ----------
        hvsr            : dict
            Dictionary containing all the calculated information about the HVSR data (i.e., hvsr_out returned from process_hvsr)
        x               : list-like obj 
            List with x-values (frequency or period values)
        y               : list-like obj 
            List with hvsr curve values ????
        index_list      : list-like obj 
            List with indices of peaks
        hvsr_band       : tuple or list 
            2-item tuple or list with lower and upper limit of frequencies to analyze
        peak_water_level: list-like obj 
            List containing
        do_rank         : bool=False    
            ?????
        peak            : list
            List containing a dictionary for each peak identified in previous step
        peakm           : <generated?>
        peakp           : <generated?>
        stdf            : <generated?>
        hvsr_log_std    : <generated?>
        rank            : <generated?>

    Returns
    -------
        peak            :
        Output file     :

    """
    if not hvsr_band:
        hvsr_band = [0.4,40]

    anyK = list(hvsr['x_freqs'].keys())[0]
    x = hvsr['x_freqs'][anyK]
    y = hvsr['hvsr_curve']
    index_list = hvsr['hvsr_peak_indices']
    peak_water_level  = hvsr['peak_water_level']

    #Do for hvsr
    peak = __init_peaks(x, y, index_list, hvsr_band, peak_water_level)
    peak = __check_clarity(x, y, peak, do_rank=True)


    #Do for hvsrp
    hvsrp = hvsr['hvsrp']
    # Find  the relative extrema of hvsrp (hvsr + 1 standard deviation)
    if not np.isnan(np.sum(hvsrp)):
        index_p = __find_peaks(hvsrp)
    else:
        index_p = list()

    peak_water_level_p  = hvsr['peak_water_level_p']
    peak = __init_peaks(x, hvsrp, index_p, hvsr_band, peak_water_level_p)
    peak = __check_clarity(x, hvsrp, peak, do_rank=False)


    #Do for hvsrm
    hvsrm = hvsr['hvsrm']
    # Find  the relative extrema of hvsrp (hvsr + 1 standard deviation)
    if not np.isnan(np.sum(hvsrm)):
        index_m = __find_peaks(hvsrm)
    else:
        index_m = list()

    peak_water_level_m  = hvsr['peak_water_level_m']

    peak = __init_peaks(x, hvsrm, index_m, hvsr_band, peak_water_level_m)
    peak = __check_clarity(x, hvsrm, peak, do_rank=False)

    hvsr_log_std = hvsr['hvsr_log_std']

    ###########FITURE OUT WHAT HVSRPEAKS IS, RELATIVE TO INDEX_LIST (AND INDEX_LIST??)
    stdf = __get_stdf(x, index_list, hvsrPeaks)

    peak = __check_stability(stdf, peak, hvsr_log_std, rank=True)
    peak = __check_freq_stability(peak, peakm, peakp)

    return peak

#Initialize peaks
def __init_peaks(_x, _y, _index_list, _hvsr_band, _peak_water_level):
    """ Initialize peaks.
        
        Creates dictionary with relevant information and removes peaks in hvsr curve that are not relevant for data analysis (outside HVSR_band)

        Parameters
        ----------
            x               : list-like obj 
                List with x-values (frequency or period values)
            y               : list-like obj 
                List with hvsr curve values ????
            index_list      : list-like obj 
                List with indices of peaks
            _hvsr_band          :
            _peak_water_level   :
        
        Returns
        -------
            _peak               : list of dictionaries, one for each input peak
    """
    _peak = list()
    for _i in _index_list:
        if _y[_i] > _peak_water_level[_i] and (_hvsr_band[0] <= _x[_i] <= _hvsr_band[1]):
            _peak.append({'f0': float(_x[_i]), 'A0': float(_y[_i]), 
                            'f-': None, 'f+': None, 'Sf': None, 'Sa': None,
                          'Score': 0, 'Report': {'A0': '', 'Sf': '', 'Sa': '', 'P+': '', 'P-': ''}})
    return _peak

#Check clarity of peaks
def __check_clarity(_x, _y, _peak, do_rank=False):
    """Check clarity of peak amplitude(s)

       Test peaks for satisfying amplitude clarity conditions as outlined by SESAME 2004:
           - there exist one frequency f-, lying between f0/4 and f0, such that A0 / A(f-) > 2
           - there exist one frequency f+, lying between f0 and 4*f0, such that A0 / A(f+) > 2
           - A0 > 2
        ------------------------
        Parameters:
            x               : list-like obj 
                List with x-values (frequency or period values)
            y               : list-like obj 
                List with hvsr curve values ????
            _peak   :
            do_rank : bool=False
        ------------------------
        Returns:
            peak
    """
    global max_rank

    # Peaks with A0 > 2.
    if do_rank:
        max_rank += 1
    _a0 = 2.0
    for _i in range(len(_peak)):

        if float(_peak[_i]['A0']) > _a0:
            _peak[_i]['Report']['A0'] = '%10.2f > %0.1f %1s' % (_peak[_i]['A0'], _a0, utilities.check_mark())
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
                _peak[_i]['f-'] = '%10.3f %1s' % (_x[_j], utilities.check_mark())
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
                _peak[_i]['f+'] = '%10.3f %1s' % (_x[_j], utilities.check_mark())
                _peak[_i]['Score'] += 1
                break

    return _peak

#Check the stability of the frequency peak
def __check_freq_stability(_peak, _peakm, _peakp):
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
            if _peak[_i]['f0'] * 0.95 <= _peakm[_j]['f0'] <= _peak[_i]['f0'] * 1.05:
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
                        _peakp[_j]['f0'], '%', _peak[_i]['f0'], utilities.check_mark())
                    _peak[_i]['Score'] += 1
                else:
                    _peak[_i]['Report']['P+'] = '%0.3f within ±5%s of %0.3f %1s' % (
                        _peakp[_i]['f0'], '%', _peak[_i]['f0'], ' ')
                break
        if _peak[_i]['Report']['P+'] == '-' and len(_peakp) > 0:
            _peak[_i]['Report']['P+'] = '%0.3f within ±5%s of %0.3f %1s' % (
                _peakp[_i]['f0'], '%', _peak[_i]['f0'], ' ')

    return _peak

#Check stability
def __check_stability(_stdf, _peak, _hvsr_log_std, rank):
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
                                                                            utilities.check_mark())
                _this_peak['Score'] += 1
            else:
                _peak[_i]['Report']['Sf'] = '%10.4f < %0.2f * %0.3f  ' % (_stdf[_i], _e, _this_peak['f0'])

            _t = 0.48
            if _hvsr_log_std[_i] < _t:
                _peak[_i]['Report']['Sa'] = '%10.4f < %0.2f %1s' % (_hvsr_log_std[_i], _t,
                                                                    utilities.check_mark())
                _this_peak['Score'] += 1
            else:
                _peak[_i]['Report']['Sa'] = '%10.4f < %0.2f  ' % (_hvsr_log_std[_i], _t)

        elif 0.2 <= _this_peak['f0'] < 0.5:
            _e = 0.2
            if _stdf[_i] < _e * _this_peak['f0']:
                _peak[_i]['Report']['Sf'] = '%10.4f < %0.2f * %0.3f %1s' % (_stdf[_i], _e, _this_peak['f0'],
                                                                            utilities.check_mark())
                _this_peak['Score'] += 1
            else:
                _peak[_i]['Report']['Sf'] = '%10.4f < %0.2f * %0.3f  ' % (_stdf[_i], _e, _this_peak['f0'])

            _t = 0.40
            if _hvsr_log_std[_i] < _t:
                _peak[_i]['Report']['Sa'] = '%10.4f < %0.2f %1s' % (_hvsr_log_std[_i], _t,
                                                                    utilities.check_mark())
                _this_peak['Score'] += 1
            else:
                _peak[_i]['Report']['Sa'] = '%10.4f < %0.2f  ' % (_hvsr_log_std[_i], _t)

        elif 0.5 <= _this_peak['f0'] < 1.0:
            _e = 0.15
            if _stdf[_i] < _e * _this_peak['f0']:
                _peak[_i]['Report']['Sf'] = '%10.4f < %0.2f * %0.3f %1s' % (_stdf[_i], _e, _this_peak['f0'],
                                                                            utilities.check_mark())
                _this_peak['Score'] += 1
            else:
                _peak[_i]['Report']['Sf'] = '%10.4f < %0.2f * %0.3f  ' % (_stdf[_i], _e, _this_peak['f0'])

            _t = 0.3
            if _hvsr_log_std[_i] < _t:
                _peak[_i]['Report']['Sa'] = '%10.4f < %0.2f %1s' % (_hvsr_log_std[_i], _t, utilities.check_mark())
                _this_peak['Score'] += 1
            else:
                _peak[_i]['Report']['Sa'] = '%10.4f < %0.2f  ' % (_hvsr_log_std[_i], _t)

        elif 1.0 <= _this_peak['f0'] <= 2.0:
            _e = 0.1
            if _stdf[_i] < _e * _this_peak['f0']:
                _peak[_i]['Report']['Sf'] = '%10.4f < %0.2f * %0.3f %1s' % (_stdf[_i], _e, _this_peak['f0'],
                                                                            utilities.check_mark())
                _this_peak['Score'] += 1
            else:
                _peak[_i]['Report']['Sf'] = '%10.4f < %0.2f * %0.3f  ' % (_stdf[_i], _e, _this_peak['f0'])

            _t = 0.25
            if _hvsr_log_std[_i] < _t:
                _peak[_i]['Report']['Sa'] = '%10.4f < %0.2f %1s' % (_hvsr_log_std[_i], _t, utilities.check_mark())
                _this_peak['Score'] += 1
            else:
                _peak[_i]['Report']['Sa'] = '%10.4f < %0.2f  ' % (_hvsr_log_std[_i], _t)

        elif _this_peak['f0'] > 0.2:
            _e = 0.05
            if _stdf[_i] < _e * _this_peak['f0']:
                _peak[_i]['Report']['Sf'] = '%10.4f < %0.2f * %0.3f %1s' % (_stdf[_i], _e, _this_peak['f0'],
                                                                            utilities.check_mark())
                _this_peak['Score'] += 1
            else:
                _peak[_i]['Report']['Sf'] = '%10.4f < %0.2f * %0.3f  ' % (_stdf[_i], _e, _this_peak['f0'])

            _t = 0.2
            if _hvsr_log_std[_i] < _t:
                _peak[_i]['Report']['Sa'] = '%10.4f < %0.2f %1s' % (_hvsr_log_std[_i], _t, utilities.check_mark())
                _this_peak['Score'] += 1
            else:
                _peak[_i]['Report']['Sa'] = '%10.4f < %0.2f  ' % (_hvsr_log_std[_i], _t)
    return _peak

#Get frequency standard deviation
def __get_stdf(x_values, indexList, hvsrPeaks):
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
    return stdf

def printreport(export=True):
    #print statement

    if export:
        pass
        #code to write to output file
    return