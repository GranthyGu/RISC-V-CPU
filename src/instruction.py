from assassyn.frontend import *
from opcodes import *

class Instruction:

    FIELDS = [
        ((0, 6), 'opcode', Bits),
        ((7, 11), 'rd', Bits),
        ((15, 19), 'rs1', Bits),
        ((20, 24), 'rs2', Bits),
        ((12, 14), 'func3', Bits),
        ((25, 31), 'func7', Bits)
    ]

    def __init__(self, rd, rs1, rs2, func3, func7, fields, value):
        self.fields = fields.copy()
        for cond, entry in zip([True, rd, rs1, rs2, func3, func7], self.FIELDS):
            key, field, ty = entry
            setattr(self, f'has_{field}', cond)
            if cond:
                self.fields[key] = (field, ty)
        self.dtype = Record(self.fields)
        self.value = value

    def view(self):
        return self.dtype.view(self.value)
    
class InstSignal:

    def __init__(self, eq, alu, cond = None):
        self.eq = eq

        self.alu = Bits(RV32I_ALU.CNT)(0)
        if alu is not None:
            self.alu = Bits(RV32I_ALU.CNT)(1 << alu)

        self.cond = Bits(RV32I_ALU.CNT)(1)
        self.flip = Bits(1)(0)
        if cond is not None:
            pred, flip = cond
            self.cond = Bits(RV32I_ALU.CNT)(1 << pred)
            self.flip = Bits(1)(flip)

class RInstruction(Instruction):

    PREFIX = 'R'

    def __init__(self, value):
        super().__init__(True, True, True, True, True, {}, value)

    def decode(self, opcode, func3, func7, alu, ex_code = None):
        view = self.view()
        opcode = view.opcode == Bits(7)(opcode)
        func3 = view.func3 == Bits(3)(func3)
        func7 = view.func7 == Bits(7)(func7)
        if ex_code is not None:
            ex = view.rs2 == Bits(5)(ex_code)
        else:
            ex = Bits(1)(1)
        eq = opcode & func3 & func7 & ex
        return InstSignal(eq, alu)
    
    def imm(self, pad):
        return None
    
class IInstruction(Instruction):

    PREFIX = 'I'
    
    def __init__(self, value):
        super().__init__(True, True, False, True, False, {(20, 31): ('imm', Bits)}, value)

    def imm(self, pad):
        raw = self.view().imm
        if pad:
            signal = raw[11:11]
            signal = signal.select(Bits(20)(0xfffff), Bits(20)(0))
            raw = concat(signal, raw)
        return raw
    
    def decode(self, opcode, func3, alu, cond, ex_code1, ex_code2):
        view = self.view()
        opcode = view.opcode == Bits(7)(opcode)
        func3 = view.func3 == Bits(3)(func3)
        if ex_code1 is not None:
            ex1 = view.imm == Bits(12)(ex_code1)
        else:
            ex1 = Bits(1)(1)

        if ex_code2 is not None:
            ex2 = (view.imm)[6:11] == Bits(6)(ex_code2)
        else:
            ex2 = Bits(1)(1)

        eq = opcode & func3 & ex1 & ex2
        return InstSignal(eq, alu, cond = cond)

class SInstruction(Instruction):

    PREFIX = 'S'

    def __init__(self, value):
        fields = {(25, 31): ("imm11_5", Bits), (7, 11): ('imm4_0', Bits)}
        super().__init__(False, True, True, True, False, fields, value)

    def imm(self, pad):
        imm = self.view().imm11_5.concat(self.view().imm4_0)
        if pad:
            sign_bit = imm[11:11]
            sign_extension = sign_bit.select(Bits(20)(0xfffff), Bits(20)(0))
            imm = concat(sign_extension, imm)
        return imm
    
    def decode(self, opcode, func3, alu):
        view = self.view()
        opcode = view.opcode == Bits(7)(opcode)
        func3 = view.func3 == Bits(3)(func3)
        eq = opcode & func3
        return InstSignal(eq, alu)
    
class UInstruction(Instruction):

    PREFIX = 'U'

    def __init__(self, value):
        super().__init__(True, False, False, False, False, {(12, 31): ('imm', Bits)}, value)

    def imm(self, pad):
        raw = self.view().imm
        if pad:
            raw = concat(raw, Bits(12)(0))
        return raw
    
    def decode(self, opcode, alu):
        view = self.view()
        eq = view.opcode == Bits(7)(opcode)
        return InstSignal(eq, alu)
    
