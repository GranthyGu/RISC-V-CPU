from assassyn.frontend import *
from instruction import *
from utils import *


class DIV_ALU(Module):
    """
    Division ALU module implementing pipelined restoring division algorithm.
    Supports both signed and unsigned division, as well as remainder operations.
    
    Algorithm: Restoring Division (32-bit / 32-bit)
    For dividend / divisor:
    1. Initialize: remainder = 0, quotient = dividend (as shift register)
    2. For each bit i from 31 to 0:
       - Left shift {remainder, quotient} by 1
       - remainder = remainder - divisor
       - If remainder >= 0: set quotient bit 0 to 1
       - Else: remainder = remainder + divisor (restore), quotient bit 0 stays 0
    3. Final: quotient contains result, remainder contains remainder
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

        # Pipeline stage 1: Input and sign handling
        stage1_valid = RegArray(Bits(1), 1)
        stage1_quotient = RegArray(Bits(32), 1)   # Holds dividend absolute value
        stage1_remainder = RegArray(Bits(32), 1)  # Initialized to 0
        stage1_divisor = RegArray(Bits(32), 1)
        stage1_addr_array = RegArray(Bits(32), 1)
        stage1_rob_index_array = RegArray(Bits(3), 1)
        stage1_get_remainder_array = RegArray(Bits(1), 1)
        stage1_dividend_neg = RegArray(Bits(1), 1)
        stage1_divisor_neg = RegArray(Bits(1), 1)
        stage1_div_by_zero = RegArray(Bits(1), 1)

        # Pipeline stage 2: First 16 iterations (bits 31-16)
        stage2_valid = RegArray(Bits(1), 1)
        stage2_quotient = RegArray(Bits(32), 1)
        stage2_remainder = RegArray(Bits(32), 1)
        stage2_divisor = RegArray(Bits(32), 1)
        stage2_addr_array = RegArray(Bits(32), 1)
        stage2_rob_index_array = RegArray(Bits(3), 1)
        stage2_get_remainder_array = RegArray(Bits(1), 1)
        stage2_dividend_neg = RegArray(Bits(1), 1)
        stage2_divisor_neg = RegArray(Bits(1), 1)
        stage2_div_by_zero = RegArray(Bits(1), 1)

        # Pipeline stage 3: Last 16 iterations (bits 15-0)
        stage3_valid = RegArray(Bits(1), 1)
        stage3_quotient = RegArray(Bits(32), 1)
        stage3_remainder = RegArray(Bits(32), 1)
        stage3_divisor = RegArray(Bits(32), 1)
        stage3_addr_array = RegArray(Bits(32), 1)
        stage3_rob_index_array = RegArray(Bits(3), 1)
        stage3_get_remainder_array = RegArray(Bits(1), 1)
        stage3_dividend_neg = RegArray(Bits(1), 1)
        stage3_divisor_neg = RegArray(Bits(1), 1)
        stage3_div_by_zero = RegArray(Bits(1), 1)

        # Pipeline stage 4: Output and sign correction
        stage4_valid = RegArray(Bits(1), 1)
        stage4_quotient = RegArray(Bits(32), 1)
        stage4_remainder = RegArray(Bits(32), 1)
        stage4_addr_array = RegArray(Bits(32), 1)
        stage4_rob_index_array = RegArray(Bits(3), 1)
        stage4_get_remainder_array = RegArray(Bits(1), 1)
        stage4_dividend_neg = RegArray(Bits(1), 1)
        stage4_divisor_neg = RegArray(Bits(1), 1)
        stage4_div_by_zero = RegArray(Bits(1), 1)

        # ===== Stage 1: Input processing and sign handling =====
        dividend_neg = rs1_sign & alu_a[31:31]
        divisor_neg = rs2_sign & alu_b[31:31]
        
        # Get absolute values
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
            stage1_quotient[0] = dividend_abs    # quotient register initially holds dividend
            stage1_remainder[0] = Bits(32)(0)    # remainder starts at 0
            stage1_divisor[0] = divisor_abs
            stage1_addr_array[0] = pc_addr
            stage1_rob_index_array[0] = rob_index
            stage1_get_remainder_array[0] = get_remainder
            stage1_dividend_neg[0] = dividend_neg
            stage1_divisor_neg[0] = divisor_neg
            stage1_div_by_zero[0] = div_by_zero
        stage1_valid[0] = valid.select(Bits(1)(1), Bits(1)(0)) & ~clear

        # ===== Stage 2: First 16 iterations of restoring division =====
        with Condition(stage1_valid[0]):
            log("DIV Stage 2: Starting division iterations")
            
            q = stage1_quotient[0]
            r = stage1_remainder[0]
            d = stage1_divisor[0]
            
            # Perform 16 iterations
            for i in range(16):
                # Left shift {r, q} by 1: 
                # - r gets its bits shifted left, and the MSB of q enters as r's LSB
                # - q gets its bits shifted left, and 0 enters as q's LSB
                # r_new = (r << 1) | (q >> 31)
                # q_new = q << 1
                r_shifted = (r << Bits(32)(1))
                q_msb = (q >> Bits(32)(31)) & Bits(32)(1)
                r_new = r_shifted | q_msb
                q_new = q << Bits(32)(1)
                
                # Try subtraction: r - d using 33-bit arithmetic to detect borrow
                # Extend to 33 bits for unsigned comparison
                r_ext = concat(Bits(1)(0), r_new)  # 33-bit, zero-extended
                d_ext = concat(Bits(1)(0), d)       # 33-bit, zero-extended
                diff_ext = (r_ext.bitcast(Int(33)) - d_ext.bitcast(Int(33))).bitcast(Bits(33))
                
                # Check if result is non-negative (r_new >= d as unsigned)
                # If diff_ext[32] == 0, then r_new >= d (no borrow)
                no_borrow = ~diff_ext[32:32]
                diff = diff_ext[0:31]  # Lower 32 bits
                
                # If no borrow: keep diff as new remainder, set q LSB to 1
                # If borrow: restore (keep r_new), q LSB stays 0
                r = no_borrow.select(diff, r_new)
                q = no_borrow.select(q_new | Bits(32)(1), q_new)
            
            stage2_quotient[0] = q
            stage2_remainder[0] = r
            stage2_divisor[0] = d
            stage2_addr_array[0] = stage1_addr_array[0]
            stage2_rob_index_array[0] = stage1_rob_index_array[0]
            stage2_get_remainder_array[0] = stage1_get_remainder_array[0]
            stage2_dividend_neg[0] = stage1_dividend_neg[0]
            stage2_divisor_neg[0] = stage1_divisor_neg[0]
            stage2_div_by_zero[0] = stage1_div_by_zero[0]
        stage2_valid[0] = stage1_valid[0].select(Bits(1)(1), Bits(1)(0)) & ~clear

        # ===== Stage 3: Last 16 iterations of restoring division =====
        with Condition(stage2_valid[0]):
            log("DIV Stage 3: Continuing division iterations")
            
            q = stage2_quotient[0]
            r = stage2_remainder[0]
            d = stage2_divisor[0]
            
            # Perform remaining 16 iterations
            for i in range(16):
                # Left shift {r, q} by 1
                r_shifted = (r << Bits(32)(1))
                q_msb = (q >> Bits(32)(31)) & Bits(32)(1)
                r_new = r_shifted | q_msb
                q_new = q << Bits(32)(1)
                
                # Use 33-bit arithmetic for unsigned comparison
                r_ext = concat(Bits(1)(0), r_new)
                d_ext = concat(Bits(1)(0), d)
                diff_ext = (r_ext.bitcast(Int(33)) - d_ext.bitcast(Int(33))).bitcast(Bits(33))
                no_borrow = ~diff_ext[32:32]
                diff = diff_ext[0:31]
                
                r = no_borrow.select(diff, r_new)
                q = no_borrow.select(q_new | Bits(32)(1), q_new)
            
            stage3_quotient[0] = q
            stage3_remainder[0] = r
            stage3_divisor[0] = d
            stage3_addr_array[0] = stage2_addr_array[0]
            stage3_rob_index_array[0] = stage2_rob_index_array[0]
            stage3_get_remainder_array[0] = stage2_get_remainder_array[0]
            stage3_dividend_neg[0] = stage2_dividend_neg[0]
            stage3_divisor_neg[0] = stage2_divisor_neg[0]
            stage3_div_by_zero[0] = stage2_div_by_zero[0]
        stage3_valid[0] = stage2_valid[0].select(Bits(1)(1), Bits(1)(0)) & ~clear

        # ===== Stage 4: Sign correction and output =====
        with Condition(stage3_valid[0]):
            log("DIV Stage 4: Sign correction")
            
            raw_quotient = stage3_quotient[0]
            raw_remainder = stage3_remainder[0]
            
            # Quotient sign: negative if exactly one of dividend/divisor is negative
            quotient_neg = stage3_dividend_neg[0] ^ stage3_divisor_neg[0]
            # Remainder sign: same as dividend
            remainder_neg = stage3_dividend_neg[0]
            
            # Apply sign correction
            final_quotient = quotient_neg.select(
                ((~raw_quotient).bitcast(Int(32)) + Int(32)(1)).bitcast(Bits(32)),
                raw_quotient
            )
            final_remainder = remainder_neg.select(
                ((~raw_remainder).bitcast(Int(32)) + Int(32)(1)).bitcast(Bits(32)),
                raw_remainder
            )
            
            # Handle divide by zero: quotient = -1 (all ones), remainder = dividend
            stage4_quotient[0] = stage3_div_by_zero[0].select(Bits(32)(0xFFFFFFFF), final_quotient)
            stage4_remainder[0] = stage3_div_by_zero[0].select(raw_remainder, final_remainder)
            stage4_addr_array[0] = stage3_addr_array[0]
            stage4_rob_index_array[0] = stage3_rob_index_array[0]
            stage4_get_remainder_array[0] = stage3_get_remainder_array[0]
            stage4_dividend_neg[0] = stage3_dividend_neg[0]
            stage4_divisor_neg[0] = stage3_divisor_neg[0]
            stage4_div_by_zero[0] = stage3_div_by_zero[0]
        stage4_valid[0] = stage3_valid[0].select(Bits(1)(1), Bits(1)(0)) & ~clear

        # ===== Output =====
        signal_array[0] = stage4_valid[0].select(Bits(1)(1), Bits(1)(0)) & ~clear
        with Condition(stage4_valid[0] & ~clear):
            result = stage4_get_remainder_array[0].select(stage4_remainder[0], stage4_quotient[0])
            log("DIV_ALU Result: quotient=0x{:08x}, remainder=0x{:08x}, output=0x{:08x}", 
                stage4_quotient[0], stage4_remainder[0], result)
            result_array[0] = result
            rob_index_array[0] = stage4_rob_index_array[0]
            pc_result_array[0] = (stage4_addr_array[0].bitcast(Int(32)) + Int(32)(4)).bitcast(Bits(32))
