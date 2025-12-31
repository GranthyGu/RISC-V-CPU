from assassyn.frontend import *
from instruction import *
from utils import *

class MUL_ALU(Module):

    def __init__(self):
        super().__init__(ports = {
            "valid": Port(Bits(1)),
            "rob_index": Port(Bits(3)),
            "alu_a": Port(Bits(32)),
            "alu_b": Port(Bits(32)),
            "calc_type": Port(Bits(RV32I_ALU.CNT)),
            "pc_addr": Port(Bits(32)),
            "get_high_bit": Port(Bits(1)),
            "rs1_sign": Port(Bits(1)),
            "rs2_sign": Port(Bits(1)),
            "clear": Port(Bits(1)),
        })
        self.name = "MUL_ALU"

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
            get_high_bit,
            rs1_sign,
            rs2_sign,
            clear
        ) = self.pop_all_ports(True)

        partial_products = [RegArray(Bits(64), 1) for _ in range(33)]
        partial_products_valid = RegArray(Bits(1), 1)
        partial_addr_array = RegArray(Bits(32), 1)
        partial_rob_index_array = RegArray(Bits(3), 1)
        partial_get_high_bit_array = RegArray(Bits(1), 1)
        partial_rs1_sign_array = RegArray(Bits(1), 1)
        partial_rs2_sign_array = RegArray(Bits(1), 1)

        final_result = RegArray(Bits(64), 1)
        final_carry_result = RegArray(Bits(64), 1)
        final_product_valid = RegArray(Bits(1), 1)
        final_addr_array = RegArray(Bits(32), 1)
        final_rob_index_array = RegArray(Bits(3), 1)
        final_get_high_bit_array = RegArray(Bits(1), 1)
        final_rs1_sign_array = RegArray(Bits(1), 1)
        final_rs2_sign_array = RegArray(Bits(1), 1)

        alu_a = rs1_sign.select(concat(alu_a[31:31], alu_a), concat(Bits(1)(0), alu_a))  # Extend alu_a to 33 bits for sign handling
        alu_b = rs2_sign.select(concat(alu_b[31:31], alu_b), concat(Bits(1)(0), alu_b))  # Extend alu_b to 33 bits for sign handling

        alu_b = concat(Bits(31)(0), alu_b)  # Extend alu_b to 64 bits for shifting

        with Condition(valid):
            log("alu_a: 0x{:08x} | alu_b: 0x{:08x} | pc_addr: 0x{:08x}", alu_a, alu_b, pc_addr)
            for i in range(33):
                alu_a_bit = ((alu_a >> Bits(32)(i)) & Bits(33)(1))[0:0]
                partial_products[i][0] = alu_a_bit.select(alu_b << Bits(32)(i), Bits(64)(0))
            partial_addr_array[0] = pc_addr
            partial_rob_index_array[0] = rob_index
            partial_get_high_bit_array[0] = get_high_bit
            partial_rs1_sign_array[0] = rs1_sign
            partial_rs2_sign_array[0] = rs2_sign
        partial_products_valid[0] = valid.select(Bits(1)(1), Bits(1)(0)) & ~clear

        with Condition(partial_products_valid[0]):
            log("Starting Wallace Tree Reduction")
            # Wallace Tree Reduction
            terms = [partial_products[i][0] for i in range(33)]
            
            while len(terms) > 2:
                next_terms = []
                while len(terms) >= 3:
                    a = terms.pop(0)
                    b = terms.pop(0)
                    c = terms.pop(0)
                    
                    s = a ^ b ^ c
                    cout = (a & b) | (b & c) | (c & a)
                    cout = cout << Bits(64)(1)
                    
                    next_terms.append(s)
                    next_terms.append(cout)
                
                next_terms.extend(terms)
                terms = next_terms
            
            final_result[0] = terms[0]
            final_carry_result[0] = terms[1]
            final_addr_array[0] = partial_addr_array[0]
            final_rob_index_array[0] = partial_rob_index_array[0]
            final_get_high_bit_array[0] = partial_get_high_bit_array[0]
            final_rs1_sign_array[0] = partial_rs1_sign_array[0]
            final_rs2_sign_array[0] = partial_rs2_sign_array[0]
        final_product_valid[0] = partial_products_valid[0].select(Bits(1)(1), Bits(1)(0)) & ~clear

        signal_array[0] = final_product_valid[0].select(Bits(1)(1), Bits(1)(0)) & ~clear
        with Condition(final_product_valid[0] & ~clear):
            log("MUL_ALU Result: 0x{:016x}", (final_result[0].bitcast(Int(64)) + final_carry_result[0].bitcast(Int(64))).bitcast(Bits(64)))
            result_array[0] = get_high_bit.select(
                (final_result[0].bitcast(Int(64)) + final_carry_result[0].bitcast(Int(64))).bitcast(Bits(64))[32:63],
                (final_result[0].bitcast(Int(64)) + final_carry_result[0].bitcast(Int(64))).bitcast(Bits(64))[0:31]
            )
            rob_index_array[0] = final_rob_index_array[0]
            pc_result_array[0] = (final_addr_array[0].bitcast(Int(32)) + Int(32)(4)).bitcast(Bits(32))