class JInstruction(Instruction):

    PREFIX = 'J'

    def __init__(self, value):
        fields = {
            (12, 19): ("imm19_12", Bits),
            (20, 20): ("imm11", Bits),
            (21, 30): ("imm10_1", Bits),
            (31, 31): ("imm20", Bits)
        }
        super().__init__(True, False, False, False, False, fields, value)

    def imm(self, pad):
        view = self.view()
        imm = concat(view.imm20, view.imm19_12, view.imm11, view.imm10_1, Bits(1)(0))
        if pad:
            signal = imm[20:20]
            signal = signal.select(Bits(11)(0x7ff), Bits(11)(0))
            imm = concat(signal, imm)
        return imm
    
    def decode(self, opcode, alu, cond):
        view = self.view()
        eq = view.opcode == Bits(7)(opcode)
        return InstSignal(eq, alu, cond = cond)
    
class BInstruction(Instruction):
    
    PREFIX = 'B'

    def __init__(self, value):
        fields = {
            (7, 7): ("imm11", Bits),
            (8, 11): ("imm4_1", Bits),
            (25, 30): ("imm10_5", Bits),
            (31, 31): ("imm12", Bits)
        }
        super().__init__(False, True, True, True, False, fields, value)

    def imm(self, pad):
        view = self.view()
        imm = concat(view.imm12, view.imm11, view.imm10_5, view.imm4_1, Bits(1)(0))
        if pad:
            signal = imm[12:12]
            sign_extenstion = signal.select(Bits(19)(0x7ffff), Bits(19)(0))
            imm = concat(sign_extenstion, imm)
        return imm

    def decode(self, opcode, func3, cmp, flip):
        view = self.view()
        opcode = view.opcode == Bits(7)(opcode)
        func3 = view.func3 == Bits(3)(func3)
        eq = opcode & func3
        return InstSignal(eq, RV32I_ALU.ALU_ADD, cond = (cmp, flip))

class RV32I_ALU:
    CNT = 18

    ALU_ADD = 0
    ALU_SUB = 1
    ALU_XOR = 2
    ALU_OR = 3
    ALU_ORI = 13
    ALU_AND = 4
    ALU_SLL = 5
    ALU_SRL = 6
    ALU_SRA = 7
    ALU_SRA_U = 12
    ALU_CMP_EQ = 8
    ALU_CMP_LT = 9
    ALU_CMP_LTU = 10
    ALU_TRUE = 11
    ALU_NONE = 15
    ALU_MUL = 14
    ALU_DIV = 16
    ALU_REM = 17

