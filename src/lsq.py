from assassyn.frontend import *
from instruction import *
from utils import *

LSQ_SIZE = 8

class LSQ(Module):

    def __init__(self):
        super().__init__(ports={
            "lsq_write": Port(Bits(1)),
            "lsq_modify_recorder": Port(Bits(1)),
            "rob_index": Port(Bits(3)),
            "signals": Port(decoder_signals),
            "rs1_value": Port(Bits(32)),
            "rs1_recorder": Port(Bits(3)),
            "rs1_has_recorder": Port(Bits(1)),
            "rs2_value": Port(Bits(32)),
            "rs2_recorder": Port(Bits(3)),
            "rs2_has_recorder": Port(Bits(1)),
            "addr": Port(Bits(32)),
            "lsq_modify_rd": Port(Bits(5)),
            "lsq_recorder": Port(Bits(3)),
            "lsq_modify_value": Port(Bits(32)),
            "rob_head_index": Port(Bits(3)),        
            })
        self.name = "LSQ"

    @module.combinational
    def build(
        self, 
        dcache: SRAM,
        depth_log: int,
        rob_index_array_ret: Array,
        pc_result_array: Array,
        signal_array: Array,
        clear_signal_array: Array,
        memory_place_array: Array,
    ):
        # This is a sequential execution module for handling load/store instructions.

        # Store the head pointer of LSQ.
        head = RegArray(Int(32), 1, initializer=[0])
        # Store the tail pointer of LSQ.
        tail = RegArray(Int(32), 1, initializer=[0])
        # Store the current number of instructions in LSQ.
        lsq_size = RegArray(Int(32), 1)
        # Store whether LSQ is full.
        lsq_full = Bits(1)(0)
        # Whether this entry in LSQ has an allocated instruction.
        allocated_array = [RegArray(Bits(1), 1) for _ in range(LSQ_SIZE)]

        # Store the index of the corresponding ROB entry.
        rob_index_array = RegArray(Bits(3), LSQ_SIZE)
        # Whether it is a load instruction.
        is_load_array = RegArray(Bits(1), LSQ_SIZE)
        # Whether it is a store instruction.
        is_store_array = RegArray(Bits(1), LSQ_SIZE)
        # Store the register number of rs1.
        rs1_array = RegArray(Bits(5), LSQ_SIZE)
        # Store the value of rs1.
        rs1_value_array = [RegArray(Bits(32), 1) for _ in range(LSQ_SIZE)]
        # Whether the instruction has rs1.
        has_rs1_array = RegArray(Bits(1), LSQ_SIZE)
        # Store the recorder of rs1.
        rs1_recorder_array = RegArray(Bits(3), LSQ_SIZE)
        # Whether rs1 has a recorder.
        has_rs1_recorder_array = [RegArray(Bits(1), 1) for _ in range(LSQ_SIZE)]
        # Store the register number of rs2.
        rs2_array = RegArray(Bits(5), LSQ_SIZE)
        # Store the value of rs2.
        rs2_value_array = [RegArray(Bits(32), 1) for _ in range(LSQ_SIZE)]
        # Whether the instruction has rs2.
        has_rs2_array = RegArray(Bits(1), LSQ_SIZE)
        # Store the recorder of rs2.
        rs2_recorder_array = RegArray(Bits(3), LSQ_SIZE)
        # Whether rs2 has a recorder.
        has_rs2_recorder_array = [RegArray(Bits(1), 1) for _ in range(LSQ_SIZE)]
        # Store the immediate value imm.
        imm_array = RegArray(Bits(32), LSQ_SIZE)
        # Store the calculated address.
        addr_array = RegArray(Bits(32), LSQ_SIZE)
        # Whether this entry is ready.
        ready_array = [RegArray(Bits(1), 1) for _ in range(LSQ_SIZE)]

        (
            lsq_write,
            lsq_modify_recorder,
            rob_index,
            signals,
            rs1_value,
            rs1_recorder,
            rs1_has_recorder,
            rs2_value,
            rs2_recorder,
            rs2_has_recorder,
            addr,
            lsq_modify_rd,
            lsq_recorder,
            lsq_modify_value,
            rob_head_index
        ) = self.pop_all_ports(True)

        rs1_coincidence = rs1_has_recorder & (rs1_recorder == lsq_recorder) & lsq_modify_recorder
        rs1_has_recorder = rs1_coincidence.select(Bits(1)(0), rs1_has_recorder)
        rs1_value = rs1_coincidence.select(lsq_modify_value, rs1_value)

        rs2_coincidence = rs2_has_recorder & (rs2_recorder == lsq_recorder) & lsq_modify_recorder
        rs2_has_recorder = rs2_coincidence.select(Bits(1)(0), rs2_has_recorder)
        rs2_value = rs2_coincidence.select(lsq_modify_value, rs2_value)

        with Condition(lsq_write & (~clear_signal_array[0])):
            log("rob_index: {} | rs1_value: 0x{:08x} | rs1_recorder: {} | rs1_has_recorder: {} | rs2_value: 0x{:08x} | rs2_recorder: {} | rs2_has_recorder: {} | addr: 0x{:08x}",
                rob_index, rs1_value, rs1_recorder, rs1_has_recorder, rs2_value, rs2_recorder, rs2_has_recorder, addr)


        lsq_write = lsq_write & (~clear_signal_array[0])
        lsq_modify_recorder = lsq_modify_recorder & (~clear_signal_array[0])

        head_ptr = head[0]
        tail_ptr = tail[0]
        
        head_idx = head_ptr.bitcast(Bits(32))[0:2]
        tail_idx = tail_ptr.bitcast(Bits(32))[0:2]

        updated_tail_ptr = tail_ptr + Int(32)(1)
        updated_tail_ptr = (updated_tail_ptr == Int(32)(LSQ_SIZE)).select(Int(32)(0), updated_tail_ptr)
        updated_lsq_size = lsq_size[0] + Int(32)(1)

        lsq_full = (updated_lsq_size == Int(32)(LSQ_SIZE)).select(Bits(1)(1), Bits(1)(0))

        write_valid = lsq_write & ~lsq_full
        with Condition(lsq_write & ~lsq_full):
            log("LSQ entry {} allocated", tail_ptr)
            write1hot(allocated_array, tail_idx, Bits(1)(1))
            rob_index_array[tail_idx] = rob_index
            is_load_array[tail_idx] = signals.memory[0:0]
            is_store_array[tail_idx] = signals.memory[1:1]
            imm_array[tail_idx] = signals.imm
            rs1_array[tail_idx] = signals.rs1
            write1hot(rs1_value_array, tail_idx, rs1_value, width = 3)
            has_rs1_array[tail_idx] = signals.rs1_valid
            rs1_recorder_array[tail_idx] = rs1_recorder
            write1hot(has_rs1_recorder_array, tail_idx, rs1_has_recorder, width = 3)
            rs2_array[tail_idx] = signals.rs2
            write1hot(rs2_value_array, tail_idx, rs2_value, width = 3)
            has_rs2_array[tail_idx] = signals.rs2_valid
            rs2_recorder_array[tail_idx] = rs2_recorder
            write1hot(has_rs2_recorder_array, tail_idx, rs2_has_recorder, width = 3)
            
            write1hot(ready_array, tail_idx, ~((signals.rs1_valid & rs1_has_recorder) | (signals.rs2_valid & rs2_has_recorder)), width = 3)
            addr_array[tail_idx] = addr
            tail[0] = updated_tail_ptr
        
        # Check if the entry pointed by head is ready to execute.
        dcache_we = Bits(1)(0)
        dcache_re = Bits(1)(0)
        dcache_addr = Bits(depth_log)(0).bitcast(UInt(depth_log))
        dcache_wdata = Bits(32)(0)

        alu_a = read_mux(rs1_value_array, head_idx, LSQ_SIZE, 32)
        alu_b = imm_array[head_idx]
        alu_result = (alu_a.bitcast(Int(32)) + alu_b.bitcast(Int(32))).bitcast(Bits(32))

        is_memory_read = is_load_array[head_idx]
        is_memory_write = is_store_array[head_idx]
        request_addr = alu_result[2:2+depth_log-1].bitcast(UInt(depth_log))

        dcache_we = is_memory_write
        dcache_re = is_memory_read
        dcache_addr = request_addr
        # load_byte requires determining which byte to load.
        memory_place_array[0] = alu_result.bitcast(Bits(32))[0:1]
        dcache_wdata = read_mux(rs2_value_array, head_idx, LSQ_SIZE, 32)

        is_store = is_store_array[head_idx]
        rob_idx_of_head = rob_index_array[head_idx]
        can_execute_store = (rob_idx_of_head == rob_head_index)
        condition_met = (~is_store) | (is_store & can_execute_store)

        execute_valid = read_mux(allocated_array, head_idx, LSQ_SIZE, 1) & read_mux(ready_array, head_idx, LSQ_SIZE, 1) & (~clear_signal_array[0]) & condition_met
        log("head_idx: {} | allocated: {} | ready: {}", head_idx, read_mux(allocated_array, head_idx, LSQ_SIZE, 1), read_mux(ready_array, head_idx, LSQ_SIZE, 1))
        with Condition(execute_valid):
            # Execute the entry pointed by head.
            log("LSQ entry {} executed", head_ptr)

            write1hot(allocated_array, head_idx, Bits(1)(0))
            head[0] = (head_ptr + Int(32)(1) == Int(32)(LSQ_SIZE)).select(Int(32)(0), head_ptr + Int(32)(1))
        dcache.build(we = dcache_we & execute_valid, re = dcache_re & execute_valid, addr = dcache_addr, wdata = dcache_wdata)

        with Condition(lsq_modify_recorder):
            for i in range(LSQ_SIZE):
                modify_rs1_recorder = allocated_array[i][0] & has_rs1_recorder_array[i][0] & (rs1_recorder_array[i] == lsq_recorder)
                modify_rs2_recorder = allocated_array[i][0] & has_rs2_recorder_array[i][0] & (rs2_recorder_array[i] == lsq_recorder)
                with Condition(modify_rs1_recorder):
                    has_rs1_recorder_array[i][0] = Bits(1)(0)
                    rs1_value_array[i][0] = lsq_modify_value
                with Condition(modify_rs2_recorder):
                    has_rs2_recorder_array[i][0] = Bits(1)(0)
                    rs2_value_array[i][0] = lsq_modify_value
                
                with Condition(~(write_valid & (tail_ptr == Int(32)(i)))):
                    ready_array[i][0] = ~((has_rs1_array[i] & (has_rs1_recorder_array[i][0] & (~modify_rs1_recorder))) | 
                                                        (has_rs2_array[i] & (has_rs2_recorder_array[i][0] & (~modify_rs2_recorder))))
                
        with Condition(clear_signal_array[0]):
            head[0] = Int(32)(0)
            tail[0] = Int(32)(0)
            lsq_size[0] = Int(32)(0)
            for i in range(LSQ_SIZE):
                allocated_array[i][0] = Bits(1)(0)

        rob_index_array_ret[0] = rob_index_array[head_idx]
        pc_result_array[0] = (addr_array[head_idx].bitcast(Int(32)) + Int(32)(4)).bitcast(Bits(32))
        signal_array[0] = execute_valid.select(Bits(1)(1), Bits(1)(0))
        
        with Condition(~clear_signal_array[0]):
            lsq_size[0] = lsq_size[0] + write_valid.select(Int(32)(1), Int(32)(0)) - execute_valid.select(Int(32)(1), Int(32)(0))