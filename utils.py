from assassyn.frontend import *

def write1hot(arrs, idx_val, value, width = 5):
    for i, arr in enumerate(arrs):
        # log("idx_val: {} | i: {}", idx_val.bitcast(Bits(width)), Bits(width)(i))
        with Condition(idx_val.bitcast(Bits(width)) == Bits(width)(i)):
            # log("write1hot index: {} | value: 0x{:08x}", idx_val, value)
            arr[0] = value

def read_mux(arrs, idx_val, size, width):
    return_value = Bits(width)(0)
    for i in range(size):
        return_value = (Bits(5)(i) == idx_val.bitcast(Bits(5))).select(arrs[i][0], return_value)
    return return_value