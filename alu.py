from assassyn.frontend import *
from instruction import *

class ALU(Module):

    def __init__(self):
        super().__init__(ports = {
            "valid": Port(Bits(1)),
            "rob_index": Port(Bits(5)),
            "a": Port(Bits(32)),
            "b": Port(Bits(32)),
            "alu_a": Port(Bits(32)),
            "alu_b": Port(Bits(32)),
            "link_pc": Port(Bits(1)),
            "is_jalr": Port(Bits(1)),
            "cond": Port(Bits(RV32I_ALU.CNT)),
            "flip": Port(Bits(1)),
            "is_branch": Port(Bits(1)),
            "calc_type": Port(Bits(RV32I_ALU.CNT)),
            "pc_addr": Port(Bits(32)),
        }, no_arbiter = True)
        self.name = "ALU"

    @module.combinational
    def build(
        self,
        rob_index_array: Array,
        result_array: Array,
        pc_result_array: Array,
        signal_array: Array,
    ):
        (
            valid,
            rob_index,
            a,
            b,
            alu_a,
            alu_b,
            link_pc,
            is_jalr,
            cond,
            flip,
            is_branch,
            calc_type,
            pc_addr
        ) = self.pop_all_ports(True)

        results = [Bits(32)(0)] * RV32I_ALU.CNT

        alu_a = is_jalr.select(a, alu_a)

        adder_result = (alu_a.bitcast(Int(32)) + alu_b.bitcast(Int(32))).bitcast(Bits(32))
        le_result = (a.bitcast(Int(32)) < b.bitcast(Int(32))).select(Bits(32)(1), Bits(32)(0))
        eq_result = (a == b).select(Bits(32)(1), Bits(32)(0))
        leu_result = (a < b).select(Bits(32)(1), Bits(32)(0))
        sra_signed_result = (alu_a.bitcast(Int(32)) >> alu_b[0:4].bitcast(Int(5))).bitcast(Bits(32))
        sub_result = (alu_a.bitcast(Int(32)) - alu_b.bitcast(Int(32))).bitcast(Bits(32))

        results[RV32I_ALU.ALU_ADD] = adder_result
        results[RV32I_ALU.ALU_SUB] = sub_result
        results[RV32I_ALU.ALU_CMP_LT] = le_result
        results[RV32I_ALU.ALU_CMP_EQ] = eq_result
        results[RV32I_ALU.ALU_CMP_LTU] = leu_result
        results[RV32I_ALU.ALU_XOR] = alu_a ^ alu_b
        results[RV32I_ALU.ALU_OR] = alu_a | alu_b
        results[RV32I_ALU.ALU_ORI] = alu_a | alu_b
        results[RV32I_ALU.ALU_AND] = alu_a & alu_b
        results[RV32I_ALU.ALU_TRUE] = Bits(32)(1)
        results[RV32I_ALU.ALU_SLL] = alu_a << alu_b[0:4]
        results[RV32I_ALU.ALU_SRA] = sra_signed_result 
        results[RV32I_ALU.ALU_SRA_U] = alu_a >> alu_b[0:4]
        results[RV32I_ALU.ALU_NONE] = Bits(32)(0)

        alu = calc_type
        result = alu.select1hot(*results)
        calc_result = result
        result = link_pc.select((pc_addr.bitcast(Int(32)) + Int(32)(4)).bitcast(Bits(32)), result)

        condition = cond.select1hot(*results)
        condition = flip.select(~condition, condition)

        new_pc = (pc_addr.bitcast(Int(32)) + Int(32)(4)).bitcast(Bits(32))
        jump = is_branch.select(condition[0:0], Bits(1)(0))
        new_pc = jump.select(calc_result, new_pc)
        
        rob_index_array[0] = rob_index
        result_array[0] = result
        pc_result_array[0] = new_pc
        signal_array[0] = valid

        with Condition(valid):
            log("a: 0x{:08x} | b: 0x{:08x} | alu_a: 0x{:08x} | alu_b: 0x{:08x} | result: 0x{:08x} | cond: 0x{:08x} | pc: 0x{:08x} | new_pc: 0x{:08x}",
            a, b, alu_a, alu_b, result, cond, pc_addr, new_pc)

        
