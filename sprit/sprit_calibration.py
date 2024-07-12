"""
This module will be used for calibration of the ambient HVSR data acquired near wells 
to derive a relation between the resonant frequency and the depth to bedrock beneath the subsurface.

"""
import numpy as np
import pandas as pd
import os
import re
import pathlib
import pkg_resources
import matplotlib.pyplot as plt
from warnings import warn
#from pyproj import GeoPandas    #need conda environment
try:  # For distribution
    from sprit import sprit_hvsr
except Exception:  # For testing
    import sprit_hvsr

"""
Attempt 1: Regression equations: 

Load the calibration data as a CSV file. Read in the frequency and the depth to bedrock. 
Use array structures to organize data. The depth should be the independent variable so probably 
the predictor and the frequency is the dependent variable so the response variable. 

Two approaches- either use the power law  y=ax^b 
or find the least squares solution using the matrix-vector multiplication. 

Use GeoPandas to eliminate outliers

calibrate - does calibration
view_results - produces Pandas dataframe of results
view_plot - produces calibration curve


Things to add:
- #checkinstance - HVSRData/HVSR Batch
- #need try-catch blocks while reading in files and checking membership
- # eliminate outlier points - will have to read in latitude and longitude from spreadsheet and then compare against that of well to find distance in meters 
- #pick only relevant points according to bedrock_type (lithology)
- #Add calibration equation to get_report csv
- #Add parameter to sprit.run
"""

resource_dir = pathlib.Path(pkg_resources.resource_filename(__name__, 'resources/'))
sample_data_dir = resource_dir.joinpath("sample_data")
sampleFileName = {'sample_1': sample_data_dir.joinpath("SampleHVSRSite1_2024-06-13_1633-1705.csv")}

models = ["ISGS_All", "ISGS_North", "ISGS_Central", "ISGS_Southeast", "ISGS_Southwest", 
                    "ISGS_North_Central", "ISGS_SW_SE", "Minnesota_All", 
                    "Minnesota_Twin_Cities", "Minnesota_South_Central", 
                    "Minnesota_River_Valleys", "Rhine_Graben",
                    "Ibsvon_A", "Ibsvon_B","Delgado_A", "Delgado_B", 
                    "Parolai", "Hinzen", "Birgoren", "Ozalaybey", "Harutoonian",
                    "Fairchild", "DelMonaco", "Tun", "Thabet_A", "Thabet_B",
                    "Thabet_C", "Thabet_D"]

swave = ["shear", "swave", "shearwave", "rayleigh","rayleighwave", "vs"]

model_list = list(map(lambda x : x.casefold(), models))

model_parameters = {"ISGS_All" : (141.81,1.582), "ISGS_North" : (142.95,1.312), "ISGS_Central" : (119.17, 1.21), "ISGS_Southeast" : (67.973,1.166), 
                    "ISGS_Southwest": (61.238,1.003), "ISGS_North_Central" : (117.44, 1.095), "ISGS_SW_SE" : (62.62, 1.039),
                    "Minnesota_All" : (121, 1.323), "Minnesota_Twin_Cities" : (129, 1.295), "Minnesota_South_Central" : (135, 1.248),
                    "Minnesota_River_Valleys" : (83, 1.232), "Rhine_Graben" : (96, 1.388), 
                    "Ibsvon_A" : (96, 1.388), "Ibsvon_B" : (146, 1.375), "Delgado_A" : (55.11, 1.256), 
                    "Delgado_B" : (55.64, 1.268), "Parolai" : (108, 1.551), "Hinzen" : (137, 1.19), "Birgoren" : (150.99, 1.153), 
                    "Ozalaybey" : (141, 1.270), "Harutoonian" : (73, 1.170), "Fairchild" : (90.53, 1), "DelMonaco" : (53.461, 1.01), 
                    "Tun" : (136, 1.357), "Thabet_A": (117.13, 1.197), "Thabet_B":(105.14, 0.899), "Thabet_C":(132.67, 1.084), "Thabet_D":(116.62, 1.169)}
def round_depth(num, ndigits = 3):
    """
    Rounds a float to the specified number of decimal places.
    num: the value to round
    ndigits: the number of digits to round to
    """
    if ndigits == 0:
        return int(num + 0.5)
    else:
        digit_value = 10 ** ndigits
        return int(num * digit_value + 0.5) / digit_value

