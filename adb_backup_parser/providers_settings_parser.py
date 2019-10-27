'''
    (c) Yogesh Khatri 2019

    License: MIT

    Purpose: Read 'com.android.providers.settings.data' located at 
             <Backup.adb>/apps/com.android.providers.settings/k
    
    Requires: Python 3 and construct 
              Construct can be installed via 'pip install construct' on Windows 
              or 'pip3 install construct' on Linux
    
    Version : 0.1 beta

    Send bugs/comments to yogesh@swiftforensics.com
'''

from construct import *
import csv
import json
import os
import sys
import time
import xml.etree.ElementTree as ET 

NameValue = Struct (
    "name_len" / Int32ub,
    "name" / String(this.name_len, 'utf8'),
    "value_len" / Int32ub,
    "value" / If(this.value_len != 0xFFFFFFFF, String(this.value_len, 'utf8'))
)

NameValue2 = Struct (
    "name_len" / Int16ub,
    "name" / String(this.name_len, 'utf8'),
    "value_len" / Int16ub,
    "value" / If(this.value_len != 0xFFFF, String(this.value_len, 'utf8'))
)

SoftapConfig = Struct (
    "version" / Int32ub,
    "is_ssid_present" / Int8ub,
    "ssid" / If(this.is_ssid_present == 1, PascalString(Int16ub, 'utf8')),
    "ap_band" / Int32ub,
    "ap_channel" / Int32ub,
    "is_psk_present" / Int8ub,
    "psk" / If(this.is_psk_present == 1, PascalString(Int16ub, 'utf8')),
    "allowed_key_mgmt" / Int32ub,
    "is_hidden_ssid" / If(this.version >= 3, Int8ub)
)

#TODO: Network Policy, and old wifi config?

DataHeader = Struct (
    Const(b"Data"),
    "size_key" / Int32ul,
    "size_data" / Int32ul
)

def ReadNameValuePairs(data, logs):
    pos = 0
    size = len(data)
    if size < 4: return
    while pos < (size - 4):
        nv = NameValue.parse(data[pos:])
        logs.append({nv.name : (nv.value if nv.value_len != 0xFFFFFFFF else '')})
        pos += nv.name_len + nv.value_len + 8

def ReadNameValue2Pairs(data, logs):
    pos = 0
    size = len(data)
    if size < 2: return
    while pos < (size - 4):
        nv = NameValue2.parse(data[pos:])
        logs.append({nv.name : (nv.value if nv.value_len != 0xFFFF else '')})
        pos += nv.name_len + nv.value_len + 4

def ReadSoftapConfig(data, logs):
    sc = SoftapConfig.parse(data)
    sc_filtered = {
                    "version" : sc.version,
                    "ssid" : sc.ssid if sc.is_ssid_present else "",
                    "ap_band" : sc.ap_band,
                    "pre_shared_key" : sc.psk if sc.is_psk_present else "",
                    "allowed_key_mgmt" : sc.allowed_key_mgmt
    }
    if sc.version >= 3:
        sc_filtered["is_hidden_ssid"] = sc.is_hidden_ssid
    logs.append(sc_filtered)

def ReadWifiNewConfig(data, logs):
    '''
        Reads the wifi settings xml data
        args:
            data: 
            logs: 
    '''
    tree = ET.fromstring(data.decode('utf8'))
    for network in tree.findall('./NetworkList/Network'): 
        wifi = {}
        for config in network:
            if config.tag == 'WifiConfiguration':
                for string in config.findall('string'):
                    name = string.attrib.get('name', None)
                    if name == 'ConfigKey':
                        parts = string.text[1:].split('"')
                        if len(parts) != 2:
                            print('Problem parsing configKey = {}'.format(string.text))
                            wifi['config_key'] = string.text
                            continue
                        ssid_part = parts[0]
                        security = parts[1]
                        wifi['config_key_ssid'] = ssid_part
                        wifi['config_key_security'] = security
                    elif name in ('PreSharedKey', 'SSID'):
                        val = string.text[1:-1]
                        wifi[name] = val
                    else:
                        wifi[name] = string.text
                for boolean in config.findall('boolean'):
                    name = boolean.attrib.get('name', 'NONAME')
                    value = boolean.attrib.get('value', '')
                    wifi[name] = value
            elif config.tag == 'IpConfiguration':
                for string in config.findall('string'):
                    name = string.attrib.get('name', None)
                    if name:
                        wifi[name] = string.text
        logs.append(wifi)
        

def WriteCsv(path, list_of_dicts):
    '''
        Write contents of a list out to a csv file
        args:
            list_of_dicts: [{}, {}, {}]
            out_file_csv: csv file
    '''
    # Get column names from dictionary
    out_file_csv = OpenFileForWriting(path)
    if (out_file_csv == None): return
    d = list_of_dicts[0]
    columns = [col for col in d]

    writer = csv.DictWriter(out_file_csv, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL, fieldnames=columns)
    writer.writeheader()
    writer.writerows(list_of_dicts)
    out_file_csv.close()

