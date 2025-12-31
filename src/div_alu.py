from assassyn.frontend import *
from instruction import *
from utils import *


class DIV_ALU(Module):
    """
    Division ALU module implementing pipelined restoring division algorithm.
    Supports both signed and unsigned division, as well as remainder operations.
    Uses a multi-cycle pipelined approach similar to mul_alu.
    """

    def __init__(self):
        super().__init__(ports = {
            "valid": Port(Bits(1)),
            "rob_index": Port(Bits(3)),
            "alu_a": Port(Bits(32)),          # Dividend
            "alu_b": Port(Bits(32)),          # Divisor
            "calc_type": Port(Bits(RV32I_ALU.CNT)),
            "pc_addr": Port(Bits(32)),
            "get_remainder": Port(Bits(1)),   # 1: get remainder, 0: get quotient
            "rs1_sign": Port(Bits(1)),        # Whether dividend is signed
            "rs2_sign": Port(Bits(1)),        # Whether divisor is signed
            "clear": Port(Bits(1)),
        })
        self.name = "DIV_ALU"

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
            alu_a,
            alu_b,
            calc_type, 
            pc_addr,
            get_remainder,
            rs1_sign,
            rs2_sign,
            clear
        ) = self.pop_all_ports(True)

        stage1_valid = RegArray(Bits(1), 1)
        stage1_dividend = RegArray(Bits(32), 1)
        stage1_divisor = RegArray(Bits(32), 1)
        stage1_addr_array = RegArray(Bits(32), 1)
        stage1_rob_index_array = RegArray(Bits(3), 1)
        stage1_get_remainder_array = RegArray(Bits(1), 1)
        stage1_dividend_neg = RegArray(Bits(1), 1)
        stage1_divisor_neg = RegArray(Bits(1), 1)
        stage1_div_by_zero = RegArray(Bits(1), 1)

        stage2_valid = RegArray(Bits(1), 1)
        stage2_quotient = RegArray(Bits(32), 1)
        stage2_remainder = RegArray(Bits(33), 1)
        stage2_divisor = RegArray(Bits(32), 1)
        stage2_bit_pos = RegArray(Bits(6), 1)
        stage2_addr_array = RegArray(Bits(32), 1)
        stage2_rob_index_array = RegArray(Bits(3), 1)
        stage2_get_remainder_array = RegArray(Bits(1), 1)
        stage2_dividend_neg = RegArray(Bits(1), 1)
        stage2_divisor_neg = RegArray(Bits(1), 1)
        stage2_div_by_zero = RegArray(Bits(1), 1)

        stage3_valid = RegArray(Bits(1), 1)
        stage3_quotient = RegArray(Bits(32), 1)
        stage3_remainder = RegArray(Bits(33), 1)
        stage3_divisor = RegArray(Bits(32), 1)
        stage3_bit_pos = RegArray(Bits(6), 1)
        stage3_addr_array = RegArray(Bits(32), 1)
        stage3_rob_index_array = RegArray(Bits(3), 1)
        stage3_get_remainder_array = RegArray(Bits(1), 1)
        stage3_dividend_neg = RegArray(Bits(1), 1)
        stage3_divisor_neg = RegArray(Bits(1), 1)
        stage3_div_by_zero = RegArray(Bits(1), 1)

        stage4_valid = RegArray(Bits(1), 1)
        stage4_quotient = RegArray(Bits(32), 1)
        stage4_remainder = RegArray(Bits(32), 1)
        stage4_addr_array = RegArray(Bits(32), 1)
        stage4_rob_index_array = RegArray(Bits(3), 1)
        stage4_get_remainder_array = RegArray(Bits(1), 1)
        stage4_dividend_neg = RegArray(Bits(1), 1)
        stage4_divisor_neg = RegArray(Bits(1), 1)
        stage4_div_by_zero = RegArray(Bits(1), 1)

        dividend_neg = rs1_sign & alu_a[31:31]
        divisor_neg = rs2_sign & alu_b[31:31]
        dividend_abs = dividend_neg.select(
            ((~alu_a).bitcast(Int(32)) + Int(32)(1)).bitcast(Bits(32)),
            alu_a
        )
        divisor_abs = divisor_neg.select(
            ((~alu_b).bitcast(Int(32)) + Int(32)(1)).bitcast(Bits(32)),
            alu_b
        )
        div_by_zero = (alu_b == Bits(32)(0))
        
        with Condition(valid):
            log("DIV_ALU Input: dividend=0x{:08x}, divisor=0x{:08x}, pc=0x{:08x}", alu_a, alu_b, pc_addr)
            stage1_dividend[0] = dividend_abs
            stage1_divisor[0] = divisor_abs
            stage1_addr_array[0] = pc_addr
            stage1_rob_index_array[0] = rob_index
            stage1_get_remainder_array[0] = get_remainder
            stage1_dividend_neg[0] = dividend_neg
            stage1_divisor_neg[0] = divisor_neg
            stage1_div_by_zero[0] = div_by_zero
        stage1_valid[0] = valid.select(Bits(1)(1), Bits(1)(0)) & ~clear

        with Condition(stage1_valid[0]):
            log("DIV Stage 2: Starting division iterations")
            quotient = Bits(32)(0)
            remainder = concat(Bits(1)(0), stage1_dividend[0])
            divisor = stage1_divisor[0]
            
            for i in range(16):
                bit_idx = 31 - i
                # Shift remainder left by 1
                remainder_shifted = remainder << Bits(33)(1)
                # Try subtraction
                diff = (remainder_shifted[0:32].bitcast(Int(33)) - concat(Bits(1)(0), divisor).bitcast(Int(33))).bitcast(Bits(33))
                # If diff >= 0, keep it and set quotient bit
                no_borrow = ~diff[32:32]
                remainder = no_borrow.select(diff, remainder_shifted)
                quotient = no_borrow.select(quotient | (Bits(32)(1) << Bits(32)(bit_idx)), quotient)
            
            stage2_quotient[0] = quotient
            stage2_remainder[0] = remainder
            stage2_divisor[0] = divisor
            stage2_addr_array[0] = stage1_addr_array[0]
            stage2_rob_index_array[0] = stage1_rob_index_array[0]
            stage2_get_remainder_array[0] = stage1_get_remainder_array[0]
            stage2_dividend_neg[0] = stage1_dividend_neg[0]
            stage2_divisor_neg[0] = stage1_divisor_neg[0]
            stage2_div_by_zero[0] = stage1_div_by_zero[0]
        stage2_valid[0] = stage1_valid[0].select(Bits(1)(1), Bits(1)(0)) & ~clear

        with Condition(stage2_valid[0]):
            log("DIV Stage 3: Continuing division iterations")
            quotient = stage2_quotient[0]
            remainder = stage2_remainder[0]
            divisor = stage2_divisor[0]
            for i in range(16):
                bit_idx = 15 - i
                remainder_shifted = remainder << Bits(33)(1)
                diff = (remainder_shifted[0:32].bitcast(Int(33)) - concat(Bits(1)(0), divisor).bitcast(Int(33))).bitcast(Bits(33))
                no_borrow = ~diff[32:32]
                remainder = no_borrow.select(diff, remainder_shifted)
                quotient = no_borrow.select(quotient | (Bits(32)(1) << Bits(32)(bit_idx)), quotient)
            
            stage3_quotient[0] = quotient
            stage3_remainder[0] = remainder
            stage3_divisor[0] = divisor
            stage3_addr_array[0] = stage2_addr_array[0]
            stage3_rob_index_array[0] = stage2_rob_index_array[0]
            stage3_get_remainder_array[0] = stage2_get_remainder_array[0]
            stage3_dividend_neg[0] = stage2_dividend_neg[0]
            stage3_divisor_neg[0] = stage2_divisor_neg[0]
            stage3_div_by_zero[0] = stage2_div_by_zero[0]
        stage3_valid[0] = stage2_valid[0].select(Bits(1)(1), Bits(1)(0)) & ~clear

        with Condition(stage3_valid[0]):
            log("DIV Stage 4: Sign correction")
            
            raw_quotient = stage3_quotient[0]
            raw_remainder = stage3_remainder[0][0:31]
            quotient_neg = stage3_dividend_neg[0] ^ stage3_divisor_neg[0]
            remainder_neg = stage3_dividend_neg[0]
            final_quotient = quotient_neg.select(
                ((~raw_quotient).bitcast(Int(32)) + Int(32)(1)).bitcast(Bits(32)),
                raw_quotient
            )
            final_remainder = remainder_neg.select(
                ((~raw_remainder).bitcast(Int(32)) + Int(32)(1)).bitcast(Bits(32)),
                raw_remainder
            )
            stage4_quotient[0] = stage3_div_by_zero[0].select(Bits(32)(0xFFFFFFFF), final_quotient)
            stage4_remainder[0] = stage3_div_by_zero[0].select(stage3_remainder[0][0:31], final_remainder)
            stage4_addr_array[0] = stage3_addr_array[0]
            stage4_rob_index_array[0] = stage3_rob_index_array[0]
            stage4_get_remainder_array[0] = stage3_get_remainder_array[0]
            stage4_dividend_neg[0] = stage3_dividend_neg[0]
            stage4_divisor_neg[0] = stage3_divisor_neg[0]
            stage4_div_by_zero[0] = stage3_div_by_zero[0]
        stage4_valid[0] = stage3_valid[0].select(Bits(1)(1), Bits(1)(0)) & ~clear

        signal_array[0] = stage4_valid[0].select(Bits(1)(1), Bits(1)(0)) & ~clear
        with Condition(stage4_valid[0] & ~clear):
            result = stage4_get_remainder_array[0].select(stage4_remainder[0], stage4_quotient[0])
            log("DIV_ALU Result: quotient=0x{:08x}, remainder=0x{:08x}, output=0x{:08x}", 
                stage4_quotient[0], stage4_remainder[0], result)
            result_array[0] = result
            rob_index_array[0] = stage4_rob_index_array[0]
            pc_result_array[0] = (stage4_addr_array[0].bitcast(Int(32)) + Int(32)(4)).bitcast(Bits(32))
