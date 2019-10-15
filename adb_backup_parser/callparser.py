'''
    (c) Yogesh Khatri 2019

    License: MIT

    Purpose: Read 'com.android.calllogbackup.data' located at 
             <Backup.adb>/apps/com.android.calllogbackup/k
    
    Requires: Python 3 and construct 
              Construct can be installed via 'pip install construct' on Windows 
              or 'pip3 install construct' on Linux
    
    Version : 0.1 beta

    Send bugs/comments to yogesh@swiftforensics.com
'''

from construct import *
import csv
import datetime
import json
import os
import sys
import time

def ReadUnixMsTime(unix_time_ms): # Unix millisecond timestamp
    '''Returns datetime object, or empty string upon error'''
    if unix_time_ms not in ( 0, None, ''):
        try:
            if isinstance(unix_time_ms, str):
                unix_time_ms = float(unix_time_ms)
            return datetime.datetime(1970, 1, 1) + datetime.timedelta(seconds=unix_time_ms/1000)
        except (ValueError, OverflowError, TypeError) as ex:
            #print("ReadUnixMsTime() Failed to convert timestamp from value " + str(unix_time_ms) + " Error was: " + str(ex))
            pass
    return ''

def GetCallTypeString(call_type):
    '''
        Returns the string for call type
    '''
    ret = ""
    if   call_type == 1 : ret = "Incoming"
    elif call_type == 2 : ret = "Outgoing"
    elif call_type == 3 : ret = "Missed"
    elif call_type == 4 : ret = "Voicemail"
    elif call_type == 5 : ret = "Rejected"
    elif call_type == 6 : ret = "Blocked"
    elif call_type == 7 : ret = "Answered_Externally"
    else:
        ret = "UNKNOWN ({})".format(call_type)
    return ret

def GetBlockReasonString(reason):
    '''
        Returns the string for call block reason given a reason code
    '''
    ret = ""
    if   reason == 0 : ret = ""
    elif reason == 1 : ret = "Screening service"
    elif reason == 2 : ret = "Direct to voicemail"
    elif reason == 3 : ret = "Blocked number"
    elif reason == 4 : ret = "Unknown number"
    elif reason == 5 : ret = "Restricted number"
    elif reason == 6 : ret = "Payphone"
    elif reason == 7 : ret = "Not in contacts"
    else:
        ret = "UNKNOWN ({})".format(reason)
    return ret

def GetPresentationString(pr):
    '''
        Returns the string for number presentation given presentation code
    '''
    ret = ""
    if   pr == 1 : ret = "Allowed"
    elif pr == 2 : ret = "Restricted"
    elif pr == 3 : ret = "Unknown"
    elif pr == 4 : ret = "Payphone"
    else:
        ret = "UNKNOWN ({})".format(pr)
    return ret

CallRecord = Struct(
    "version" / Int32ub, #  1007 (0x03ef) or 1005 seen
    "timestamp" / Int64sb,
    "duration_in_sec" / Int64ub,
    "is_num_present" / Int8ub,
    "number" / If(this.is_num_present == 1, PascalString(Int16ub, 'utf8')),
    "type" / Int32ub,
    "presentation" / Int32ub,
    "is_servicename_present" / Int8ub,
    "servicename" / If(this.is_servicename_present == 1, PascalString(Int16ub, 'utf8')),
    "is_iccid_present" / Int8ub,
    "iccid" / If(this.is_iccid_present == 1, PascalString(Int16ub, 'utf8')),
    "is_own_num_present" / Int8ub,
    "own_number" / If(this.is_own_num_present == 1, PascalString(Int16ub, 'utf8')),
    "unknown3" / Byte[12],
    "oem" / PascalString(Int16ub, 'utf8'),
    "unknown4" / Int32ub[2],
    "unknown5" / If(this.version == 1007, Byte[10]),
    "block_reason" / If(this.version == 1007, Int32ub)
)

DataHeader = Struct (
    Const(b"Data"),
    "size_key" / Int32ul,
    "size_data" / Int32ul
)

def GetDuration(duration_in_sec):
    '''Convert call duration into HH:MM:SS format'''
    return time.strftime('%H:%M:%S', time.gmtime(duration_in_sec))

