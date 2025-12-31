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
        # 这是一个顺序执行的用于处理 load/store 指令的模块

        head = RegArray(Int(32), 1, initializer=[0])          # 存储 LSQ 的头指针
        tail = RegArray(Int(32), 1, initializer=[0])          # 存储 LSQ 的尾指针
        lsq_size = RegArray(Int(32), 1)                       # 存储 LSQ 目前指令的条数
        lsq_full = Bits(1)(0)                                 # 存储 LSQ 是否已满
        allocated_array = [RegArray(Bits(1), 1) for _ in range(LSQ_SIZE)]         # LSQ 中这一条有没有分配指令

        rob_index_array = RegArray(Bits(3), LSQ_SIZE)         # 存储对应的 ROB 条目的索引
        is_load_array = RegArray(Bits(1), LSQ_SIZE)           # 是否为 load 指令
        is_store_array = RegArray(Bits(1), LSQ_SIZE)          # 是否为 store 指令
        rs1_array = RegArray(Bits(5), LSQ_SIZE)               # 存储 rs1 的编号
        rs1_value_array = [RegArray(Bits(32), 1) for _ in range(LSQ_SIZE)]        # 存储 rs1 的值
        has_rs1_array = RegArray(Bits(1), LSQ_SIZE)           # 存储指令中是否有 rs1
        rs1_recorder_array = RegArray(Bits(3), LSQ_SIZE)      # 存储 rs1 的 recorder
        has_rs1_recorder_array = [RegArray(Bits(1), 1) for _ in range(LSQ_SIZE)]  # 存储 rs1 是否有 recorder
        rs2_array = RegArray(Bits(5), LSQ_SIZE)               # 存储 rs2 的编号
        rs2_value_array = [RegArray(Bits(32), 1) for _ in range(LSQ_SIZE)]        # 存储 rs2 的值
        has_rs2_array = RegArray(Bits(1), LSQ_SIZE)           # 存储指令中是否有 rs2
        rs2_recorder_array = RegArray(Bits(3), LSQ_SIZE)      # 存储 rs2 的 recorder
        has_rs2_recorder_array = [RegArray(Bits(1), 1) for _ in range(LSQ_SIZE)]   # 存储 rs2 是否有 recorder
        imm_array = RegArray(Bits(32), LSQ_SIZE)              # 存储立即数 imm
        addr_array = RegArray(Bits(32), LSQ_SIZE)             # 存储计算得到的地址
        ready_array = [RegArray(Bits(1), 1) for _ in range(LSQ_SIZE)]             # 存储该条目是否准备好

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
        
        # 检查 head 指向的条目是否准备好执行
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
        memory_place_array[0] = alu_result.bitcast(Bits(32))[0:1] # load_byte 的时候需要确定是加载哪个字节
        dcache_wdata = read_mux(rs2_value_array, head_idx, LSQ_SIZE, 32)

        is_store = is_store_array[head_idx]
        rob_idx_of_head = rob_index_array[head_idx]
        can_execute_store = (rob_idx_of_head == rob_head_index)
        condition_met = (~is_store) | (is_store & can_execute_store)

        execute_valid = read_mux(allocated_array, head_idx, LSQ_SIZE, 1) & read_mux(ready_array, head_idx, LSQ_SIZE, 1) & (~clear_signal_array[0]) & condition_met
        log("head_idx: {} | allocated: {} | ready: {}", head_idx, read_mux(allocated_array, head_idx, LSQ_SIZE, 1), read_mux(ready_array, head_idx, LSQ_SIZE, 1))
        with Condition(execute_valid):
            # 执行 head 指向的条目
            log("LSQ entry {} executed", head_ptr)

            write1hot(allocated_array, head_idx, Bits(1)(0))
            head[0] = (head_ptr + Int(32)(1) == Int(32)(LSQ_SIZE)).select(Int(32)(0), head_ptr + Int(32)(1))
        dcache.build(we = dcache_we & execute_valid, re = dcache_re & execute_valid, addr = dcache_addr, wdata = dcache_wdata)
        # with Condition(dcache_we & execute_valid | dcache_re & execute_valid):
        #     log("DCACHE | we: {} | re: {} | wdata: 0x{:08x} | addr: 0x{:08x} | pc_addr: 0x{:08x}", dcache_we & execute_valid, dcache_re & execute_valid, dcache_wdata, dcache_addr, addr_array[0])

        with Condition(lsq_modify_recorder):
            for i in range(LSQ_SIZE):
                # log("LSQ entry {} modify recorder", Bits(5)(i))
                # log("  allocated: {}, has_rs1_recorder: {}, rs1_recorder: {}, has_rs2_recorder: {}, rs2_recorder: {}", 
                #     allocated_array[i][0], has_rs1_recorder_array[i][0], rs1_recorder_array[i], has_rs2_recorder_array[i][0], rs2_recorder_array[i])
                modify_rs1_recorder = allocated_array[i][0] & has_rs1_recorder_array[i][0] & (rs1_recorder_array[i] == lsq_recorder)
                modify_rs2_recorder = allocated_array[i][0] & has_rs2_recorder_array[i][0] & (rs2_recorder_array[i] == lsq_recorder)
                with Condition(modify_rs1_recorder):
                    has_rs1_recorder_array[i][0] = Bits(1)(0)
                    rs1_value_array[i][0] = lsq_modify_value
                with Condition(modify_rs2_recorder):
                    has_rs2_recorder_array[i][0] = Bits(1)(0)
                    rs2_value_array[i][0] = lsq_modify_value
                
                with Condition(~(write_valid & (tail_ptr == Int(32)(i)))):
                    # log("  ready_array[{}] modified to : {}", Bits(5)(i), ~((has_rs1_array[i] & (has_rs1_recorder_array[i][0] & (~modify_rs1_recorder))) | (has_rs2_array[i] & (has_rs2_recorder_array[i][0] & (~modify_rs2_recorder)))))
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