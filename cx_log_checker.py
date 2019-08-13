# Author: Simon Song
# cx_log_checker.py: This script will unzip Checkmarx log file and perform quick sanity check
# Usage: python cx_log_checker.py --file checkmarx_log.zip

import zipfile
import sys
import fnmatch
import getopt
import re
import os
import shutil
from pathlib import Path

#--------------------------------------------------------------------------
# Key strings to search from the log
SOURCE_SINK = "Query - "
FIND_DB = "Find_DB_In"
FIND_INPUT = "Find_Interactive_Inputs"
FIND_OUTPUT = "Find_Interactive_Outputs"
TARGET_ZIP_FILE_PATTERN = 'Scan_*.zip'
SUMMARY_PAGE = "---------------------------General Queries Summary------------------------------Status-----------Results-----------Duration-------------Wait Block----Blocked-----InternalDur-----DeltaDur---Count---DeltaStart-----DeltaEnd"
LOC_SUMMARY = "Total files              	"
EX_PATH = "EXCLUDE_PATH"
AVAIL_MEM = "Available memory: 0"
EXCLUDED_FILE_STR = "Number of exclude file"
#---------------------------------------------------------------------------

# Move Zip file to target directory
def move_file(target_file, target_dir, debug):
    if debug:
        print("Moving file...")
        print("Target File: ")
        print(target_file)
        print("Target Directory: ")
        print(target_dir)
    try:
        shutil.move(target_file, target_dir)
    except OSError as err:
        if debug:
            print("[Warning] File already exists")

# Print output
def printer(str, target_dir, output_filename):
    if (str is not None) and (target_dir is not None):
        output_path = Path(target_dir)
        output_path = output_path / output_filename
        print(str)
        with open(output_path, 'a') as file:
            file.write(str + '\n')

# Read log file and print sanity check result
def run_sanity_check(file, target_dir, target_file, debug):
    out_of_ram = False
    save_line = False
    exclude_path = None
    num_excluded_file = None
    c = 100
    output = []
    summary = []
    output_filename = target_file[:-4] + ".log"
    with open(file, 'r') as file:
        for line in file:
            if AVAIL_MEM in line:
                out_of_ram = True
			# This should always show up at very last
            elif SUMMARY_PAGE in line:
                save_line = True
			# This should show up in the middle of the log
            elif LOC_SUMMARY in line:
                c = 0
            elif EX_PATH in line:
                exclude_path = line.replace('\t', '').replace('\n', '')
            elif EXCLUDED_FILE_STR in line:
                cline = line.replace('\t', '').replace('\n', '')
                num_excluded_file = cline.split('-')[1]

            if c < 9:
                if c == 8:
                    coverage_line = line.replace('\t', '').replace('\n', '').replace('%', '')
                    coverage_percentage = float(coverage_line.split(":")[1])
                    if (coverage_percentage - 93.00) < 0:
                        coverage_line = "[WARNING] " + coverage_line + "%"
                        summary.append(coverage_line)
                    else:
                        coverage_line = "[OK] " + coverage_line + "%"
                        summary.append(coverage_line)
                else:
                    summary.append(line.replace('\t', '').replace('\n', ''))

            if save_line:
                output.append(line.replace('\t', '').replace('\n', ''))
                if FIND_DB in line or FIND_INPUT in line or FIND_OUTPUT in line:
                    cline = line.replace('\t', '').replace('\n', '')
                    cline = re.sub("\s\s+", ' ', cline)
                    cline = cline.split(" ")
                    count = cline[2]
                    result = cline[1]
                    if (int(count) == 0) or (result != "success"):
                        summary.append("[WARNING] " + cline[0] + " " + result + " " + count)
                    else:
                        summary.append("[OK] " + cline[0] + " " + result + " " + count)
            c = c + 1
    if debug:
        for ele in output:
            print(ele)

    printer("===============Log Sanity Check result===============", target_dir, output_filename)
    if len(summary) < 2:
        printer("[Error] Scan may not have finished, please review the log manually", target_dir, output_filename)
    for ele in summary:
        printer(ele, target_dir, output_filename)
    if out_of_ram:
        printer("[WARNING] Available memory: 0", target_dir, output_filename)
    printer(num_excluded_file[1:], target_dir, output_filename)
    printer(exclude_path, target_dir, output_filename)
    save_folder = Path(target_dir) / target_file
    move_file(target_file, target_dir, debug)

# Unzip zip files
def unzip_files(target_file, target_dir, debug):
    extracted_path = None
    log_file = None
    zip_file = Path(target_dir) / target_file
    if debug:
        print("======================")
        print("Unzipping files...")
        print("Target file:")
        print(target_file)
        print("Target directory:")
        print(target_dir)
        print("Current working directory:")
        print(os.getcwd())
    with zipfile.ZipFile(target_file, "r") as zipref:
        zipref.extractall(target_dir)

    for root, dirs, files in os.walk(target_dir):
        for filename in fnmatch.filter(files, TARGET_ZIP_FILE_PATTERN):
            zipfile.ZipFile(os.path.join(root, filename)).extractall(os.path.join(root, os.path.splitext(filename)[0]))
            extracted_path = os.path.join(root, os.path.splitext(filename)[0])

    for root, dir, files in os.walk(extracted_path):
        log_file = files[0]
    log_file_path = Path(extracted_path) / log_file
    return log_file_path

# Wrapper function to unzip log file
def unzip_log(target_file, target_dir, debug):
    if debug:
        print("Target Directory")
        print(target_dir)
        print("Target file name")
        print(target_file)
    if target_dir is None:
        current_path = os.getcwd()
        target_dir = Path(current_path) / "processed_log" / target_file[:-4]
        if debug:
            print("Attempting to create project folder")
            print(target_dir)
        try:
            os.mkdir(target_dir)
            if debug:
                print("Proccessed log directory not found, creating directory...")
                print("Target directory: ")
                print(target_dir)
        except FileExistsError:
            if debug:
                print("[Warning] Directory already exists. Skipping directory creation...")
    target_dir = Path(target_dir) / target_file[:-4]
    if debug:
        print(target_dir)
        print(target_file)
    log_file_path = unzip_files(target_file, target_dir, debug)
    return log_file_path, target_dir

# Main function
def main():
    all_file = False
    debug = False
    target_file = None
    target_dir = None
    options, remainder = getopt.getopt(sys.argv[1:], 'ft:ad', ['file=', 'targetdir=', 'debug'])
    for opt, arg in options:
        if opt in '-a':
            all_file = True
        elif opt in ('-f', '--file'):
            target_file = arg
        elif opt in ('-t', '--targetdir'):
            target_dir = arg
        elif opt in ('-d', '--debug'):
            debug = True
            print("[Info] Debug enabled")
    if debug:
        print("Argument - TARGET FILE:")
        print(target_file)
        print("Argument - TARGET DIR:")
        print(target_dir)
        print("Argument all file:")
        print(all_file)
        print("=============")
    log_file_path, target_dir = unzip_log(target_file, target_dir, debug)
    run_sanity_check(log_file_path, target_dir, target_file, debug)

if __name__ == '__main__':
    main()