def calculate_depth(freq_input = {sprit_hvsr.HVSRData, sprit_hvsr.HVSRBatch, float, os.PathLike},  
                    model = "ISGS_All",
                    site = "HVSRSite", 
                    unit = "m",
                    freq_col = "PeakFrequency", 
                    calculate_elevation = False, 
                    elevation_col = "Elevation", 
                    depth_col = "BedrockDepth", 
                    verbose = False,    #if verbose is True, display warnings otherwise not
                    export_path = None,
                    Vs = 563.0,
                    decimal_places = 3, 
                    **kwargs):
    
    a = 0
    b = 0
    params = None

    #Fetching model parameters
    try:
        if isinstance(model,(tuple, list, dict)):  
            (a,b) = model  
            if b >= a:                     #b should always be less than a
                if verbose:
                    warn("Second parameter greater than the first, inverting values")
                (b,a) = model
            elif a == 0 or b == 0:         
                raise ValueError("Parameters cannot be zero, check model inputs")

        elif isinstance(model, str): 

            if model.casefold() in model_list:
                
                for k,v in model_parameters.items():

                    if model.casefold() == k.casefold():   
                        (a, b) = model_parameters[k]
                        break

            elif model.casefold() in swave:
                params = model.casefold()

            elif model.casefold() == "all":
                params = model.casefold()

            else:   #parameters a and b could be passed in as a parsable string
                params = [int(s) for s in re.findall(r"[-+]?(?:\d*\.*\d+)", model)]  #figure this out later for floating points; works for integers
                (a,b) = params
                if a == 0 or b == 0:         
                    raise ValueError("Parameters cannot be zero, check model inputs")
                elif b >= a:                     #b should always be less than a
                    if verbose:
                        warn("Second parameter greater than the first, inverting values")
                    (b,a) = params
                
    except Exception:
        if (a,b) == (0, 0):

            raise ValueError( "Model not found: check inputs")

    #Checking if freq_input is a filepath
    try:
        if os.path.exists(freq_input):
            data = pd.read_csv(freq_input,
                                skipinitialspace= True,
                                index_col=False,
                                on_bad_lines= "error")

            pf_values= data[freq_col].values

            calib_data = np.array((pf_values, np.ones(len(pf_values))))

            calib_data = calib_data.T

                
            for each in range(calib_data.shape[0]):
                try:
                    if params in swave:
                        calib_data[each, 1] = Vs/(4*calib_data[each, 0])
                    elif params == "all":
                        print("do something")
                    else:
                        calib_data[each, 1] = a*(calib_data[each, 0]**-b), decimal_places
                except Exception:
                    raise ValueError("Error in calculating depth, check file for empty values or missing columns")

                
            if unit.casefold() in {"ft", "feet"}:
                depth_col = depth_col + "_ft"
                data[depth_col] = round_depth(calib_data[:, 1]*3.281, decimal_places)
            else:
                depth_col = depth_col + "_m"   
                data[depth_col] = round_depth(calib_data[:, 1], decimal_places)
            

            if export_path is not None and os.path.exists(export_path):
                if export_path == freq_input:
                    data.to_csv(freq_input)
                    if verbose:
                        print("Saving data in the original file")

                else:
                    if "/" in export_path:
                        temp = os.path.join(export_path+ "/"+ site + ".csv")
                        data.to_csv(temp)
                    
                    else:
                        temp = os.path.join(export_path+"\\"+ site + ".csv")
                        data.to_csv(temp)

                    if verbose:
                        print("Saving data to the path specified")
                        
            plt.plot(data[freq_col], data[depth_col])
            return data
    except Exception:
        if verbose:
            print("freq_input not a filepath, checking other types")
        
    
    #Checking if freq_input is HVSRData object
    try:
        if isinstance(freq_input, sprit_hvsr.HVSRData):
            try:
                data = freq_input.CSV_Report
            except Exception:
                warn("Passed HVSRData Object has no attribute CSV_Report")
                data = sprit_hvsr.get_report(freq_input,report_format = 'csv')
            
            pf_values= data[freq_col].values

            calib_data = np.array((pf_values, np.ones(len(pf_values))))

            calib_data = calib_data.T

                
            for each in range(calib_data.shape[0]):

                try:
                    if params in swave:
                        calib_data[each, 1] = Vs/(4*calib_data[each, 0])
                    elif params == "all":
                        print("do something")
                    else:
                        calib_data[each, 1] = a*(calib_data[each, 0]**-b), decimal_places
                except Exception:
                    raise ValueError("Error in calculating depth, check HVSRData object for empty values or missing columns")
            
            if unit.casefold() in {"ft", "feet"}:
                depth_col = depth_col + "_ft"
                data[depth_col] = round_depth(calib_data[:, 1]*3.281, decimal_places)

            else:
                depth_col = depth_col + "_m"
                data[depth_col +"_m"] = round_depth(calib_data[:, 1], decimal_places)
            

            if export_path is not None and os.path.exists(export_path):
                if export_path == freq_input:
                    data.to_csv(freq_input)
                    if verbose:
                        print("Saving data in the original file")

                else:
                    if "/" in export_path:
                        temp = os.path.join(export_path+ "/"+ site + ".csv")
                        data.to_csv(temp)
                    
                    else:
                        temp = os.path.join(export_path+"\\"+ site + ".csv")
                        data.to_csv(temp)

                    if verbose:
                        print("Saving data to the path specified")
                
            freq_input.CSV_Report = data
            return freq_input.CSV_Report
        
    except Exception: 
        if verbose:
            print("freq_input not an HVSRData object, checking other types")

    try:
        if isinstance(freq_input, float):
            print("Did i get here?")
            data = sprit_hvsr.HVSRData(params = {"PeakFrequency":freq_input})
            return data.CSV_Report

























    except:
        print("Sorry, I failed here")




        
        





















    




















def calibrate(calib_filepath, calib_type = "power",outlier_radius = None, bedrock_type = None,peak_freq_col = "PeakFrequency",
              bed_depth_col = "Bedrock_Depth", **kwargs):    

    calib_data = None

    calib_types = ["Power", "Vs", "Matrix"]

    calib_type_list = list(map(lambda x : x.casefold(), calib_types))
    
    power_list = ["Power", "power", "pw", "POWER"]

    Vs_list = ["vs", "VS", "v_s", "V_s", "V_S"]

    matrix_list = ["matrix", "Matrix", "MATRIX"]

    
    bedrock_types = ["shale", "limetone", "dolomite", 
                     "sedimentary", "igneous", "metamorphic"]
    
   
    

    freq_columns_names = ["PeakFrequency", "ResonanceFrequency", "peak_freq", "res_freq", "Peakfrequency", "Resonancefrequency", "PF", "RF", "pf", "rf"]

    bedrock_depth_names = ["BedrockDepth", "DepthToBedrock", "bedrock_depth", "depth_bedrock", "depthtobedrock", "bedrockdepth"]

    # if calib_type.casefold() in calib_type_list: 
        
       
    #     if calib_type.casefold() in power_list:









    








                         

                           
                           
                        
                  













































