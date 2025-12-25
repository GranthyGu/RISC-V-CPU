from assassyn.frontend import *
from opcodes import *
from instruction import *
from decode_logic import *
from ROB import *

class Decoder(Module):

    def __init__(self):
        super().__init__(ports = {
            "receive": Port(Bits(1)),
            "fetch_addr": Port(Bits(32)),
            "predicted_taken": Port(Bits(1))
        })
        self.name = "D"

    @module.combinational
    def build(self, rob: ROB, rdata: Array, rob_full_array: Array, decode_valid_array: Array, clear_signal_array: Array):
        receive, fetch_addr, predicted_taken = self.pop_all_ports(True)
        inst = rdata[0].bitcast(Bits(32))

        rob_full = rob_full_array[0]
        clear = clear_signal_array[0]

        sending = receive & ~clear

        log("raw: 0x{:08x}  | addr: 0x{:05x} | sending: {}", inst, fetch_addr, sending)

        rob.async_called(
            receive = sending,
            signals = decode_logic(inst),
            addr = fetch_addr,
            predicted_taken = predicted_taken
        )