supported_opcodes = [
    ("jal", (0b1101111, RV32I_ALU.ALU_ADD, (RV32I_ALU.ALU_TRUE, False)), JInstruction),

    ("lui", (0b0110111, RV32I_ALU.ALU_ADD), UInstruction),

    ("add", (0b0110011, 0b000, 0b0000000, RV32I_ALU.ALU_ADD), RInstruction),
    ("sub", (0b0110011, 0b000, 0b0100000, RV32I_ALU.ALU_SUB), RInstruction),
    ("or", (0b0110011, 0b110, 0b0000000, RV32I_ALU.ALU_OR), RInstruction),
    ("mul", (0b0110011, 0b000, 0b0000001, RV32I_ALU.ALU_MUL), RInstruction),
    ("mulh", (0b0110011, 0b001, 0b0000001, RV32I_ALU.ALU_MUL), RInstruction),
    ("mulhu", (0b0110011, 0b011, 0b0000001, RV32I_ALU.ALU_MUL), RInstruction),
    ("mulhsu", (0b0110011, 0b010, 0b0000001, RV32I_ALU.ALU_MUL), RInstruction),
    
    # Division instructions (RV32M extension)
    ("div", (0b0110011, 0b100, 0b0000001, RV32I_ALU.ALU_DIV), RInstruction),
    ("divu", (0b0110011, 0b101, 0b0000001, RV32I_ALU.ALU_DIV), RInstruction),
    ("rem", (0b0110011, 0b110, 0b0000001, RV32I_ALU.ALU_REM), RInstruction),
    ("remu", (0b0110011, 0b111, 0b0000001, RV32I_ALU.ALU_REM), RInstruction),

    ("jalr", (0b1100111, 0b000, RV32I_ALU.ALU_ADD, (RV32I_ALU.ALU_TRUE, False), None, None), IInstruction),
    ("addi", (0b0010011, 0b000, RV32I_ALU.ALU_ADD, None, None, None), IInstruction),

    # Permenantly stop here to comprehend the total structure in a rapid way
    ('lw'    , (0b0000011, 0b010, RV32I_ALU.ALU_ADD, None, None, None), IInstruction),
    ('lbu'   , (0b0000011, 0b100, RV32I_ALU.ALU_ADD, None, None, None), IInstruction),

    ('ebreak', (0b1110011, 0b000, RV32I_ALU.ALU_NONE, None,0b000000000001,None), IInstruction),

    ('sw'    , (0b0100011, 0b010, RV32I_ALU.ALU_ADD), SInstruction),

    # mn,       opcode,    funct3,cmp,                  flip
    ('beq'   , (0b1100011, 0b000, RV32I_ALU.ALU_CMP_EQ,  False), BInstruction),
    ('bne'   , (0b1100011, 0b001, RV32I_ALU.ALU_CMP_EQ,  True), BInstruction),
    ('blt'   , (0b1100011, 0b100, RV32I_ALU.ALU_CMP_LT,  False), BInstruction),
    ('bge'   , (0b1100011, 0b101, RV32I_ALU.ALU_CMP_LT,  True), BInstruction),
    ('bgeu' , (0b1100011, 0b111, RV32I_ALU.ALU_CMP_LTU, True), BInstruction),
    ('bltu' , (0b1100011, 0b110, RV32I_ALU.ALU_CMP_LTU, False), BInstruction),

    ('csrrs'   , (0b1110011, 0b010, RV32I_ALU.ALU_OR, None ,None ,None), IInstruction),
    ('auipc' , (0b0010111, RV32I_ALU.ALU_ADD), UInstruction),
    ('csrrw' , (0b1110011, 0b001, RV32I_ALU.ALU_ADD, None,None,None), IInstruction),
    ('csrrwi' , (0b1110011, 0b101, RV32I_ALU.ALU_ADD, None,None,None), IInstruction),

    ('slli' , (0b0010011, 0b001, RV32I_ALU.ALU_SLL, None, None , 0b000000), IInstruction),
    ('sll'  , (0b0110011, 0b001, 0b0000000, RV32I_ALU.ALU_SLL), RInstruction),
    ('srai' , (0b0010011, 0b101, RV32I_ALU.ALU_SRA,  None,None , 0b010000), IInstruction),#signed
    ('srli' , (0b0010011, 0b101, RV32I_ALU.ALU_SRA_U,  None, None , 0b000000), IInstruction),#0
    ('sltu' , (0b0110011, 0b011, 0b0000000, RV32I_ALU.ALU_CMP_LTU), RInstruction),
    ('srl'  , (0b0110011, 0b101, 0b0000000, RV32I_ALU.ALU_SRA_U), RInstruction),
    ('sra'  , (0b0110011, 0b101, 0b0100000, RV32I_ALU.ALU_SRA), RInstruction),

    #todo: mret is not supported for setting the MPIE in CSR(mstatus)
    ('mret' , (0b1110011, 0b000, 0b0011000,RV32I_ALU.ALU_ADD,0b00010), RInstruction),
    #we have only a sigle thread, so we don't need to deal with 'fence' instruction
    ('fence' , (0b0001111, 0b000, RV32I_ALU.ALU_ADD, None,None,None), IInstruction),
    ('ecall' , (0b1110011, 0b000, RV32I_ALU.ALU_NONE, None,0b000000000000,None), IInstruction),
    
    ('and' , (0b0110011, 0b111, 0b0000000, RV32I_ALU.ALU_AND), RInstruction),
    ('xor' , (0b0110011, 0b100, 0b0000000, RV32I_ALU.ALU_XOR), RInstruction),
    ('andi' , (0b0010011, 0b111, RV32I_ALU.ALU_AND, None,None,None), IInstruction),
    ('ori' , (0b0010011, 0b110, RV32I_ALU.ALU_ORI, None,None,None), IInstruction),
    ('xori' , (0b0010011, 0b100, RV32I_ALU.ALU_XOR, None,None,None), IInstruction),
]
    
decoder_signals = Record(
    rs1 = Bits(5),
    rs1_valid = Bits(1),
    rs2 = Bits(5),
    rs2_valid = Bits(1),
    rd = Bits(5),
    rd_valid = Bits(1),
    csr_read = Bits(1),
    csr_write = Bits(1),
    csr_calculate = Bits(1),
    is_zimm = Bits(1),
    is_mepc = Bits(1),
    is_pc_calc = Bits(1),
    imm = Bits(32),
    imm_valid = Bits(1),
    # Bit 0 is read, bit 1 is write.
    memory = Bits(2),
    alu = Bits(RV32I_ALU.CNT),
    cond = Bits(RV32I_ALU.CNT),
    # Whether to flip the sign.
    flip = Bits(1),
    is_branch = Bits(1),
    is_offset_br = Bits(1),
    link_pc = Bits(1),
    mem_ext = Bits(2),
    is_memory_write = Bits(1),
    is_reg_write = Bits(1),
    is_load_or_store = Bits(1),
    is_jalr = Bits(1),
    # 00: byte, 01: half, 10: word
    memory_length = Bits(2),
    is_mult = Bits(1),
    # In multiplication instructions, whether to get the high 32 bits.
    get_high_bit = Bits(1),
    # Whether rs1 is signed or unsigned, useful for multiplication.
    rs1_sign = Bits(1),
    # Whether rs2 is signed or unsigned, useful for multiplication.
    rs2_sign = Bits(1),
    # Whether this is a division instruction.
    is_div = Bits(1),
    # In division instructions, whether to get the remainder instead of quotient.
    get_remainder = Bits(1)
)

supported_types = [RInstruction, IInstruction, BInstruction, UInstruction, JInstruction, SInstruction]