from assassyn.frontend import *
from instruction import *
from RS import *
from lsq import *
from opcodes import *
from utils import *

ROB_SIZE = 8

class ROB(Module):

    def __init__(self):
        super().__init__(ports = {
            "receive": Port(Bits(1)),
            "signals": Port(decoder_signals),
            "addr": Port(Bits(32)),
            "predicted_taken": Port(Bits(1)),
            "pred_next_pc": Port(Bits(32))
        }, no_arbiter = True)
        self.name = "ROB"

    @module.combinational
    def build(
        self, 
        rob_full_array: Array, 
        rob_full_array_for_fetcher: Array,
        rob_index_array_from_alu: Array,
        result_array_from_alu: Array,
        pc_result_array_from_alu: Array,
        signal_array_from_alu: Array,
        rob_index_array_from_mul_alu: Array,
        result_array_from_mul_alu: Array,
        pc_result_array_from_mul_alu: Array,
        signal_array_from_mul_alu: Array,
        rob_index_array_from_lsq: Array,
        result_array_from_lsq: Array,
        pc_result_array_from_lsq: Array,
        signal_array_from_lsq: Array,
        memory_place_array: Array,
        clear_signal_array: Array,
        reset_pc_addr_array: Array,
        rs: RS,
        lsq: LSQ,
        bht_array: Array,
        btb_target_array: Array,
        bht_log_size: int
    ):
        rf_value_array = RegArray(Bits(32), 32)
        rf_recorder_array = RegArray(Bits(3), 32)
        rf_has_recorder_array = [RegArray(Bits(1), 1) for _ in range(32)]

        allocated_array = [RegArray(Bits(1), 1) for _ in range(ROB_SIZE)]
        ready_array = [RegArray(Bits(1), 1) for _ in range(ROB_SIZE)]
        head = RegArray(Int(32), 1, initializer = [0])
        tail = RegArray(Int(32), 1, initializer = [0])
        rob_size = RegArray(Int(32), 1, initializer = [0])
        rob_full = Bits(1)(0)
        rob_empty = Bits(1)(0)

        is_final_array = RegArray(Bits(1), ROB_SIZE)
        is_reg_write_array = RegArray(Bits(1), ROB_SIZE)
        is_memory_write_array = RegArray(Bits(1), ROB_SIZE)
        is_branch_array = RegArray(Bits(1), ROB_SIZE)
        is_load_or_store_array = RegArray(Bits(1), ROB_SIZE)
        is_mult_array = RegArray(Bits(1), ROB_SIZE)
        predicted_taken_array = RegArray(Bits(1), ROB_SIZE)
        pred_next_pc_array = RegArray(Bits(32), ROB_SIZE)

        rd_array = RegArray(Bits(5), ROB_SIZE)
        rd_valid_array = RegArray(Bits(1), ROB_SIZE)
        rs1_array = RegArray(Bits(5), ROB_SIZE)
        rs2_array = RegArray(Bits(5), ROB_SIZE)
        imm_array = RegArray(Bits(32), ROB_SIZE)
        mul_result_array = RegArray(Bits(32), ROB_SIZE)
        calc_result_array = RegArray(Bits(32), ROB_SIZE)
        load_result_array = RegArray(Bits(32), ROB_SIZE)
        memory_length_array = RegArray(Bits(2), ROB_SIZE)
        pc_result_array = [RegArray(Bits(32), 1) for _ in range(ROB_SIZE)]
        addr_array = RegArray(Bits(32), ROB_SIZE)

        rob_phys_full = (rob_size[0] >= Int(32)(ROB_SIZE))
        rob_empty = (rob_size[0] == Int(32)(0))

        receive, signals, addr, predicted_taken, pred_next_pc = self.pop_all_ports(True)
        rd = signals.rd
        has_rd = signals.rd_valid
        rs1 = signals.rs1
        has_rs1 = signals.rs1_valid
        rs2 = signals.rs2
        has_rs2 = signals.rs2_valid
        imm = signals.imm
        has_imm = signals.imm_valid
        is_branch = signals.is_branch
        is_reg_write = signals.is_reg_write
        is_memory_write = signals.is_memory_write
        is_load_or_store = signals.is_load_or_store
        is_final = (signals.alu == Bits(RV32I_ALU.CNT)(1 << RV32I_ALU.ALU_NONE))

        head_ptr = head[0]
        tail_ptr = tail[0]
        head_idx = head_ptr.bitcast(Bits(32))[0:2]
        tail_idx = tail_ptr.bitcast(Bits(32))[0:2]

        updated_tail_ptr = tail_ptr + Int(32)(1)
        updated_tail_ptr = (updated_tail_ptr == Int(32)(ROB_SIZE)).select(Int(32)(0), updated_tail_ptr)
        updated_head_ptr = head_ptr + Int(32)(1)
        updated_head_ptr = (updated_head_ptr == Int(32)(ROB_SIZE)).select(Int(32)(0), updated_head_ptr)
        
        commit = ~rob_empty & read_mux(ready_array, head_idx, ROB_SIZE, 1)
        
        pc_seq = (addr_array[head_idx].bitcast(Int(32)) + Int(32)(4)).bitcast(Bits(32))
        pc_result_val = read_mux(pc_result_array, head_idx, ROB_SIZE, 32)
        actual_taken = (pc_result_val != pc_seq)
        pred_taken_stored = predicted_taken_array[head_idx]
        pred_next_pc_stored = pred_next_pc_array[head_idx]
        
        is_misprediction = commit & (pc_result_val != pred_next_pc_stored)
        
        has_unresolved_branch = Bits(1)(0)
        for i in range(ROB_SIZE):
            has_unresolved_branch = has_unresolved_branch | (allocated_array[i][0] & is_branch_array[i])
        stall_for_store = has_unresolved_branch & is_memory_write
        should_receive = ~rob_phys_full & receive & (~clear_signal_array[0])

        with Condition(should_receive & ~is_misprediction):
            rd_valid_array[tail_idx] = has_rd
            predicted_taken_array[tail_idx] = predicted_taken
            pred_next_pc_array[tail_idx] = pred_next_pc

        with Condition(should_receive & ~is_misprediction & has_rd):
            rd_array[tail_idx] = rd
        with Condition(should_receive & ~is_misprediction & has_rs1):
            rs1_array[tail_idx] = rs1
        with Condition(should_receive & ~is_misprediction & has_rs2):
            rs2_array[tail_idx] = rs2
        with Condition(should_receive & ~is_misprediction & has_imm):
            imm_array[tail_idx] = imm

        modify_recorder = ~rob_empty & read_mux(ready_array, head_idx, ROB_SIZE, 1) & rd_valid_array[head_idx]
        rs_modify_recorder = modify_recorder
        lsq_modify_recorder = modify_recorder
        modify_value = is_load_or_store_array[head_idx].select(load_result_array[head_idx], calc_result_array[head_idx])
        modify_value = is_mult_array[head_idx].select(mul_result_array[head_idx], modify_value)

        rs_write = should_receive & ~is_misprediction & (~is_load_or_store)
        lsq_write = should_receive & ~is_misprediction & is_load_or_store

        with Condition(should_receive & ~is_misprediction):
            is_branch_array[tail_idx] = is_branch
            is_memory_write_array[tail_idx] = is_memory_write
            is_reg_write_array[tail_idx] = is_reg_write
            addr_array[tail_idx] = addr
            is_load_or_store_array[tail_idx] = is_load_or_store
            is_mult_array[tail_idx] = signals.is_mult
            memory_length_array[tail_idx] = signals.memory_length
            write1hot(ready_array, tail_idx, Bits(1)(0))
            is_final_array[tail_idx] = is_final

        rob_index_from_alu = rob_index_array_from_alu[0]
        write_result_from_alu = signal_array_from_alu[0]
        write_result_from_alu = write_result_from_alu & read_mux(allocated_array, rob_index_from_alu[0:2], ROB_SIZE, 1)
        with Condition(write_result_from_alu):
            calc_result_array[rob_index_from_alu[0:2]] = result_array_from_alu[0]
            write1hot(pc_result_array, rob_index_from_alu[0:2], pc_result_array_from_alu[0], width = 3)
            write1hot(ready_array, rob_index_from_alu[0:2], Bits(1)(1), width = 3)

        rob_index_from_mul_alu = rob_index_array_from_mul_alu[0]
        write_result_from_mul_alu = signal_array_from_mul_alu[0]
        write_result_from_mul_alu = write_result_from_mul_alu & read_mux(allocated_array, rob_index_from_mul_alu[0:2], ROB_SIZE, 1)
        with Condition(write_result_from_mul_alu):
            mul_result_array[rob_index_from_mul_alu[0:2]] = result_array_from_mul_alu[0]
            write1hot(pc_result_array, rob_index_from_mul_alu[0:2], pc_result_array_from_mul_alu[0], width = 3)
            write1hot(ready_array, rob_index_from_mul_alu[0:2], Bits(1)(1), width = 3)
        
        rob_index_from_lsq = rob_index_array_from_lsq[0]
        write_signal_from_lsq = signal_array_from_lsq[0]
        write_result_from_lsq = write_signal_from_lsq & read_mux(allocated_array, rob_index_from_lsq[0:2], ROB_SIZE, 1)
        load_byte = (memory_length_array[rob_index_from_lsq[0:2]] == Bits(2)(0))
        result_byte = Bits(8)(0)
        result_byte = (memory_place_array[0] == Bits(2)(0)).select(result_array_from_lsq[0][0:7], result_byte)
        result_byte = (memory_place_array[0] == Bits(2)(1)).select(result_array_from_lsq[0][8:15], result_byte)
        result_byte = (memory_place_array[0] == Bits(2)(2)).select(result_array_from_lsq[0][16:23], result_byte)
        result_byte = (memory_place_array[0] == Bits(2)(3)).select(result_array_from_lsq[0][24:31], result_byte)
        with Condition(write_result_from_lsq):
            load_result_array[rob_index_from_lsq[0:2]] = load_byte.select(concat(Bits(24)(0), result_byte), result_array_from_lsq[0].bitcast(Bits(32)))
            write1hot(pc_result_array, rob_index_from_lsq[0:2], pc_result_array_from_lsq[0], width = 3)
            write1hot(ready_array, rob_index_from_lsq[0:2], Bits(1)(1), width = 3)

        modify_rd = rd_valid_array[head_idx].select(rd_array[head_idx], Bits(5)(0))
        recorder = head_ptr
        receive_write = should_receive & ~is_misprediction & has_rd
        commit_write = modify_recorder & (modify_rd != Bits(5)(0)) & \
                       read_mux(rf_has_recorder_array, modify_rd, 32, 1) & \
                       (rf_recorder_array[modify_rd] == recorder.bitcast(Bits(5)))
        conflict = receive_write & commit_write & (rd == modify_rd)

        with Condition(receive_write & (rd != Bits(5)(0))):
             write1hot(rf_has_recorder_array, rd, Bits(1)(1))
             rf_recorder_array[rd] = tail_idx.bitcast(Bits(3))
        with Condition(commit_write & ~conflict & ~is_misprediction):
             write1hot(rf_has_recorder_array, modify_rd, Bits(1)(0))
        with Condition(modify_recorder & (modify_rd != Bits(5)(0))):
            rf_value_array[modify_rd] = modify_value
    
        with Condition(commit):
            log("ROB entry {} committed, addr: 0x{:08x}", head_ptr, addr_array[head_idx])

        bht_idx = addr_array[head_idx][2 : 2+bht_log_size - 1].bitcast(Bits(6))
        old_state = bht_array[bht_idx]
        
        with Condition(commit & is_branch_array[head_idx]):
            state_uint = old_state.bitcast(UInt(2))
            res_plus = (state_uint + UInt(2)(1)).bitcast(Bits(2))
            res_minus = (state_uint - UInt(2)(1)).bitcast(Bits(2))

            plus_one = (old_state == Bits(2)(3)).select(Bits(2)(3), res_plus)
            minus_one = (old_state == Bits(2)(0)).select(Bits(2)(0), res_minus)
            new_state = actual_taken.select(plus_one, minus_one)
            
            bht_array[bht_idx] = new_state
            
            with Condition(actual_taken):
                btb_target_array[bht_idx] = pc_result_val

        with Condition(~rob_empty & is_final_array[head_idx]):
            log("ebreak | addr: 0x{:08x}", addr_array[head_idx])
            finish()

        with Condition(is_misprediction):
            reset_pc_addr_array[0] = pc_result_val
            for i in range(32):
                rf_has_recorder_array[i][0] = Bits(1)(0)

        head[0] = is_misprediction.select(Int(32)(0), commit.select(updated_head_ptr, head_ptr))
        tail[0] = is_misprediction.select(Int(32)(0), should_receive.select(updated_tail_ptr, tail_ptr))
        new_size = rob_size[0] + should_receive.select(Int(32)(1), Int(32)(0)) - commit.select(Int(32)(1), Int(32)(0))
        new_rob_size = is_misprediction.select(Int(32)(0), new_size)
        rob_size[0] = new_rob_size

        rob_full = (new_rob_size >= Int(32)(ROB_SIZE // 2))
        rob_full_array[0] = rob_full
        rob_full_array_for_fetcher[0] = (rob_size[0] >= Int(32)(ROB_SIZE - 2))

        for i in range(ROB_SIZE):
            idx = Bits(5)(i)
            is_head = (idx == head_ptr.bitcast(Bits(5)))
            is_tail = (idx == tail_ptr.bitcast(Bits(5)))
            write_0 = is_misprediction | (commit & is_head)
            write_1 = should_receive & is_tail & ~is_misprediction
            with Condition(write_0):
                allocated_array[i][0] = Bits(1)(0)
            with Condition(write_1):
                allocated_array[i][0] = Bits(1)(1)

        clear_signal_array[0] = is_misprediction.select(Bits(1)(1), Bits(1)(0))
        
        rs.async_called(
            rs_write = rs_write,
            rs_modify_recorder = rs_modify_recorder,
            rob_index = tail_idx.bitcast(Bits(3)),
            signals = signals,
            rs1_value = rf_value_array[rs1],
            rs1_recorder = rf_recorder_array[rs1].bitcast(Bits(3)),
            rs1_has_recorder = read_mux(rf_has_recorder_array, rs1, 32, 1),
            rs2_value = rf_value_array[rs2],
            rs2_recorder = rf_recorder_array[rs2].bitcast(Bits(3)),
            rs2_has_recorder = read_mux(rf_has_recorder_array, rs2, 32, 1),
            addr = addr,
            rs_modify_rd = modify_rd,
            rs_recorder = recorder.bitcast(Bits(3)),
            rs_modify_value = modify_value
        )
        lsq.async_called(
            lsq_write = lsq_write,
            lsq_modify_recorder = lsq_modify_recorder,
            rob_index = tail_idx.bitcast(Bits(3)),
            signals = signals,
            rs1_value = rf_value_array[rs1],
            rs1_recorder = rf_recorder_array[rs1],
            rs1_has_recorder = read_mux(rf_has_recorder_array, rs1, 32, 1),
            rs2_value = rf_value_array[rs2],
            rs2_recorder = rf_recorder_array[rs2],
            rs2_has_recorder = read_mux(rf_has_recorder_array, rs2, 32, 1),
            addr = addr,
            lsq_modify_rd = modify_rd,
            lsq_recorder = recorder.bitcast(Bits(3)),
            lsq_modify_value = modify_value,
            rob_head_index = head_idx.bitcast(Bits(3))
        )
        log("register value {}: 0x{:08x}", Bits(5)(10), rf_value_array[10])
        return rob_full
    