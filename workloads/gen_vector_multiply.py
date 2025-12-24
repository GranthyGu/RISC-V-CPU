import sys
import os

# Add path to assembler
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../RISC-V-CPU/unit_tests')))

from assembler import *

def slli(rd, rs1, shamt):
    return encode_i_type(0b0010011, 0b001, rd, rs1, shamt)

def srli(rd, rs1, shamt):
    return encode_i_type(0b0010011, 0b101, rd, rs1, shamt)

def andi(rd, rs1, imm):
    return encode_i_type(0b0010011, 0b111, rd, rs1, imm)

instructions = [
    # Init
    (addi(5, 0, 0), "addi x5, x0, 0      i = 0"),
    (addi(6, 0, 20), "addi x6, x0, 20     limit = 20"),
    (addi(7, 0, 0), "addi x7, x0, 0      base_a = 0"),
    (addi(28, 0, 80), "addi x28, x0, 80    base_b = 80"),
    (addi(29, 0, 160), "addi x29, x0, 160   base_c = 160"),

    # Loop 1
    (lw(11, 7, 0), "lw x11, 0(x7)       x = a[i]"),
    (lw(12, 28, 0), "lw x12, 0(x28)      y = b[i]"),
    (jal(1, 64), "jal x1, 64          call multiply"),
    (sw(29, 10, 0), "sw x10, 0(x29)      c[i] = result"), # Note: sw args are (rs1, rs2, imm) -> (base, src, offset) in assembler.py? Let's check.
    (addi(7, 7, 4), "addi x7, x7, 4      base_a++"),
    (addi(28, 28, 4), "addi x28, x28, 4    base_b++"),
    (addi(29, 29, 4), "addi x29, x29, 4    base_c++"),
    (addi(5, 5, 1), "addi x5, x5, 1      i++"),
    (blt(5, 6, -32), "blt x5, x6, -32     if i < 20, goto loop_1"),

    # Loop 2
    (addi(5, 0, 0), "addi x5, x0, 0      i = 0"),
    (addi(29, 0, 160), "addi x29, x0, 160   base_c = 160"),
    (addi(10, 0, 0), "addi x10, x0, 0     ans = 0"),
    (lw(30, 29, 0), "lw x30, 0(x29)      load c[i]"),
    (add(10, 10, 30), "add x10, x10, x30   ans += c[i]"),
    (addi(29, 29, 4), "addi x29, x29, 4    base_c++"),
    (addi(5, 5, 1), "addi x5, x5, 1      i++"),
    (blt(5, 6, -16), "blt x5, x6, -16     if i < 20, goto loop_2"),
    (ebreak(), "ebreak              End of program"),

    # Multiply Function
    (addi(10, 0, 0), "addi x10, x0, 0     ans = 0"),
    (beq(12, 0, 28), "beq x12, x0, 28     if y == 0, goto end_mult"),
    (andi(13, 12, 1), "andi x13, x12, 1    x13 = y & 1"),
    (beq(13, 0, 8), "beq x13, x0, 8      if (y & 1) == 0, goto skip_add"),
    (add(10, 10, 11), "add x10, x10, x11   ans += x"),
    (slli(11, 11, 1), "slli x11, x11, 1    x <<= 1"),
    (srli(12, 12, 1), "srli x12, x12, 1    y >>= 1"),
    (jal(0, -24), "jal x0, -24         goto loop_mult"),
    (jalr(0, 1, 0), "jalr x0, 0(x1)      return"),
]

# Check sw arguments in assembler.py
# def sw(rs1, rs2, imm): return encode_s_type(..., rs1, rs2, imm)
# S-type: rs1 is base, rs2 is src.
# So sw(29, 10, 0) means base=x29, src=x10, offset=0. Correct.

with open('vector_multiply.exe', 'w') as f:
    addr = 0
    for instr, comment in instructions:
        hex_val = f"{instr:08x}"
        f.write(f"{hex_val} // {addr:2d}: {comment}\n")
        addr += 4

# Generate data file
with open('vector_multiply.data', 'w') as f:
    # a: 1..20
    for i in range(1, 21):
        f.write(f"{i:x}\n")
    # b: 21..40
    for i in range(21, 41):
        f.write(f"{i:x}\n")
    # c: 20 zeros
    for _ in range(20):
        f.write("0\n")