def WriteJson(path, list_of_dicts, dataset_name):
    '''
        Write contents of a list out to a json file
        args:
            list_of_dicts: [{}, {}, {}]
            out_file_json: json file
    '''
    out_file_json = OpenFileForWriting(path)
    if (out_file_json == None): return    
    data = { dataset_name : list_of_dicts }
    json.dump(data, out_file_json)
    out_file_json.close()

def OpenFileForWriting(path):
    try:
        out_file = open(path, 'w')
        return out_file
    except OSError as ex:
        print("Error: Could not create file '{}' for writing, error was: ".format(path) + str(ex))
    return None

def WriteOutput(data_type, data, output_folder):
    if data:
        out_file_path_json = os.path.join(output_folder, data_type.replace(' ', '_') + ".json")
        WriteJson(out_file_path_json, data, data_type)
        print("Wrote {} items to ".format(len(data)) + out_file_path_json)
    else:
        print("No {} found".format(data_type))

def main():
    usage = "Parser for 'com.android.providers.settings.data' "\
            "which includes wifi settings with passwords"\
            "\n--------------------------------------------"\
            "\nUsage: providers_settings_parser.py input_file output_folder"\
            "\nExample: providers_settings_parser.py  com.android.providers.settings.data  c:\output_folder\\"\
            "\n\nOutput is in CSV and JSON formats"\
            "\nNote: All times in output are UTC"\
            "\nSend bugs/comments to yogesh@swiftforensics.com"

    argc = len(sys.argv)
    if argc < 3:
        print("Error: Insufficient arguments..")
        print(usage)
        return

    input_path = sys.argv[1]
    output_path = sys.argv[2]

    try:
        if os.path.exists(input_path):
            if os.path.isdir(output_path): # Check output path provided
                pass
            else: # Either path does not exist or it is a file
                if os.path.isfile(output_path):
                    print("Error: There is already a file existing by that name. Cannot create folder : " + output_path)
                    return
                try:
                    os.makedirs(output_path)
                except OSError as ex:
                    print("Error: Cannot create output file : " + output_path + "\nError Details: " + str(ex))
                    return
            # Actual processing starts here
            try:
                system_settings = []
                secure_settings = []
                global_settings = []
                locale = ''
                lock_settings = []
                softap_config = []
                network_policies = []
                wifi_settings = []
                print("Trying to read file " + input_path)
                with open (input_path, "rb") as f:
                    file_data = f.read(12)
                    while file_data:
                        if len(file_data) != 12:
                            print('Error, read less than 12 bytes from file, expected full Data header!')
                            break
                        data_meta = DataHeader.parse(file_data)
                        key = f.read(data_meta.size_key + 1).decode('utf8').rstrip('\x00')
                        if f.tell() % 4: f.seek(4 - (f.tell() % 4), 1) # Align to 4 byte boundary
                        #print ("Reading Key =", key)
                        if data_meta.size_data != 0xFFFFFFFF:
                            data = f.read(data_meta.size_data)
                            #print (data)
                            if key == 'system': ReadNameValuePairs(data, system_settings)
                            elif key == 'secure': ReadNameValuePairs(data, secure_settings)
                            elif key == 'global': ReadNameValuePairs(data, global_settings)
                            elif key == 'locale': locale = data.decode('utf8')
                            elif key == 'lock_settings': ReadNameValue2Pairs(data, lock_settings)
                            elif key == 'softap_config': ReadSoftapConfig(data, softap_config)
                            elif key == 'network_policies': pass
                            elif key == 'wifi_new_config': ReadWifiNewConfig(data, wifi_settings)
                        
                        if f.tell() % 4: f.seek(4 - (f.tell() % 4), 1) # Align to 4 byte boundary
                        # Read next header
                        file_data = f.read(12)
                    # Done processing, now write it out

                    if locale:
                        print('Locale is ' + locale)
                    WriteOutput('system settings', system_settings, output_path)
                    WriteOutput('secure settings', secure_settings, output_path)
                    WriteOutput('global settings', global_settings, output_path)
                    WriteOutput('lock settings', lock_settings, output_path)
                    WriteOutput('softap settings', softap_config, output_path)
                    WriteOutput('wifi settings', wifi_settings, output_path)

            except OSError as ex:
                print("Error: Cannot read input file : " + input_path + "\nError Details: " + str(ex))
                return
        else:
            print("Error: Failed to find file at specified path. Path was : " + input_path)
    except OSError as ex:
        print("Error: Unknown exception, error details are: " + str(ex))

if __name__ == '__main__':
    main()
