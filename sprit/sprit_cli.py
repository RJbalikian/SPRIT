"""This module/script is used to run sprit from the command line. 

The arguments here should correspond to any of the keyword arguments that can be used with sprit.run()
"""

import argparse
import inspect
import sprit  # Assuming you have a module named 'sprit'

def get_param_docstring(func, param_name):
    function_docstring = func.__doc__

    # Search for the parameter's docstring within the function's docstring
    param_docstring = None
    if function_docstring:
        param_start = function_docstring.find(f'{param_name} :')
        param_start = param_start + len(f'{param_name} :')
        if param_start != -1:
            param_end_line1 = function_docstring.find('\n', param_start + 1)
            param_end = function_docstring.find('\n', param_end_line1 + 1)
            if param_end != -1:
                param_docstring = function_docstring[param_start:param_end].strip()
    
    if param_docstring is None:
        param_docstring = ''
    return param_docstring

def main():
    parser = argparse.ArgumentParser(description='CLI for SPRIT HVSR package (specifically the sprit.run() function)')
    
    hvsrFunctions = [sprit.input_params,
                     sprit.fetch_data,
                     sprit.remove_noise,
                     sprit.generate_ppsds,
                     sprit.process_hvsr,
                     sprit.check_peaks,
                     sprit.get_report,
                     sprit.hvplot]

    parameters = []

    for f in hvsrFunctions:
        parameters.append(inspect.signature(f).parameters)

    intermediate_params_list = ['params']

    paramNamesList = []
    for i, param in enumerate(parameters):
        for name, parameter in param.items():
            # Add arguments and options here
            if name not in paramNamesList and name not in intermediate_params_list:
                paramNamesList.append(name)
                curr_doc_str = get_param_docstring(func=hvsrFunctions[i], param_name=name)
                if name == 'datapath':
                    parser.add_argument(F'--{name}',  required=True, help=f'{curr_doc_str}', default=parameter.default)
                elif name == 'verbose':
                    parser.add_argument('-V', F'--verbose',  action='store_true', help=f'Print status and results to terminal.', default=parameter.default)
                else:
                    helpStr = f'Keyword argument {name} in function sprit.{hvsrFunctions[i].__name__}(). default={parameter.default}.\n\t{curr_doc_str}'
                    print(helpStr)
                    parser.add_argument(F'--{name}', help=helpStr, default=parameter.default)
    # Add more arguments/options as needed
    
    args = parser.parse_args()

    kwargs = {}
    
    #MAKE THIS A LOOP!!!
    # Map command-line arguments/options to kwargs
    for arg_name, arg_value in vars(args).items():
        if arg_value is None:
            pass
            print(f"{arg_name}={arg_value}")
        else:
            print(f"{arg_name}={arg_value}")

    # Call the sprit.run function with the generated kwargs
    sprit.run(**kwargs)

if __name__ == '__main__':
    main()
