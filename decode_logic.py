from assassyn.frontend import *
from opcodes import *
from instruction import *

def decode_logic(instruction):

    views = {i: i(instruction) for i in supported_types} # 这里的 views 指的是什么
    is_type = {i: Bits(1)(0) for i in supported_types}

    eqs = {}

    rd_valid = Bits(1)(0)
    rs1_valid = Bits(1)(0)
    rs2_valid = Bits(1)(0)
    imm_valid = Bits(1)(0)
    supported = Bits(1)(0) # supported 意为我们的 CPU 是否支持这个指令

    alu = Bits(RV32I_ALU.CNT)(0) # alu 的具体含义是什么
    cond = Bits(RV32I_ALU.CNT)(0)
    flip = Bits(1)(0)

    for mn, args, cur_type in supported_opcodes:

        ri = views[cur_type]
        signal = ri.decode(*args)
        eq = signal.eq
        is_type[cur_type] = is_type[cur_type] | eq
        eqs[mn] = eq
        supported = supported | eq

        alu = alu | eq.select(signal.alu, Bits(RV32I_ALU.CNT)(0))
        cond = cond | eq.select(signal.cond, Bits(RV32I_ALU.CNT)(0))
        flip = flip | eq.select(signal.flip, Bits(1)(0))

        suffix_length = 6 - len(mn)
        suffix = ' ' * suffix_length # suffix 的作用是什么

        fmt = None # fmt 是什么
        opcode = args[0]
        str_opcode = bin(opcode)[2:] # 将 opcode 转化为没有前缀的二进制字符串
        str_opcode = (7 - len(str_opcode)) * '0' + str_opcode
        fmt = f"{cur_type.PREFIX}.{mn}.{str_opcode}{suffix}" # 格式对齐

        args = []

        if ri.has_rd:
            fmt = fmt + "| rd: x{:02}      "
            args.append(ri.view().rd)
            rd_valid = rd_valid | eq
        else:
            fmt = fmt + "|              "

        if ri.has_rs1:
            fmt = fmt + "| rs1: x{:02}      "
            args.append(ri.view().rs1)
            rs1_valid = rs1_valid | eq
        else:
            fmt = fmt + "|              "
        
        if ri.has_rs2:
            fmt = fmt + "| rs2: x{:02}      "
            args.append(ri.view().rs2)
            rs2_valid = rs2_valid | eq
        else:
            fmt = fmt + "|              "

        imm = ri.imm(False)
        if imm is not None:
            fmt = fmt + "|imm: 0x{:x}"
            args.append(imm)

        with Condition(eq):
            log(fmt, *args)

    with Condition(~supported):
        view = views[RInstruction].view()
        log("Unsupported instruction: opcode = 0x{:x} func3: 0x{:x} func7: 0x{:x}", view.opcode, view.func3, view.func7)
        # assume(Bits(1)(0)) 等价于 C++ 中的 assert(false)

    alu = supported.select(alu, Bits(RV32I_ALU.CNT)(1 << RV32I_ALU.ALU_NONE))
    cond = supported.select(cond, Bits(RV32I_ALU.CNT)(1 << RV32I_ALU.ALU_TRUE))

    memory = concat(eqs['sw'], eqs['lw'] | eqs['lbu'])
    mem_ext = concat(eqs['lbu'], eqs['lbu'])

    is_branch = is_type[BInstruction] | is_type[JInstruction] | eqs['jalr'] | eqs['mret']
    is_reg_write = is_type[RInstruction] | is_type[IInstruction] | is_type[JInstruction] | eqs['lw'] | eqs['lbu'] | eqs['jalr'] # Newly inserted, waiting to be verified
    is_memory_write = is_type[SInstruction] # Newly inserted, waiting to be verified
    is_load = eqs['lw'] | eqs['lbu']
    is_load_or_store = is_load | is_memory_write
    is_offset_branch = is_type[BInstruction] | eqs['jal']
    link_pc = eqs['jalr'] | eqs['jal']
    is_jalr = eqs['jalr']
    is_pc_calc = eqs['auipc']

    rd = rd_valid.select(views[RInstruction].view().rd, Bits(5)(0))
    rs1 = rs1_valid.select(views[RInstruction].view().rs1, Bits(5)(0))
    rs2 = rs2_valid.select(views[RInstruction].view().rs2, Bits(5)(0))

    imm_valid = is_type[IInstruction] | is_type[UInstruction] | is_type[BInstruction] | is_type[JInstruction] | is_type[SInstruction]

    imm = Bits(32)(0)
    for i in supported_types:
        tmp_imm = views[i].imm(True)
        if tmp_imm is not None:
            imm = is_type[i].select(tmp_imm, imm)
    imm = eqs['lui'].select(views[UInstruction].imm(False).concat(Bits(12)(0)), imm)
    imm = eqs['auipc'].select(views[UInstruction].imm(False).concat(Bits(12)(0)), imm)

    csr_read = eqs['csrrs'] | eqs['mret']
    csr_calculate = eqs['csrrs']
    csr_write = eqs['csrrw'] | eqs['csrrwi']
    is_zimm = eqs['csrrwi']
    is_mepc = eqs['mret']

    with Condition(csr_read | csr_write):
        view = views[IInstruction].view()
        log('CSR instruction: opcode = 0x{:x} func3: 0x{:x} csr_addr: 0x{:x}', view.opcode, view.func3, view.imm)

    return decoder_signals.bundle(
        memory=memory,
        alu=alu,
        cond=cond,
        flip=flip,
        is_load_or_store = is_load_or_store,  # Newly inserted, waiting to be verified  
        is_reg_write = is_reg_write,          # Newly inserted, waiting to be verified
        is_memory_write = is_memory_write,    # Newly inserted, waiting to be verified
        is_branch=is_branch,
        is_offset_br=is_offset_branch,
        link_pc=link_pc,
        is_jalr=is_jalr,
        rs1=rs1,
        rs1_valid=rs1_valid,
        rs2=rs2,
        rs2_valid=rs2_valid,
        rd=rd,
        rd_valid=rd_valid,
        imm=imm,
        imm_valid=imm_valid,
        is_pc_calc = is_pc_calc,
        csr_read=csr_read,
        csr_write=csr_write,
        csr_calculate=csr_calculate,
        is_zimm = is_zimm,
        is_mepc = is_mepc,
        mem_ext = mem_ext
    )