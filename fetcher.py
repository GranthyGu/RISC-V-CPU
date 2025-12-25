from assassyn.frontend import *
from decoder import *

class Fetcher(Module):

    def __init__(self):
        super().__init__(ports = {}, no_arbiter=True)
        self.name = "F"

    @module.combinational
    def build(self):
        pc_reg = RegArray(Bits(32), 1)
        addr = pc_reg[0]
        return pc_reg, addr

class FetcherImpl(Downstream):

    def __init__(self):
        super().__init__()
        self.name = "FI"

    @downstream.combinational
    def build(
        self,
        depth_log: int,
        pc_reg: Value,
        pc_addr: Value,
        decoder: Decoder,
        rob_full_array: Array,
        decode_valid_array: Array,
        icache: SRAM,
        clear_signal_array: Array,
        reset_pc_addr_array: Array,
        bht_array: Array,
        btb_target_array: Array,
        bht_log_size: int
    ):
        local_pc_addr = pc_addr.bitcast(Bits(32))

        bht_index = local_pc_addr[2 : 2 + bht_log_size].bitcast(Bits(6))
        current_state = bht_array[bht_index]
        should_branch = current_state[1:1] 
        predicted_target = btb_target_array[bht_index]

        next_seq_pc = (local_pc_addr.bitcast(Int(32)) + Int(32)(4)).bitcast(Bits(32))
        next_pc_pred = should_branch.select(predicted_target, next_seq_pc)

        clear = clear_signal_array[0]
        fetch_valid = (~rob_full_array[0]) & (~clear)

        log("fetch_valid : {} | addr: 0x{:05x} | pred_taken: {} | next_pc: 0x{:05x}", 
            fetch_valid, local_pc_addr, should_branch, next_pc_pred)

        decoder.async_called(
            receive = fetch_valid, 
            fetch_addr = local_pc_addr,
            predicted_taken = should_branch
        )
        
        with Condition(fetch_valid & (~clear)):
            pc_reg[0] = next_pc_pred
        with Condition(~fetch_valid & (~clear)):
            pc_reg[0] = pc_reg[0]

        with Condition(clear):
            pc_reg[0] = reset_pc_addr_array[0]

        icache.build(Bits(1)(0), fetch_valid, local_pc_addr[2:2+depth_log - 1].bitcast(Int(depth_log)), Bits(32)(0))
        return fetch_valid