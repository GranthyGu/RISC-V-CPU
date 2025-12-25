import os
import shutil

from assassyn.frontend import *
from assassyn.backend import *
from assassyn import utils

from decode_logic import *
from decoder import *
from fetcher import *
from opcodes import *
from ROB import *
from RS import *
from alu import *
from lsq import *

current_path = os.path.dirname(os.path.abspath(__file__))
workspace = f"{current_path}/.workspace/"

class Driver(Module):
    def __init__(self):
        super().__init__(ports={})

    @module.combinational
    def build(self, fetcher: Module):
        init_reg = RegArray(UInt(1), 1, initializer=[1])
        with Condition(init_reg[0] == UInt(1)(1)):
            init_reg[0] = UInt(1)(0)
        with Condition(init_reg[0] == UInt(1)(0)):
            d_call = fetcher.async_called()

def cp_if_exists(src, dst, required):
    if os.path.exists(src):
        shutil.copy(src, dst)
    elif required:
        raise FileNotFoundError(f"File {src} not found")

def init_workspace(base_path, case):
    if os.path.exists(f'{workspace}'):
        shutil.rmtree(f'{workspace}')
    os.mkdir(f'{workspace}')
    cp_if_exists(f'{base_path}/{case}.exe', f'{workspace}/workload.exe', False)
    cp_if_exists(f'{base_path}/{case}.data', f'{workspace}/workload.data', True)
    cp_if_exists(f'{base_path}/{case}.config', f'{workspace}/workload.config', False)

def build_cpu(depth_log: int):
    init_workspace(f"{current_path}/workloads", "vector_multiply")
    with open(f'{workspace}/workload.config') as f:
        raw = f.readline()
        raw = raw.replace('offset:', "'offset':").replace('data_offset:', "'data_offset':")
        offsets = eval(raw)
        value = hex(offsets['data_offset'])
        value = value[1:] if value[0] == '-' else value
        value = value[2:]
        open(f'{workspace}/workload.init', 'w').write(value)

    sys = SysBuilder("Tomasulo-CPU")

    with sys:
        rob_index_array_to_alu = RegArray(Bits(3), 1)
        result_array_to_alu = RegArray(Bits(32), 1)
        pc_result_array_to_alu = RegArray(Bits(32), 1)
        signal_array_to_alu = RegArray(Bits(1), 1)

        rob_index_array_to_lsq = RegArray(Bits(3), 1)
        pc_result_array_to_lsq = RegArray(Bits(32), 1)
        signal_array_to_lsq = RegArray(Bits(1), 1)

        clear_signal_array = RegArray(Bits(1), 1)
        reset_pc_addr = RegArray(Bits(32), 1)

        decode_valid = RegArray(Bits(1), 1)
        rob_full = RegArray(Bits(1), 1)
        rob_full_for_fetcher = RegArray(Bits(1), 1)

        BHT_LOG_SIZE = 6
        BHT_SIZE = 1 << BHT_LOG_SIZE
        
        bht_array = RegArray(Bits(2), BHT_SIZE, initializer=[1] * BHT_SIZE)
        btb_target_array = RegArray(Bits(32), BHT_SIZE, initializer=[0] * BHT_SIZE)

        icache = SRAM(width=32, depth = 1<<depth_log, init_file = f"{workspace}/workload.exe")
        icache.name = "icache"
        
        rob = ROB()
        decoder = Decoder()
        fetcher = Fetcher()
        fetcher_impl = FetcherImpl()
        alu = ALU()
        rs = RS()
        lsq = LSQ()
        dcache = SRAM(width=32, depth = 1<<depth_log, init_file = f"{workspace}/workload.data")
        dcache.name = "dcache"

        rob.build(
            rob_full_array=rob_full,
            rob_full_array_for_fetcher=rob_full_for_fetcher,
            rob_index_array_from_alu = rob_index_array_to_alu,
            result_array_from_alu = result_array_to_alu,
            pc_result_array_from_alu = pc_result_array_to_alu,
            signal_array_from_alu = signal_array_to_alu,
            rob_index_array_from_lsq = rob_index_array_to_lsq,
            result_array_from_lsq = dcache.dout,
            pc_result_array_from_lsq = pc_result_array_to_lsq,
            signal_array_from_lsq = signal_array_to_lsq,
            reset_pc_addr_array = reset_pc_addr,
            rs = rs,
            lsq = lsq,
            clear_signal_array = clear_signal_array,
            bht_array = bht_array,
            btb_target_array = btb_target_array,
            bht_log_size = BHT_LOG_SIZE
        )

        pc_reg, pc_addr = fetcher.build()

        fetch_valid = fetcher_impl.build(
            depth_log = depth_log,
            pc_reg = pc_reg,
            pc_addr = pc_addr,
            decoder = decoder,
            rob_full_array = rob_full,
            decode_valid_array = decode_valid,
            icache = icache,
            clear_signal_array = clear_signal_array,
            reset_pc_addr_array = reset_pc_addr,
            bht_array = bht_array,
            btb_target_array = btb_target_array,
            bht_log_size = BHT_LOG_SIZE
        )

        decoder.build(rob = rob, rdata = icache.dout, rob_full_array = rob_full, decode_valid_array = decode_valid, clear_signal_array = clear_signal_array)

        driver = Driver()
        driver.build(fetcher)

        rs.build(
            alu = alu,
            clear_signal_array = clear_signal_array,
        )
        
        alu.build(
            rob_index_array = rob_index_array_to_alu,
            result_array = result_array_to_alu,
            pc_result_array = pc_result_array_to_alu,
            signal_array = signal_array_to_alu
        )
        
        lsq.build(
            dcache = dcache,
            depth_log = depth_log,
            rob_index_array_ret = rob_index_array_to_lsq,
            pc_result_array = pc_result_array_to_lsq,
            signal_array = signal_array_to_lsq,
            clear_signal_array = clear_signal_array,
        )
    
    print(sys)
    conf = config(
        verilog=utils.has_verilator(),
        sim_threshold=4000,
        idle_threshold=4000,
        resource_base='',
        fifo_depth=1,
    ) 

    simulator_path, verilog_path = elaborate(sys, **conf)

    raw = utils.run_verilator(verilog_path)
    with open(f'{workspace}/verilation.log', 'w') as f:
        f.write(raw)
    print(f"Verilation log saved to {workspace}/verilation.log")

depth_log = 16
if __name__ == "__main__":
    build_cpu(depth_log)