def ParseCallLogData(key, data, call_logs):
    '''
        Reads the call log Data structure for a single call log record

        args:
            key: utf8 string, which is the serial number
            data: buffer holding single call log data
            call_logs: list to which this function will add a dict
    '''
    cr = CallRecord.parse(data)
    #print(ReadUnixMsTime(cr.timestamp), GetDuration(cr.duration_in_sec), cr.number, cr.own_number, cr.iccid, GetCallTypeString(cr.type))
    cr_filtered = { 
                    "serial_number" : key,
                    "version" : cr.version,
                    "timestamp" : str(ReadUnixMsTime(cr.timestamp)),
                    "duration" : GetDuration(cr.duration_in_sec),
                    "number" : cr.number if cr.is_num_present else '',
                    "type" : GetCallTypeString(cr.type),
                    "presentation" : GetPresentationString(cr.presentation),
                    "iccid" : cr.iccid if cr.is_iccid_present else '',
                    "own_number" : cr.own_number if cr.is_own_num_present else '',
                    "block_reason" : GetBlockReasonString(cr.block_reason) if cr.version == 1007 else ''
                    }
    call_logs.append(cr_filtered)

def WriteCsv(list_of_dicts, out_file_csv):
    '''
        Write contents of a list out to a csv file
        args:
            list_of_dicts: [{}, {}, {}]
            out_file_csv: csv file
    '''
    # Get column names from dictionary
    d = list_of_dicts[0]
    columns = [col for col in d]

    writer = csv.DictWriter(out_file_csv, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL, fieldnames=columns)
    writer.writeheader()
    writer.writerows(list_of_dicts)

def WriteJson(list_of_dicts, out_file_json):
    '''
        Write contents of a list out to a json file
        args:
            list_of_dicts: [{}, {}, {}]
            out_file_json: json file
    '''
    data = { 'call_logs' : list_of_dicts }
    json.dump(data, out_file_json)


def main():
    usage = "Parser for 'com.android.calllogbackup.data'"\
            "\n--------------------------------------------"\
            "\nUsage: callparser.py input_file output_folder"\
            "\nExample: callparser.py  com.android.calllogbackup.data  c:\output_folder\\"\
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
    call_logs = []
    out_file_path_csv = ""
    out_file_path_json = ""
    out_file_csv = None
    out_file_json = None

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
            out_file_path_csv = os.path.join(output_path, "call_logs.csv")
            out_file_path_json = os.path.join(output_path, "call_logs.json")
            try:
                out_file_csv = open(out_file_path_csv, 'w')
                out_file_json = open(out_file_path_json, 'w')
            except OSError as ex:
                print("Error: Could not create output file, error was: " + str(ex))
                return

            # Actual processing starts here
            try:
                print("Trying to read file " + input_path)
                with open (input_path, "rb") as f:
                    file_data = f.read(12)
                    while file_data:
                        if len(file_data) != 12:
                            print('Error, read less than 12 bytes from file, expected full Data header!')
                            break
                        data_meta = DataHeader.parse(file_data)
                        key = f.read(data_meta.size_key).decode('utf8')
                        if f.tell() % 4: f.seek(4 - (f.tell() % 4), 1) # Align to 4 byte boundary
                        #print ("Reading Key =", key)
                        if data_meta.size_data != 0xFFFFFFFF:
                            data = f.read(data_meta.size_data)
                            #print (data)
                            ParseCallLogData(key, data, call_logs)
                        
                        if f.tell() % 4: f.seek(4 - (f.tell() % 4), 1) # Align to 4 byte boundary
                        # Read next header
                        file_data = f.read(12)
                    # Done processing, now write it out
                    if call_logs:
                        WriteCsv(call_logs, out_file_csv)
                        print("Wrote out " + out_file_path_csv)
                        WriteJson(call_logs, out_file_json)
                        print("Wrote out " + out_file_path_json)
                    else:
                        print("No items found in input file, nothing to write out!")

            except OSError as ex:
                print("Error: Cannot read input file : " + input_path + "\nError Details: " + str(ex))
                return
        else:
            print("Error: Failed to find file at specified path. Path was : " + input_path)
    except OSError as ex:
        print("Error: Unknown exception, error details are: " + str(ex))    
    
    if out_file_csv:
        out_file_csv.close()
    if out_file_json:
        out_file_json.close()

if __name__ == '__main__':
    main()
