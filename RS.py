from assassyn.frontend import *
from instruction import *
from alu import *
from utils import *

RS_SIZE = 8


class RS(Module):

    def __init__(self):
        super().__init__(
            ports = {
                "rs_write": Port(Bits(1)),
                "rs_modify_recorder": Port(Bits(1)),
                "rob_index": Port(Bits(3)),                # 当前这个 entry 在 rs 中的下标
                "signals": Port(decoder_signals),
                "rs1_value": Port(Bits(32)),
                "rs1_recorder": Port(Bits(3)),
                "rs1_has_recorder": Port(Bits(1)),
                "rs2_value": Port(Bits(32)),
                "rs2_recorder": Port(Bits(3)),
                "rs2_has_recorder": Port(Bits(1)),
                "addr": Port(Bits(32)),                    # 计算对应的指令的地址
                "rs_modify_rd": Port(Bits(5)),
                "rs_recorder": Port(Bits(3)),
                "rs_modify_value": Port(Bits(32)),
            }
        )
        self.name = "RS"

    @module.combinational
    def build(
            self, 
            alu: ALU,
            clear_signal_array: Array,
        ):

        # RS 自身的性质
        allocated_array = [RegArray(Bits(1), 1) for _ in range(RS_SIZE)]          # RS 中这一条有没有分配指令

        rob_index_array = RegArray(Bits(3), RS_SIZE)
        rs1_array = RegArray(Bits(5), RS_SIZE)
        rs1_value_array = [RegArray(Bits(32), 1) for _ in range(RS_SIZE)]
        has_rs1_array = RegArray(Bits(1), RS_SIZE)
        rs2_array = RegArray(Bits(5), RS_SIZE)
        rs2_value_array = [RegArray(Bits(32), 1) for _ in range(RS_SIZE)]
        has_rs2_array = RegArray(Bits(1), RS_SIZE)  
        rs1_recorder_array = RegArray(Bits(3), RS_SIZE)
        has_rs1_recorder_array = [RegArray(Bits(1), 1) for _ in range(RS_SIZE)]
        rs2_recorder_array = RegArray(Bits(3), RS_SIZE)
        has_rs2_recorder_array = [RegArray(Bits(1), 1) for _ in range(RS_SIZE)]
        imm_array = RegArray(Bits(32), RS_SIZE)
        has_imm_array = RegArray(Bits(1), RS_SIZE)
        link_pc_array = RegArray(Bits(1), RS_SIZE)
        is_jalr_array = RegArray(Bits(1), RS_SIZE)
        alu_type_array = RegArray(Bits(RV32I_ALU.CNT), RS_SIZE)
        cond_array = RegArray(Bits(RV32I_ALU.CNT), RS_SIZE)
        flip_array = RegArray(Bits(1), RS_SIZE)
        is_branch_array = RegArray(Bits(1), RS_SIZE)
        addr_array = RegArray(Bits(32), RS_SIZE)
                                  
        (
            rs_write,
            rs_modify_recorder,
            rob_index,
            signals,
            rs1_value,
            rs1_recorder,
            rs1_has_recorder,
            rs2_value,
            rs2_recorder,
            rs2_has_recorder,
            addr,
            rs_modify_rd,
            rs_recorder,
            rs_modify_value
        ) = self.pop_all_ports(True)

        allocated =  read_mux(allocated_array, rob_index, RS_SIZE, 1).select(Bits(1)(1), Bits(1)(0))

        # 非常有意思的设计
        rs1_coincidence = rs1_has_recorder & (rs1_recorder == rs_recorder) & rs_modify_recorder
        rs1_has_recorder = rs1_coincidence.select(Bits(1)(0), rs1_has_recorder)
        rs1_value = rs1_coincidence.select(rs_modify_value, rs1_value)

        rs2_coincidence = rs2_has_recorder & (rs2_recorder == rs_recorder) & rs_modify_recorder
        rs2_has_recorder = rs2_coincidence.select(Bits(1)(0), rs2_has_recorder)
        rs2_value = rs2_coincidence.select(rs_modify_value, rs2_value)

        with Condition(rs_write & ~allocated):
            log("RS entry {} allocated", rob_index)
            log("RS write: rs1_value: 0x{:08x} | rs1_recorder: {} | rs1_has_recorder: {} | rs2_value: 0x{:08x} | rs2_recorder: {} | rs2_has_recorder: {}",
                rs1_value, rs1_recorder, rs1_has_recorder, rs2_value, rs2_recorder, rs2_has_recorder)
            rob_index_array[rob_index] = rob_index
            rs1_array[rob_index] = signals.rs1
            has_rs1_array[rob_index] = signals.rs1_valid
            write1hot(rs1_value_array, rob_index, rs1_value, width=3)
            rs2_array[rob_index] = signals.rs2
            has_rs2_array[rob_index] = signals.rs2_valid
            write1hot(rs2_value_array, rob_index, rs2_value, width=3)
            rs1_recorder_array[rob_index] = rs1_recorder
            write1hot(has_rs1_recorder_array, rob_index, rs1_has_recorder, width=3)
            rs2_recorder_array[rob_index] = rs2_recorder
            write1hot(has_rs2_recorder_array, rob_index, rs2_has_recorder, width=3)
            imm_array[rob_index] = signals.imm
            has_imm_array[rob_index] = signals.imm_valid
            link_pc_array[rob_index] = signals.link_pc
            is_jalr_array[rob_index] = signals.is_jalr
            alu_type_array[rob_index] = signals.alu
            addr_array[rob_index] = addr
            cond_array[rob_index] = signals.cond
            flip_array[rob_index] = signals.flip
            is_branch_array[rob_index] = signals.is_branch
            write1hot(allocated_array, rob_index, Bits(1)(1))

        send_index = Bits(3)(0)
        send = Bits(1)(0)
        for i in range(RS_SIZE):
            allocated = allocated_array[i][0]
            rs1_valid = (~has_rs1_array[i]) | (has_rs1_array[i] & (~has_rs1_recorder_array[i][0]))
            rs2_valid = (~has_rs2_array[i]) | (has_rs2_array[i] & (~has_rs2_recorder_array[i][0]))
            valid = allocated & rs1_valid & rs2_valid
            # log("RS entry {} - allocated:  {} | rs1_valid: {} | rs2_valid: {} | valid: {}",
            #     Bits(5)(i), allocated, rs1_valid, rs2_valid, valid)
            send_index = valid.select(Bits(3)(i), send_index)
            send = valid.select(Bits(1)(1), send)

        # log("send_index: {} | send: {}", send_index, send)

        a = (rs1_array[send_index] == Bits(5)(0)).select(Bits(32)(0), read_mux(rs1_value_array, send_index, RS_SIZE, 32))
        b = (rs2_array[send_index] == Bits(5)(0)).select(Bits(32)(0), read_mux(rs2_value_array, send_index, RS_SIZE, 32))

        alu_a = (is_branch_array[send_index]).select(addr_array[send_index], a)
        alu_b = has_imm_array[send_index].select(imm_array[send_index], b)
        send = send & (~clear_signal_array[0])

        with Condition(send):
            # 这里需要实现把已经准备好的第一条指令送去 alu 执行
            # log("RS entry {} send to alu", send_index)
            write1hot(allocated_array, send_index, Bits(1)(0))


        alu.async_called(
            valid = send,
            rob_index = rob_index_array[send_index],
            a = a,
            b = b,
            alu_a = alu_a,
            alu_b = alu_b,
            link_pc = link_pc_array[send_index],
            is_jalr = is_jalr_array[send_index],
            cond = send.select(cond_array[send_index], Bits(RV32I_ALU.CNT)(1)),
            flip = flip_array[send_index],
            is_branch = is_branch_array[send_index],
            calc_type = send.select(alu_type_array[send_index], Bits(RV32I_ALU.CNT)(1 << RV32I_ALU.ALU_NONE)),
            pc_addr = addr_array[send_index]
        )

        with Condition(rs_modify_recorder):
            log("RS modify recorder: rs_recorder: {} | rs_modify_value: 0x{:08x}",
                rs_recorder, rs_modify_value)
            for i in range(RS_SIZE):
                with Condition(allocated_array[i][0] & has_rs1_recorder_array[i][0] & (rs1_recorder_array[i] == rs_recorder)):
                    log("RS entry {} rs1_recorder matched, updating value", Bits(5)(i))
                    has_rs1_recorder_array[i][0] = Bits(1)(0)
                    rs1_value_array[i][0] = rs_modify_value
                with Condition(allocated_array[i][0] & has_rs2_recorder_array[i][0] & (rs2_recorder_array[i] == rs_recorder)):
                    log("RS entry {} rs2_recorder matched, updating value", Bits(5)(i))
                    has_rs2_recorder_array[i][0] = Bits(1)(0)
                    rs2_value_array[i][0]= rs_modify_value

        with Condition(clear_signal_array[0]):
            for i in range(RS_SIZE):
                allocated_array[i][0] = Bits(1)(0)

        for i in range(RS_SIZE):
            # log("rs1_value_array[{}] = 0x{:08x} | rs2_value_array[{}] = 0x{:08x}", Bits(3)(i), rs1_value_array[i][0], Bits(3)(i), rs2_value_array[i][0])
            log("has_rs1_recorder_array[{}] = {} | has_rs2_recorder_array[{}] = {}", Bits(3)(i), has_rs1_recorder_array[i][0], Bits(3)(i), has_rs2_recorder_array[i][0])