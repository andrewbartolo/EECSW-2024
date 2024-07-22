#!/usr/bin/env python
import csv
from copy import deepcopy
from scipy.stats import hmean

# Computes and summarizes statistics from the supplied CSV file.

# CSV header (for reference):
# BENCHMARK,CLASS,ARCH,INIT_TIME,RUN_TIME,OPS_MOPS_S,MEM_BW_RD_GB_S,MEM_BW_WR_GB_S,
CSV_FILEPATH = './data.csv'

# used for computing energy breakdowns
power_w = {
    'cpu': 250,
    'gpu': 250,
}

mem_energy_pj_bit = {
    'cpu': 22,
    'gpu': 5.9,
}


def do_individual():
    # keep running arrays of values so we can take the h-mean at the end
    inner = {
        'g_ops_s': [],
        'mem_bw_gib_s': [],
        'bytes_op': [],
        'nj_op': [],
        'cmp_power_w': [],
        'mem_power_w': [],
    }
    data = {
        'cpu': deepcopy(inner),
        'gpu': deepcopy(inner),
    }

    with open(CSV_FILEPATH, 'r') as f:
        reader = csv.DictReader(f)

        print(f"{'-'*25} per-benchmark {'-'*25}")

        for row in reader:
            benchmark = row['BENCHMARK']
            benchmark_class = row['CLASS']
            arch = row['ARCH']

            m_ops_s = float(row['OPS_MOPS_S'])
            g_ops_s = m_ops_s / 1e3

            mem_bw_rd_bytes_s = float(row['MEM_BW_RD_GB_S']) * 1e9
            mem_bw_wr_bytes_s = float(row['MEM_BW_WR_GB_S']) * 1e9
            mem_bw_bytes_s = mem_bw_rd_bytes_s + mem_bw_wr_bytes_s
            mem_bw_gib_s = mem_bw_bytes_s / 1024**3

            mem_bw_bits_s = mem_bw_bytes_s * 8
            mem_power_w = mem_bw_bits_s * mem_energy_pj_bit[arch] * 1e-12
            cmp_power_w = power_w[arch] - mem_power_w

            ops_s = m_ops_s * 1e6

            bytes_op = mem_bw_bytes_s / ops_s

            power_nj_s = power_w[arch] * 1e9
            nj_op = power_nj_s / ops_s

            data[arch]['g_ops_s'].append(g_ops_s)
            data[arch]['mem_bw_gib_s'].append(mem_bw_gib_s)
            data[arch]['bytes_op'] .append(bytes_op)
            data[arch]['nj_op'] .append(nj_op)
            data[arch]['cmp_power_w'].append(cmp_power_w)
            data[arch]['mem_power_w'].append(mem_power_w)

            print(f"[{arch}] {benchmark}.{benchmark_class}: "
                    f"{g_ops_s:.2f} G ops/s "
                    f"| {mem_bw_gib_s:.2f} GiB/s "
                    f"| {bytes_op:.2f} bytes/op "
                    f"| {nj_op:.2f} nJ/op"
                    f"| {cmp_power_w:.2f} W (compute) "
                    f"| {mem_power_w:.2f} W (memory) "
            )

    return data


def do_hmeans(data):
    print(f"{'-'*25} h-means {'-'*25}")

    for arch in ['cpu', 'gpu']:
        for col, vals in data[arch].items():
            if 'power' in col: continue

            m = hmean(vals)
            print(f"[{arch}] {col}: {m:.2f}")


def do_avg_power(data):
    print(f"{'-'*25} avg. power {'-'*25}")

    for arch in ['cpu', 'gpu']:
        avg_cmp_power_w = sum(data[arch]['cmp_power_w']) / len(data[arch]['cmp_power_w'])
        avg_mem_power_w = power_w[arch] - avg_cmp_power_w
        pct_mem_power = (avg_mem_power_w / power_w[arch]) * 100.0

        print(f"[{arch}] avg. cmp. power = {avg_cmp_power_w:.2f};",
                f"avg. mem. power = {avg_mem_power_w:.2f} ",
                f"({pct_mem_power:.2f}%)")


def main():
    data = do_individual()
    do_hmeans(data)
    do_avg_power(data)


if __name__ == '__main__':
    main()
