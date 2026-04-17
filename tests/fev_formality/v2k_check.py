####################################################################################################
####################################################################################################
#
#                                                                     
#
#
####################################################################################################


import json
import sys
import os
import re

def read_json_file(file_path):
    try:
        with open(file_path, 'r') as file:
            data = json.load(file)
            return data
    except FileNotFoundError:
        print("The file was not found.")
    except json.JSONDecodeError:
        print("Error decoding JSON.")
    except Exception as e:
        print(f"An error occurred: {e}")

def create_custom_dictionary(json_data):
    custom_dict = {}
    # Process the main module
    main_module = json_data['design']['module']
    custom_dict[main_module['name']] = {
        'library': main_module['library'],
        'fileName': main_module['fileName']
    }
    
    # Process instances
    for instance in json_data['instances']:
        key = instance['name']
        key = key.replace('\\', '')
        value = {
            'library': instance['module']['library'],
            'fileName': instance['module']['fileName']
        }
        custom_dict[key] = value
    
    return custom_dict

def process_cfg_cv(cfg_file_path):
    try:
        with open(cfg_file_path, 'r') as file:
            cfg_content = file.readlines()
    except FileNotFoundError:
        print("The file does not exist.")
        sys.exit(1)
    
    cfg_dict = {}
    pattern = r'instance\s+(\S+).*?liblist\s+(\S+)'
    
    for line in cfg_content:
        #replace "  ." with "."
        pttrn = r'\s+\.'
        line = re.sub(pttrn, '.', line)
        match = re.search(pattern, line)
        if match:
            #replace all backslash
            instance_word = match.group(1).replace('\\', '')
            #remove semi colon after lib name
            liblist_word = match.group(2).replace(';', '')
            cfg_dict[instance_word] = liblist_word
        else:
            print('Pattern not found in line:', line)
    
    return cfg_dict

def main(file_path, cfg_file_path, v2k_report_path):

    json_data = read_json_file(file_path)
    cfg_data = process_cfg_cv(cfg_file_path)

    if json_data:
        json_dict = create_custom_dictionary(json_data)

    if not cfg_data or not json_dict:
        print ('Please contact DA')
        sys.exit(1)

    set_cfg = set(cfg_data.keys())
    set_json = set(json_dict.keys())

    common_set = set_cfg.intersection(set_json)
    cfg_only = set_cfg.difference(set_json)
    json_only = set_json.difference(set_cfg)

    try:
        with open(v2k_report_path, 'w') as file:
            for inst in common_set:
                if json_dict[inst]['library'].lower() == cfg_data[inst].lower():
                    file.write(f'-MATCH- {inst} FM report: {json_dict[inst]["library"]} cfg_report: {cfg_data[inst]}\n')
                else:
                    file.write(f'-ERROR- -MISMATCH- {inst} FM report: {json_dict[inst]["library"]} cfg_report: {cfg_data[inst]}\n')
            
            for inst in cfg_only:
                file.write(f'-CFG ONLY- {inst} {cfg_data[inst]}\n')
            
            for inst in json_only:
                file.write(f'-FEV ONLY- {inst} {json_dict[inst]["library"]}\n')
    except IOError as e:
        # Handle the error (e.g., file not found, permission denied, etc.)
        print(f"Failed to open or write to the file: {e}")
    except Exception as e:
        # Handle other possible exceptions
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":

    if len(sys.argv) < 2:
        print("Usage: python script.py argument1 argument2 ...")
        sys.exit(1)
        # Exit the script with an error code

    # Print all arguments
    print("Script name:", sys.argv[0])
        
    file_path = sys.argv[1]
    cfg_file_path = sys.argv[2]
    v2k_report_path = sys.argv[3]
    
    main(file_path,cfg_file_path,v2k_report_path)


