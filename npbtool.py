#!/usr/bin/env python

# Wrapper for NAS Parallel Benchmarks under AMDuProfPCM, that allows us to:
# 1. Get split times for initialization vs. main kernel(s) runtime, and thus
# 2. Begin profiling only after initialization is complete.
#
# The script also sets up some environment variables; namely, OMP_NUM_THREADS.
#
# GP-GPU statistics should instead be collected using a combination of NVIDIA
# `nsys` (command-line tool) and NVIDIA Nsight Systems (GUI) viewer. Nsight
# Systems allows us to drag-and-select the main kernel(s) segment on its
# execution timeline, thus ignoring initialization.

import argparse
import os
import subprocess
import sys
import threading
import time
from math import floor

# set the number of OpenMP threads
OMP_NUM_THREADS = 64
# markers to look for in the output text that delimit phases
SPLIT_MARKER = 'Initialization time'
MOP_S_MARKER = 'Mop/s total'
# location of the AMD profiler executable
UPROF_PCM_EXE = '/opt/AMDuProf_4.2-850/bin/AMDuProfPcm'

def do_time(args):
    # set up the environment variable
    env = os.environ.copy()
    env['OMP_NUM_THREADS'] = str(OMP_NUM_THREADS)

    # kick off the benchmark process
    process = subprocess.Popen(args.command, shell=True, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True, env=env)

    start_time = time.time()

    initialization_duration = None
    mop_s = None

    # looks for both SPLIT_MARKER and MOP_S_MARKER
    def tail_output():
        nonlocal initialization_duration, mop_s
        for line in process.stdout:
            print(line, end='')

            if SPLIT_MARKER in line and initialization_duration == None:
                initialization_duration = time.time() - start_time

            if MOP_S_MARKER in line and mop_s == None:
                mop_s = float(line.split()[3])

    thread = threading.Thread(target=tail_output)
    thread.start()

    process.wait()
    end_time = time.time()
    thread.join()

    total_duration = end_time - start_time

    initialization_duration = initialization_duration or 0.0
    runtime_duration = total_duration - initialization_duration

    print('-' * 40)
    print(f"Initialization duration: {initialization_duration:.2f} seconds")
    print(f"Runtime duration: {runtime_duration:.2f} seconds")
    print(f"Total execution duration: {total_duration:.2f} seconds")
    print(f"Mop/s: {mop_s:.2f}")


def do_profile(args):
    # make sure the MSR kernel module is loaded
    try:
        result = subprocess.run(["sudo", "modprobe", "msr"], check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error inserting msr kernel module: {e}")
        sys.exit(1)

    # set up the environment variable
    env = os.environ.copy()
    env['OMP_NUM_THREADS'] = str(OMP_NUM_THREADS)

    # create the profiler output directory and determine the output file path
    os.makedirs('out/', exist_ok=True)
    benchmark_name = os.path.basename(args.command)
    csv_output_path = f'out/{benchmark_name}.csv'

    # kick off the benchmark process
    process = subprocess.Popen(args.command, shell=True, env=env)

    def run_profiler_on(command, init_duration, run_duration, csv_output_path):
        time.sleep(init_duration)

        run_duration_s = int(floor(run_duration))
        profiler_command = [UPROF_PCM_EXE, '-m', 'memory', '-a', '-d', str(run_duration_s),
                '-o', csv_output_path]

        # kick off the profiler process
        subprocess.run(profiler_command)

    thread = threading.Thread(target=run_profiler_on, args=(args.command,
            args.init_duration, args.run_duration, csv_output_path))
    thread.start()

    process.wait()
    thread.join()

    print('-' * 40)
    print(f"Profiling complete; output: {csv_output_path}")


def main():
    parser = argparse.ArgumentParser(
            description="NAS Parallel Benchmarks basic evaluation tool for CPU")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # `time` subcommand
    time_parser = subparsers.add_parser("time",
            help="Time the benchmark execution and output initialization + main runtime splits")
    time_parser.add_argument("-c", "--command", required=True,
            help="The path to the benchmark to run")
    time_parser.set_defaults(func=do_time)

    # `profile` subcommand
    profile_parser = subparsers.add_parser("profile",
            help="Profile the benchmark and record memory bandwidth")
    profile_parser.add_argument("-i", "--init_duration", required=True, type=float,
            help="Duration expected for initialization phase")
    profile_parser.add_argument("-r", "--run_duration", required=True, type=float,
            help="Duration expected for run (main) phase (after initialization phase)")
    profile_parser.add_argument("-c", "--command", required=True,
            help="The path to the benchmark to run")
    profile_parser.set_defaults(func=do_profile)

    args = parser.parse_args()

    if args.command:
        args.func(args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
