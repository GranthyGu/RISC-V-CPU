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
            "addr": Port(Bits(32))
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

        rob_index_array_from_lsq: Array,
        result_array_from_lsq: Array,
        pc_result_array_from_lsq: Array,
        signal_array_from_lsq: Array,

        clear_signal_array: Array,
        reset_pc_addr_array: Array,

        rs: RS,
        lsq: LSQ,
    ):
        # 参数解析： 
        # rob_full_array: Array(Bits(1), 1)                     判定 rob 是否已满
        # rf_value_array: Array(Bits(32), 32)                   存储 rf 中各个寄存器的值
        # rf_recorder_array: Array(Bits(5), 32)                 存储 rf 中各个寄存器 recorder 的编号
        # rf_has_recorder_array: Array(Bits(1), 32)             存储当前 rf 中各个寄存器是否有 recorder

        rf_value_array = RegArray(Bits(32), 32)
        rf_recorder_array = RegArray(Bits(3), 32)
        rf_has_recorder_array = [RegArray(Bits(1), 1) for _ in range(32)]

        # ROB 自身的性质
        allocated_array = [RegArray(Bits(1), 1) for _ in range(ROB_SIZE)]         # ROB 中这一条有没有分配指令
        ready_array = [RegArray(Bits(1), 1) for _ in range(ROB_SIZE)]             # ROB 中当前指令能不能 commit
        head = RegArray(Int(32), 1, initializer = [0])        # 存储 ROB 的头指针
        tail = RegArray(Int(32), 1, initializer = [0])        # 存储 ROB 的尾指针
        rob_size = RegArray(Int(32), 1, initializer = [0])   # 存储 ROB 目前指令的条数
        rob_full = Bits(1)(0)                                 # 存储 ROB 是否已满
        rob_empty = Bits(1)(0)

        # 指令有关的信息
        is_final_array = RegArray(Bits(1), ROB_SIZE)          # 是否为最终指令（写回到寄存器或内存）
        is_reg_write_array = RegArray(Bits(1), ROB_SIZE)      # 是否为写回到寄存器的指令
        is_memory_write_array = RegArray(Bits(1), ROB_SIZE)   # 是否为写回到内存的指令
        is_branch_array = RegArray(Bits(1), ROB_SIZE)         # 是否为分支指令
        is_load_or_store_array = RegArray(Bits(1), ROB_SIZE)  # 是否为 load/store 指令

        rd_array = RegArray(Bits(5), ROB_SIZE)                # 存储指令的 rd
        rd_valid_array = RegArray(Bits(1), ROB_SIZE)          # 存储指令是否有 rd

        rs1_array = RegArray(Bits(5), ROB_SIZE)               # 存储指令的 rs1

        rs2_array = RegArray(Bits(5), ROB_SIZE)               # 存储指令的 rs2

        imm_array = RegArray(Bits(32), ROB_SIZE)              # 存储立即数 imm

        calc_result_array = RegArray(Bits(32), ROB_SIZE)      # 存储 alu 计算出的 32 位结果
        load_result_array = RegArray(Bits(32), ROB_SIZE)      # 存储 load 出来的 32 位结果
        pc_result_array = [RegArray(Bits(32), 1) for _ in range(ROB_SIZE)]

        addr_array = RegArray(Bits(32), ROB_SIZE)             # 存储指令的地址

        # Decoder -> ROB has 1-cycle latency (async_called): one instruction can be in-flight.
        # We therefore expose an *upstream* full signal one entry earlier (reserve 1 slot),
        # but ROB itself should only reject when it is physically full.
        rob_phys_full = (rob_size[0] >= Int(32)(ROB_SIZE))

        rob_empty = (rob_size[0] == Int(32)(0))

        receive, signals, addr = self.pop_all_ports(True)
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

        log("addr: 0x{:08x} | is_reg_write: {} | is_memory_write: {} | is_branch: {}", addr, is_reg_write, is_memory_write, is_branch)
        log("rd: 0x{:02x} | has_rd: {} | rs1: 0x{:02x} | has_rs1: {} | rs2: 0x{:02x} | has_rs2: {} | imm: 0x{:08x} | has_imm: {} | alu: {}",
            rd, has_rd, rs1, has_rs1, rs2, has_rs2, imm, has_imm, signals.alu)
        
        head_ptr = head[0]
        tail_ptr = tail[0]

        head_idx = head_ptr.bitcast(Bits(32))[0:2]
        tail_idx = tail_ptr.bitcast(Bits(32))[0:2]

        updated_tail_ptr = tail_ptr + Int(32)(1)
        updated_tail_ptr = (updated_tail_ptr == Int(32)(ROB_SIZE)).select(Int(32)(0), updated_tail_ptr)

        updated_head_ptr = head_ptr + Int(32)(1)
        updated_head_ptr = (updated_head_ptr == Int(32)(ROB_SIZE)).select(Int(32)(0), updated_head_ptr)
        
        updated_head_idx = updated_head_ptr.bitcast(Bits(32))[0:2]

        commit = ~rob_empty & read_mux(ready_array, head_idx, ROB_SIZE, 1)
        updated_pc_addr = addr_array[updated_head_idx]
        pc_result_val = read_mux(pc_result_array, head_idx, ROB_SIZE, 32)
        is_misprediction = commit & (updated_pc_addr != pc_result_val) & (updated_head_ptr != tail_ptr)
        should_receive = ~rob_phys_full & receive & (~clear_signal_array[0])

        with Condition(should_receive & ~is_misprediction):
            rd_valid_array[tail_idx] = has_rd

        with Condition(should_receive & ~is_misprediction & has_rd):
            # rf_recorder_array[rd] = tail_ptr.bitcast(Bits(5)) # Moved to conflict logic
            # write1hot(rf_has_recorder_array, rd, Bits(1)(1)) # Moved to conflict logic
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
        # log("is_load_or_store_array[head_ptr]: {} | modify_value: 0x{:08x}", is_load_or_store_array[head_ptr], modify_value)

        rs_write = should_receive & ~is_misprediction & (~is_load_or_store)
        lsq_write = should_receive & ~is_misprediction & is_load_or_store

        # log("receive: {} | should_receive: {} | is_misprediction: {} | commit: {}", receive, should_receive, is_misprediction, commit)
        with Condition(should_receive & ~is_misprediction):
            log("ROB entry {} allocated", tail_ptr)
            # write1hot(allocated_array, tail_ptr, Bits(1)(1)) # Moved to loop
            is_branch_array[tail_idx] = is_branch
            is_memory_write_array[tail_idx] = is_memory_write
            is_reg_write_array[tail_idx] = is_reg_write
            addr_array[tail_idx] = addr
            is_load_or_store_array[tail_idx] = is_load_or_store
            write1hot(ready_array, tail_idx, Bits(1)(0))
            is_final_array[tail_idx] = is_final
            # tail[0] = updated_tail_ptr # Moved to select

        rob_index_from_alu = rob_index_array_from_alu[0]
        write_result_from_alu = signal_array_from_alu[0]
        write_result_from_alu = write_result_from_alu & read_mux(allocated_array, rob_index_from_alu[0:2], ROB_SIZE, 1)
        with Condition(write_result_from_alu):
            log("ROB entry {} received ALU result: 0x{:08x} | pc_result: 0x{:08x}", rob_index_from_alu, result_array_from_alu[0], pc_result_array_from_alu[0])    
            calc_result_array[rob_index_from_alu[0:2]] = result_array_from_alu[0]
            write1hot(pc_result_array, rob_index_from_alu[0:2], pc_result_array_from_alu[0])
            write1hot(ready_array, rob_index_from_alu[0:2], Bits(1)(1))
        
        rob_index_from_lsq = rob_index_array_from_lsq[0]
        write_signal_from_lsq = signal_array_from_lsq[0]
        write_result_from_lsq = write_signal_from_lsq & read_mux(allocated_array, rob_index_from_lsq[0:2], ROB_SIZE, 1)
        with Condition(write_result_from_lsq):
            log("ROB entry {} received LSQ result: 0x{:08x} | pc_result: 0x{:08x}", rob_index_from_lsq, result_array_from_lsq[0], pc_result_array_from_lsq[0])
            load_result_array[rob_index_from_lsq[0:2]] = result_array_from_lsq[0]
            write1hot(pc_result_array, rob_index_from_lsq[0:2], pc_result_array_from_lsq[0])
            write1hot(ready_array, rob_index_from_lsq[0:2], Bits(1)(1))

        modify_rd = rd_valid_array[head_idx].select(rd_array[head_idx], Bits(5)(0))
        recorder = head_ptr

        # Logic for rf_has_recorder_array
        receive_write = should_receive & ~is_misprediction & has_rd
        commit_write = modify_recorder & (modify_rd != Bits(5)(0)) & \
                       read_mux(rf_has_recorder_array, modify_rd, 32, 1) & \
                       (rf_recorder_array[modify_rd] == recorder.bitcast(Bits(5)))
        
        conflict = receive_write & commit_write & (rd == modify_rd)

        with Condition(receive_write):
             write1hot(rf_has_recorder_array, rd, Bits(1)(1))
             rf_recorder_array[rd] = tail_idx.bitcast(Bits(3))
             
        with Condition(commit_write & ~conflict & ~is_misprediction):
             write1hot(rf_has_recorder_array, modify_rd, Bits(1)(0))
             
        with Condition(modify_recorder & (modify_rd != Bits(5)(0))):
            log("RF entry {} update value to 0x{:08x}", modify_rd, modify_value)
            rf_value_array[modify_rd] = modify_value
    
        with Condition(commit):
            log("ROB entry {} committed, addr: 0x{:08x}", head_ptr, addr_array[head_idx])
        with Condition(~rob_empty & is_final_array[head_idx]):
            log("ebreak")
            finish()

        with Condition(is_misprediction):
            log("Branch misprediction detected at ROB entry {}", head_ptr)
            reset_pc_addr_array[0] = pc_result_val
            for i in range(32):
                rf_has_recorder_array[i][0] = Bits(1)(0)

        # State updates
        head[0] = is_misprediction.select(Int(32)(0), commit.select(updated_head_ptr, head_ptr))
        tail[0] = is_misprediction.select(Int(32)(0), should_receive.select(updated_tail_ptr, tail_ptr))
        
        new_size = rob_size[0] + should_receive.select(Int(32)(1), Int(32)(0)) - commit.select(Int(32)(1), Int(32)(0))
        new_rob_size = is_misprediction.select(Int(32)(0), new_size)
        rob_size[0] = new_rob_size

        # log("ROB size updated to {}", new_rob_size)

        rob_full = (new_rob_size >= Int(32)(ROB_SIZE // 2))
        rob_full_array[0] = rob_full
        rob_full_array_for_fetcher[0] = (rob_size[0] >= Int(32)(ROB_SIZE - 2))

        # log("rob_full: {} | rob_phy_full: {} | rob_size: {}", rob_full, rob_phys_full, rob_size[0])

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
        
        # log("result_from_alu: 0x{:08x} | result_from_lsq: 0x{:08x}",
        #     result_array_from_alu[0], result_array_from_lsq[0])
        
        # log("modify_recorder: {} | rs_modify_recorder:{} | lsq_modify_recorder: {}", modify_recorder, rs_modify_recorder, lsq_modify_recorder)
        # 把信息发送到 rs 中
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

        # 把信息发送到 lsq 中
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
            lsq_recorder = recorder.bitcast(Bits(5)),
            lsq_modify_value = modify_value
        )

        for i in range(ROB_SIZE):
            log("ROB Entry {}: allocated: {} | ready: {} | pc_addr: 0x{:08x}",
                Bits(5)(i),
                allocated_array[i][0],
                ready_array[i][0],
                addr_array[i]
            )

        return rob_full 
